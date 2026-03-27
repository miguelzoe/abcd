import json
import logging

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

logger = logging.getLogger('apps.reservations.consumers')


class TripTrackingConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer pour le suivi en temps réel de la position du technicien.

    URL de connexion : ws/trip/{reservation_id}/?token=<jwt_access_token>
    Groupe           : trip_{reservation_id}

    Utilisateurs autorisés :
      - Le client de la réservation
      - Le technicien assigné à la réservation
      - Tout administrateur
    """

    async def connect(self):
        self.reservation_id = self.scope['url_route']['kwargs']['reservation_id']
        self.group_name = f'trip_{self.reservation_id}'

        # 1. Extraire le token JWT depuis le query string (?token=xxx)
        token = self._get_token_from_query_string()
        if not token:
            logger.warning('WS rejeté – token manquant (reservation=%s)', self.reservation_id)
            await self.close(code=4001)
            return

        # 2. Valider le token et charger l'utilisateur
        user = await self._authenticate_token(token)
        if user is None:
            logger.warning('WS rejeté – token invalide/expiré (reservation=%s)', self.reservation_id)
            await self.close(code=4001)
            return

        self.user = user

        # 3. Vérifier que l'utilisateur a accès à cette réservation
        authorized = await self._user_can_access_reservation(self.reservation_id, user)
        if not authorized:
            logger.warning(
                'WS rejeté – accès refusé : user=%s reservation=%s',
                user.id, self.reservation_id
            )
            await self.close(code=4003)
            return

        # 4. Rejoindre le groupe et accepter la connexion
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        logger.info(
            'WS connecté : user=%s reservation=%s',
            user.id, self.reservation_id
        )

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        logger.info(
            'WS déconnecté : reservation=%s code=%s',
            getattr(self, 'reservation_id', '?'), close_code
        )

    async def receive(self, text_data=None, bytes_data=None):
        # Lecture seule : les mises à jour de position arrivent via POST HTTP,
        # pas depuis le client WebSocket.
        pass

    # ------------------------------------------------------------------ #
    #  Handlers du channel layer                                           #
    # ------------------------------------------------------------------ #

    async def trip_location_update(self, event):
        """
        Reçoit un message 'trip.location.update' depuis le channel layer
        et le transmet au client WebSocket connecté.

        Clés attendues dans event :
            reservation_id, latitude, longitude, timestamp, technician_id
        """
        await self.send(text_data=json.dumps({
            'type': 'location_update',
            'reservation_id': event['reservation_id'],
            'latitude': event['latitude'],
            'longitude': event['longitude'],
            'timestamp': event['timestamp'],
            'technician_id': event['technician_id'],
        }))

    # ------------------------------------------------------------------ #
    #  Helpers privés                                                      #
    # ------------------------------------------------------------------ #

    def _get_token_from_query_string(self):
        """Extrait le token JWT du query string (?token=<valeur>)."""
        raw = self.scope.get('query_string', b'')
        if isinstance(raw, bytes):
            raw = raw.decode('utf-8')
        for segment in raw.split('&'):
            if segment.startswith('token='):
                return segment[len('token='):]
        return None

    @database_sync_to_async
    def _authenticate_token(self, raw_token):
        """
        Décode un AccessToken SimpleJWT et retourne l'utilisateur correspondant,
        ou None en cas d'échec (expiré, invalide, utilisateur supprimé).
        """
        try:
            from rest_framework_simplejwt.tokens import AccessToken
            from django.contrib.auth import get_user_model

            User = get_user_model()
            payload = AccessToken(raw_token)
            return User.objects.get(id=payload['user_id'])
        except Exception:
            return None

    @database_sync_to_async
    def _user_can_access_reservation(self, reservation_id, user):
        """
        Retourne True si l'utilisateur est autorisé à suivre cette réservation :
        - Administrateurs / staff
        - Le client propriétaire de la réservation
        - Le technicien assigné à la réservation
        """
        try:
            from django.db.models import Q
            from apps.reservations.models import Reservation

            if user.is_staff or getattr(user, 'user_type', None) == 'administrator':
                return Reservation.objects.filter(pk=reservation_id).exists()

            ownership_q = Q()
            if hasattr(user, 'client_profile'):
                ownership_q |= Q(client=user.client_profile)
            if hasattr(user, 'technician_profile'):
                ownership_q |= Q(technician=user.technician_profile)

            if not ownership_q:
                return False

            return Reservation.objects.filter(pk=reservation_id).filter(ownership_q).exists()

        except Exception:
            logger.exception(
                'Erreur vérification accès : user=%s reservation=%s',
                user.id, reservation_id
            )
            return False
