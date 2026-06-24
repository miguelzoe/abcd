from django.db.models import Q
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.reservations.models import Reservation
from apps.voice_calls.models import VoiceCallSession, VoiceCallSignal
from apps.voice_calls.serializers import VoiceCallSessionSerializer, VoiceCallSignalSerializer
from apps.voice_calls.services import (
    broadcast_call_event,
    create_call_notification,
    notify_voice_event,
    session_payload,
)


class VoiceCallSessionViewSet(viewsets.ModelViewSet):
    """API REST pour créer, accepter, refuser, terminer et consulter les appels internes."""

    serializer_class = VoiceCallSessionSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        user = self.request.user
        return VoiceCallSession.objects.select_related(
            'reservation', 'caller', 'callee', 'reservation__client__user', 'reservation__technician__user'
        ).filter(Q(caller=user) | Q(callee=user)).order_by('-created_at')

    def _get_owned_session(self, pk):
        return self.get_queryset().get(pk=pk)

    def create(self, request, *args, **kwargs):
        """Démarrer un appel à partir d'une réservation.

        Body attendu: {"reservation_id": 123}. Le backend déduit automatiquement
        l'autre interlocuteur (client ou technicien) pour éviter les erreurs côté mobile.
        """
        reservation_id = request.data.get('reservation_id')
        if not reservation_id:
            return Response({'detail': 'Réservation requise.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            reservation = Reservation.objects.select_related('client__user', 'technician__user').get(id=reservation_id)
        except Reservation.DoesNotExist:
            return Response({'detail': 'Réservation introuvable.'}, status=status.HTTP_404_NOT_FOUND)

        user = request.user
        if user.user_type == 'client' and reservation.client.user_id == user.id and reservation.technician:
            callee = reservation.technician.user
        elif user.user_type == 'technician' and reservation.technician and reservation.technician.user_id == user.id:
            callee = reservation.client.user
        else:
            return Response({'detail': 'Vous ne pouvez appeler que l’interlocuteur lié à cette intervention.'}, status=status.HTTP_403_FORBIDDEN)

        if callee.id == user.id:
            return Response({'detail': 'Appel impossible vers votre propre compte.'}, status=status.HTTP_400_BAD_REQUEST)

        # Évite de multiplier les sessions ouvertes sur la même réservation.
        open_call = VoiceCallSession.objects.filter(
            reservation=reservation,
            status__in=[VoiceCallSession.STATUS_RINGING, VoiceCallSession.STATUS_ACCEPTED],
        ).filter(Q(caller=user, callee=callee) | Q(caller=callee, callee=user)).first()
        if open_call:
            data = self.get_serializer(open_call).data
            return Response(data, status=status.HTTP_200_OK)

        session = VoiceCallSession.objects.create(
            reservation=reservation,
            caller=user,
            callee=callee,
            metadata={
                'reservation_status': reservation.status,
                'service_type': reservation.service_type,
            },
        )
        VoiceCallSignal.objects.create(session=session, sender=user, signal_type='ringing', payload={})
        create_call_notification(session, request=request)
        return Response(self.get_serializer(session).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        session = self._get_owned_session(pk)
        if session.callee_id != request.user.id:
            return Response({'detail': 'Seul le destinataire peut accepter cet appel.'}, status=status.HTTP_403_FORBIDDEN)
        if session.status != VoiceCallSession.STATUS_RINGING:
            return Response({'detail': 'Cet appel n’est plus en attente.'}, status=status.HTTP_400_BAD_REQUEST)
        session.mark_accepted()
        VoiceCallSignal.objects.create(session=session, sender=request.user, signal_type='accepted', payload={})
        payload = {'session': session_payload(session, request=request), 'accepted_by': request.user.id}
        notify_voice_event(session.caller, 'call_accepted', payload)
        broadcast_call_event(str(session.id), 'call_accepted', payload)
        return Response(self.get_serializer(session).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        session = self._get_owned_session(pk)
        if session.callee_id != request.user.id:
            return Response({'detail': 'Seul le destinataire peut refuser cet appel.'}, status=status.HTTP_403_FORBIDDEN)
        if not session.is_open:
            return Response({'detail': 'Cet appel est déjà terminé.'}, status=status.HTTP_400_BAD_REQUEST)
        reason = str(request.data.get('reason') or 'refusé').strip()
        session.mark_terminal(VoiceCallSession.STATUS_REJECTED, reason)
        VoiceCallSignal.objects.create(session=session, sender=request.user, signal_type='rejected', payload={'reason': reason})
        payload = {'session': session_payload(session, request=request), 'reason': reason}
        notify_voice_event(session.caller, 'call_rejected', payload)
        broadcast_call_event(str(session.id), 'call_rejected', payload)
        return Response(self.get_serializer(session).data)

    @action(detail=True, methods=['post'])
    def end(self, request, pk=None):
        session = self._get_owned_session(pk)
        if not session.is_open:
            return Response(self.get_serializer(session).data)
        reason = str(request.data.get('reason') or 'terminé').strip()
        terminal_status = VoiceCallSession.STATUS_ENDED if session.answered_at else VoiceCallSession.STATUS_CANCELLED
        session.mark_terminal(terminal_status, reason)
        VoiceCallSignal.objects.create(session=session, sender=request.user, signal_type='ended', payload={'reason': reason})
        payload = {'session': session_payload(session, request=request), 'reason': reason, 'ended_by': request.user.id}
        other = session.callee if session.caller_id == request.user.id else session.caller
        notify_voice_event(other, 'call_ended', payload)
        broadcast_call_event(str(session.id), 'call_ended', payload)
        return Response(self.get_serializer(session).data)

    @action(detail=True, methods=['post'])
    def missed(self, request, pk=None):
        session = self._get_owned_session(pk)
        if session.status != VoiceCallSession.STATUS_RINGING:
            return Response(self.get_serializer(session).data)
        session.mark_terminal(VoiceCallSession.STATUS_MISSED, 'appel manqué')
        VoiceCallSignal.objects.create(session=session, sender=request.user, signal_type='ended', payload={'reason': 'appel manqué'})
        payload = {'session': session_payload(session, request=request)}
        notify_voice_event(session.caller, 'call_missed', payload)
        broadcast_call_event(str(session.id), 'call_missed', payload)
        return Response(self.get_serializer(session).data)

    @action(detail=True, methods=['post'])
    def signal(self, request, pk=None):
        """Fallback REST pour enregistrer/retransmettre un signal si le WebSocket n'est pas ouvert."""
        session = self._get_owned_session(pk)
        if request.user.id not in {session.caller_id, session.callee_id}:
            return Response({'detail': 'Non autorisé.'}, status=status.HTTP_403_FORBIDDEN)
        signal_type = str(request.data.get('signal_type') or '').strip()
        payload = request.data.get('payload') or {}
        if signal_type not in {'offer', 'answer', 'ice-candidate', 'mute-state', 'failed'}:
            return Response({'detail': 'Signal invalide.'}, status=status.HTTP_400_BAD_REQUEST)
        signal = VoiceCallSignal.objects.create(session=session, sender=request.user, signal_type=signal_type, payload=payload)
        broadcast_call_event(
            str(session.id),
            'signal',
            VoiceCallSignalSerializer(signal).data,
        )
        return Response(VoiceCallSignalSerializer(signal).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'], url_path='signals')
    def signals(self, request, pk=None):
        """Historique de signalisation pour fallback REST si le WebSocket est instable.

        Query params optionnels:
        - after_id: ne retourner que les signaux dont l'id est supérieur.
        - limit: nombre maximal de signaux, borné à 200.
        """
        session = self._get_owned_session(pk)
        qs = session.signals.select_related('sender').order_by('id')
        after_id = request.query_params.get('after_id')
        if after_id:
            try:
                qs = qs.filter(id__gt=int(after_id))
            except (TypeError, ValueError):
                return Response({'detail': 'after_id invalide.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            limit = min(max(int(request.query_params.get('limit', 100)), 1), 200)
        except (TypeError, ValueError):
            limit = 100
        data = VoiceCallSignalSerializer(qs[:limit], many=True).data
        return Response(data)

    @action(detail=False, methods=['get'], url_path='ice-config')
    def ice_config(self, request):
        """Configuration STUN/TURN à utiliser par le mobile WebRTC."""
        from django.conf import settings

        ice_servers = [{'urls': list(getattr(settings, 'STUN_SERVERS', [])) or ['stun:stun.l.google.com:19302']}]
        turn_url = getattr(settings, 'TURN_SERVER_URL', '')
        if turn_url:
            turn = {'urls': turn_url}
            username = getattr(settings, 'TURN_SERVER_USERNAME', '')
            credential = getattr(settings, 'TURN_SERVER_CREDENTIAL', '')
            if username:
                turn['username'] = username
            if credential:
                turn['credential'] = credential
            ice_servers.append(turn)
        return Response({'iceServers': ice_servers})

    @action(detail=False, methods=['get'])
    def history(self, request):
        qs = self.get_queryset()
        reservation_id = request.query_params.get('reservation_id')
        if reservation_id:
            qs = qs.filter(reservation_id=reservation_id)
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        return Response(self.get_serializer(qs[:50], many=True).data)
