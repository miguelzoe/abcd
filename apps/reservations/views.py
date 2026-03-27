from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.contrib.gis.geos import Point
from datetime import datetime, timedelta

from apps.reservations.models import (
    Reservation, Evaluation, Vehicle, Diagnostic,
    TripTracking, ChatMessage, ChatConversation,
    TechnicianAvailability, WorkProgress
)
from apps.reservations.serializers import *
from apps.reservations.permissions import (
    IsReservationOwner, CanCreateReservation, CanUpdateReservationStatus, CanEvaluate
)
from apps.reservations.services import (
    complete_reservation, cancel_reservation, reassign_technician,
    get_reservation_stats
)


class VehicleViewSet(viewsets.ModelViewSet):
    """ViewSet pour les véhicules"""
    queryset = Vehicle.objects.all()
    serializer_class = VehicleSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if user.user_type == 'client':
            return Vehicle.objects.filter(client__user=user)
        elif user.user_type == 'administrator':
            return Vehicle.objects.all()
        return Vehicle.objects.none()
    
    def perform_create(self, serializer):
        serializer.save(client=self.request.user.client_profile)
    
    @action(detail=True, methods=['post'])
    def update_mileage(self, request, pk=None):
        vehicle = self.get_object()
        new_mileage = request.data.get('mileage')
        
        if not new_mileage or new_mileage < vehicle.mileage:
            return Response({'error': 'Kilométrage invalide'}, status=status.HTTP_400_BAD_REQUEST)
        
        vehicle.mileage = new_mileage
        vehicle.save()
        return Response(VehicleSerializer(vehicle).data)


class ReservationViewSet(viewsets.ModelViewSet):
    """ViewSet pour les réservations"""
    queryset = Reservation.objects.select_related('client__user', 'technician__user', 'vehicle').prefetch_related('evaluation', 'diagnostic', 'work_progress')
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ReservationListSerializer
        elif self.action == 'create':
            return ReservationCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return ReservationUpdateSerializer
        elif self.action == 'retrieve':
            return ReservationDetailSerializer
        return ReservationSerializer
    
    def get_permissions(self):
        if self.action == 'create':
            return [CanCreateReservation()]
        elif self.action in ['update', 'partial_update', 'start', 'complete', 'cancel']:
            return [CanUpdateReservationStatus()]
        elif self.action == 'destroy':
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]
    
    def get_queryset(self):
        user = self.request.user
        queryset = Reservation.objects.select_related('client__user', 'technician__user', 'vehicle').prefetch_related('evaluation', 'diagnostic')
        
        if user.user_type == 'client':
            queryset = queryset.filter(client__user=user)
        elif user.user_type == 'technician':
            queryset = queryset.filter(technician__user=user)
        elif user.user_type != 'administrator':
            queryset = queryset.none()
        
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        service_type = self.request.query_params.get('service_type')
        if service_type:
            queryset = queryset.filter(service_type=service_type)
        
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        if date_from:
            queryset = queryset.filter(date__gte=date_from)
        if date_to:
            queryset = queryset.filter(date__lte=date_to)
        
        return queryset.order_by('-created_at')

    @action(detail=True, methods=['post'], url_path='respond')
    def respond(self, request, pk=None):
        """Réponse du technicien à une demande (accept/refuse).

        Body: {"action": "accept"|"refuse"}
        """
        reservation = self.get_object()

        if request.user.user_type != 'technician':
            return Response({'error': 'Seul un technicien peut répondre'}, status=status.HTTP_403_FORBIDDEN)
        if not reservation.technician or reservation.technician.user != request.user:
            return Response({'error': 'Non autorisé'}, status=status.HTTP_403_FORBIDDEN)

        action_value = (request.data.get('action') or '').strip().lower()
        if action_value not in ['accept', 'refuse']:
            return Response({'error': 'action invalide'}, status=status.HTTP_400_BAD_REQUEST)

        from apps.users.models import Notification
        from apps.users.services import send_expo_push_to_user

        # Toujours créer une conversation si absente (pour la messagerie)
        ChatConversation.objects.get_or_create(reservation=reservation)

        client_user = reservation.client.user
        tech_user = reservation.technician.user

        if action_value == 'accept':
            # Confirmer la réservation
            reservation.status = 'confirmed'
            reservation.save(update_fields=['status'])

            # Mettre le technicien en busy
            try:
                tech = reservation.technician
                tech.status = 'busy'
                tech.save(update_fields=['status'])
            except Exception:
                pass

            # Créer trip tracking si absent
            TripTracking.objects.get_or_create(reservation=reservation)

            # Notifications client: acceptation + demande de paiement du déplacement
            title = 'Réservation acceptée'
            body = f"{tech_user.get_full_name() or tech_user.username} a accepté votre demande."
            data = {'type': 'reservation_accepted', 'reservation_id': reservation.id}
            Notification.objects.create(user=client_user, title=title, body=body, data=data)
            send_expo_push_to_user(client_user, title=title, body=body, data=data)

            deposit_title = 'Paiement requis'
            deposit_body = 'Le technicien a approuvé votre demande. Veuillez payer 2000 FCFA pour les frais de déplacement.'
            deposit_data = {'type': 'payment_required', 'kind': 'deposit', 'reservation_id': reservation.id, 'amount': 2000}
            Notification.objects.create(user=client_user, title=deposit_title, body=deposit_body, data=deposit_data)
            send_expo_push_to_user(client_user, title=deposit_title, body=deposit_body, data=deposit_data)

            # Marquer notifications technicien liées à cette réservation comme lues
            Notification.objects.filter(user=tech_user, data__reservation_id=reservation.id, read_at__isnull=True).update(read_at=timezone.now())

            return Response({'status': 'accepted', 'reservation': ReservationDetailSerializer(reservation).data})

        # refuse
        reservation.status = 'cancelled'
        reservation.cancelled_at = timezone.now()
        reservation.cancelled_by = request.user
        reservation.cancellation_reason = 'Refusée par le technicien'
        reservation.save(update_fields=['status', 'cancelled_at', 'cancelled_by', 'cancellation_reason'])

        title = 'Réservation refusée'
        body = f"{tech_user.get_full_name() or tech_user.username} a refusé votre demande. Veuillez choisir un autre technicien."
        data = {'type': 'reservation_refused', 'reservation_id': reservation.id}
        Notification.objects.create(user=client_user, title=title, body=body, data=data)
        send_expo_push_to_user(client_user, title=title, body=body, data=data)

        Notification.objects.filter(user=tech_user, data__reservation_id=reservation.id, read_at__isnull=True).update(read_at=timezone.now())

        return Response({'status': 'refused', 'reservation_id': reservation.id})
    
    @action(detail=True, methods=['post'])
    def start_trip(self, request, pk=None):
        """Démarrer le trajet"""
        reservation = self.get_object()

        # Le trajet ne peut démarrer qu'après paiement confirmé du transport.
        if reservation.status not in ['confirmed', 'technician_dispatched', 'technician_arrived', 'in_progress', 'diagnosis_submitted', 'awaiting_client_approval']:
            return Response({'error': 'Statut invalide'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            from apps.payments.models import PaymentTransaction
            transport_paid = PaymentTransaction.objects.filter(
                reservation=reservation,
                kind='deposit',
                status='confirmed'
            ).exists()
            if not transport_paid:
                return Response({'error': 'Les frais de déplacement (2000 FCFA) doivent être confirmés avant le départ.'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            pass
        
        if request.user.user_type != 'technician':
            return Response({'error': 'Seul un technicien peut démarrer'}, status=status.HTTP_403_FORBIDDEN)
        
        trip, created = TripTracking.objects.get_or_create(
            reservation=reservation,
            defaults={'status': 'en_route', 'started_at': timezone.now()}
        )
        
        if not created:
            trip.status = 'en_route'
            trip.started_at = timezone.now()
            trip.save()
        
        # Ne pas "revenir en arrière" si la mission a déjà évolué.
        if reservation.status == 'confirmed':
            reservation.status = 'technician_dispatched'
            reservation.save(update_fields=['status'])
        
        return Response({
            'reservation': ReservationSerializer(reservation).data,
            'trip_tracking': TripTrackingSerializer(trip).data
        })
    
    @action(detail=True, methods=['post'])
    def update_location(self, request, pk=None):
        """Mettre à jour la position GPS"""
        reservation = self.get_object()

        # Mobile friendly: si le tracking n'existe pas encore, on le crée.
        trip, _ = TripTracking.objects.get_or_create(
            reservation=reservation,
            defaults={'status': 'en_route', 'started_at': timezone.now()}
        )

        latitude = request.data.get('latitude', None)
        longitude = request.data.get('longitude', None)

        if latitude is None or longitude is None:
            return Response({'error': 'Coordonnées requises'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            latitude = float(latitude)
            longitude = float(longitude)
        except (TypeError, ValueError):
            return Response({'error': 'Coordonnées invalides'}, status=status.HTTP_400_BAD_REQUEST)

        new_location = Point(longitude, latitude, srid=4326)
        trip.technician_current_location = new_location

        if reservation.location:
            distance = new_location.distance(reservation.location) * 111
        else:
            distance = 0
        trip.distance_remaining_km = round(distance, 2)
        
        travel_time = int((distance / 40) * 60)
        trip.travel_duration_minutes = travel_time
        trip.estimated_arrival_time = timezone.now() + timedelta(minutes=travel_time)
        
        if not isinstance(trip.location_history, list):
            trip.location_history = []
        trip.location_history.append({
            'lat': latitude,
            'lng': longitude,
            'timestamp': timezone.now().isoformat()
        })
        
        trip.save(update_fields=[
            'technician_current_location',
            'distance_remaining_km',
            'travel_duration_minutes',
            'estimated_arrival_time',
            'location_history',
            'status',
            'arrived_at',
            'updated_at',
        ])
        
        # Arrivée: 5 mètres ou moins (0.005 km)
        if distance <= 0.005 and trip.status != 'arrived':
            trip.status = 'arrived'
            trip.arrived_at = timezone.now()
            trip.save()
            
            reservation.status = 'technician_arrived'
            reservation.save()

            try:
                from apps.users.models import Notification
                from apps.users.services import send_expo_push_to_user
                title = 'Technicien arrivé'
                body = "Votre technicien est arrivé sur place. Vous pouvez échanger via le chat et suivre le démarrage de l'intervention."
                data = {'type': 'technician_arrived', 'reservation_id': reservation.id}
                Notification.objects.create(user=reservation.client.user, title=title, body=body, data=data)
                send_expo_push_to_user(reservation.client.user, title=title, body=body, data=data)
            except Exception:
                pass
        
        return Response(TripTrackingSerializer(trip).data)
    
    @action(detail=True, methods=['get'])
    def track(self, request, pk=None):
        """Récupérer le suivi"""
        reservation = self.get_object()
        
        if not hasattr(reservation, 'trip_tracking'):
            return Response({'error': 'Aucun suivi'}, status=status.HTTP_404_NOT_FOUND)
        
        return Response(TripTrackingSerializer(reservation.trip_tracking).data)
    
    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """Démarrer l'intervention"""
        reservation = self.get_object()

        if request.user.user_type != 'technician':
            return Response({'error': 'Seul un technicien peut démarrer'}, status=status.HTTP_403_FORBIDDEN)

        # Tolérant: on autorise aussi 'technician_dispatched' pour éviter les 400.
        if reservation.status not in ['confirmed', 'technician_dispatched', 'technician_arrived', 'in_progress']:
            return Response({'error': 'Statut invalide'}, status=status.HTTP_400_BAD_REQUEST)
        
        reservation.status = 'in_progress'
        reservation.actual_start_time = timezone.now()
        reservation.save()
        
        WorkProgress.objects.create(
            reservation=reservation,
            status='inspection',
            description="Début de l'intervention"
        )
        
        return Response(ReservationSerializer(reservation).data)
    
    @action(detail=True, methods=['post'])
    def submit_diagnostic(self, request, pk=None):
        """Soumettre le diagnostic"""
        reservation = self.get_object()

        if request.user.user_type != 'technician':
            return Response({'error': 'Seul un technicien peut soumettre'}, status=status.HTTP_403_FORBIDDEN)

        # Si le technicien n'a pas encore "démarré", on passe en in_progress automatiquement.
        if reservation.status in ['confirmed', 'technician_dispatched']:
            reservation.status = 'in_progress'
            reservation.actual_start_time = timezone.now()
            reservation.save(update_fields=['status', 'actual_start_time'])

        if reservation.status not in ['in_progress', 'technician_arrived']:
            return Response({'error': 'Statut invalide'}, status=status.HTTP_400_BAD_REQUEST)

        data = request.data.copy()
        # Le serializer exige le champ reservation
        data['reservation'] = reservation.id

        serializer = DiagnosticCreateSerializer(data=data, context={'request': request})
        
        if serializer.is_valid():
            diagnostic = serializer.save()
            reservation.client_notified_diagnosis = True
            # Statut explicite
            reservation.status = 'diagnosis_submitted'
            reservation.save(update_fields=['client_notified_diagnosis', 'status'])

            # Déclencher une notification de paiement final au client (montant issu du diagnostic)
            try:
                from apps.users.models import Notification
                from apps.users.services import send_expo_push_to_user

                amount = float(diagnostic.estimated_total_cost)
                title = 'Paiement requis'
                body = f"Veuillez régler {int(round(amount))} FCFA pour valider les frais d’intervention."
                data_payload = {
                    'type': 'payment_required',
                    'kind': 'final',
                    'reservation_id': reservation.id,
                    'amount': amount,
                }
                Notification.objects.create(user=reservation.client.user, title=title, body=body, data=data_payload)
                send_expo_push_to_user(reservation.client.user, title=title, body=body, data=data_payload)
            except Exception:
                # Best effort: la notification DB est importante, mais on évite de bloquer la réponse.
                pass
            
            return Response(DiagnosticSerializer(diagnostic).data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def approve_diagnostic(self, request, pk=None):
        """Approuver le diagnostic"""
        reservation = self.get_object()
        
        if not hasattr(reservation, 'diagnostic'):
            return Response({'error': 'Aucun diagnostic'}, status=status.HTTP_404_NOT_FOUND)
        
        if request.user.user_type != 'client':
            return Response({'error': 'Seul le client peut approuver'}, status=status.HTTP_403_FORBIDDEN)
        
        diagnostic = reservation.diagnostic
        approved = request.data.get('approved', False)
        comments = request.data.get('comments', '')
        
        diagnostic.client_approved = approved
        diagnostic.client_approval_date = timezone.now()
        diagnostic.client_comments = comments
        diagnostic.save()
        
        if approved:
            if diagnostic.can_repair_onsite:
                reservation.status = 'in_progress'
            else:
                reservation.status = 'parts_ordered'
                WorkProgress.objects.create(
                    reservation=reservation,
                    status='parts_ordering',
                    description="Commande de pièces en cours"
                )
        else:
            reservation.status = 'cancelled'
            reservation.cancellation_reason = f"Client a refusé: {comments}"
        
        reservation.save()
        
        return Response(DiagnosticSerializer(diagnostic).data)
    
    @action(detail=True, methods=['post'])
    def add_work_progress(self, request, pk=None):
        """Ajouter une mise à jour"""
        reservation = self.get_object()
        
        if request.user.user_type != 'technician':
            return Response({'error': 'Seul le technicien peut ajouter'}, status=status.HTTP_403_FORBIDDEN)
        
        serializer = WorkProgressSerializer(data={'reservation': reservation.id, **request.data})
        
        if serializer.is_valid():
            progress = serializer.save()
            return Response(WorkProgressSerializer(progress).data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Terminer l'intervention"""
        reservation = self.get_object()

        # Tolérant: permettre la clôture après diagnostic soumis/attente validation.
        if reservation.status not in ['in_progress', 'diagnosis_submitted', 'awaiting_client_approval', 'technician_arrived']:
            return Response({'error': 'Statut invalide'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Si un diagnostic a été soumis, on exige un paiement final confirmé avant clôture.
        try:
            from apps.payments.models import PaymentTransaction

            if hasattr(reservation, 'diagnostic'):
                required_amount = reservation.diagnostic.estimated_total_cost
                paid = PaymentTransaction.objects.filter(
                    reservation=reservation,
                    kind='final',
                    status='confirmed'
                ).exists()
                if not paid:
                    return Response({'error': 'Paiement final non confirmé'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            # Si l'app payments n'est pas dispo, on ne bloque pas.
            pass

        price = request.data.get('price')
        notes = request.data.get('notes', '')
        
        if notes:
            reservation.notes += f"\n{notes}"
        
        complete_reservation(reservation, price=price)
        
        if reservation.vehicle:
            reservation.vehicle.last_service_date = timezone.now().date()
            reservation.vehicle.save()

        try:
            from apps.users.models import Notification
            from apps.users.services import send_expo_push_to_user
            title = 'Mission terminée'
            body = "L'intervention est terminée. Vous pouvez maintenant noter le technicien."
            data = {'type': 'mission_completed', 'reservation_id': reservation.id}
            Notification.objects.create(user=reservation.client.user, title=title, body=body, data=data)
            send_expo_push_to_user(reservation.client.user, title=title, body=body, data=data)
        except Exception:
            pass
        
        return Response(ReservationSerializer(reservation).data)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Annuler la réservation"""
        reservation = self.get_object()
        
        if not reservation.can_be_cancelled:
            return Response({'error': 'Impossible d\'annuler'}, status=status.HTTP_400_BAD_REQUEST)
        
        reason = request.data.get('reason', '')
        if reason:
            reservation.notes += f"\nRaison: {reason}"
        
        cancel_reservation(reservation, request.user)
        
        return Response(ReservationSerializer(reservation).data)
    
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def reassign(self, request, pk=None):
        """Réassigner un technicien"""
        reservation = self.get_object()
        
        new_technician = reassign_technician(reservation, force_new=True)
        
        if new_technician:
            return Response(ReservationSerializer(reservation).data)
        
        return Response({'error': 'Aucun technicien disponible'}, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=True, methods=['post'], permission_classes=[CanEvaluate])
    def evaluate(self, request, pk=None):
        """Évaluer la réservation"""
        reservation = self.get_object()
        
        serializer = EvaluationCreateSerializer(data={'reservation': reservation.id, **request.data})
        
        if serializer.is_valid():
            evaluation = serializer.save()
            return Response(EvaluationSerializer(evaluation).data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """Réservations à venir"""
        user = request.user
        now = timezone.now()
        
        if user.user_type == 'client':
            reservations = Reservation.objects.filter(
                client__user=user,
                date__gte=now,
                status__in=['confirmed', 'pending', 'technician_dispatched']
            ).order_by('date')
        elif user.user_type == 'technician':
            reservations = Reservation.objects.filter(
                technician__user=user,
                date__gte=now,
                status__in=['confirmed', 'in_progress', 'technician_dispatched']
            ).order_by('date')
        else:
            reservations = Reservation.objects.none()
        
        return Response(ReservationListSerializer(reservations, many=True).data)
    
    @action(detail=False, methods=['get'])
    def history(self, request):
        """Historique"""
        user = request.user
        
        if user.user_type == 'client':
            reservations = Reservation.objects.filter(
                client__user=user,
                status__in=['completed', 'cancelled']
            ).order_by('-date')
        elif user.user_type == 'technician':
            reservations = Reservation.objects.filter(
                technician__user=user,
                status__in=['completed', 'cancelled']
            ).order_by('-date')
        else:
            reservations = Reservation.objects.none()
        
        return Response(ReservationListSerializer(reservations, many=True).data)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Statistiques"""
        user = request.user
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        if start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
        if end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d')
        
        if user.user_type == 'client':
            stats = get_reservation_stats(client=user.client_profile, start_date=start_date, end_date=end_date)
        elif user.user_type == 'technician':
            stats = get_reservation_stats(technician=user.technician_profile, start_date=start_date, end_date=end_date)
        else:
            stats = get_reservation_stats(start_date=start_date, end_date=end_date)
        
        return Response(ReservationStatsSerializer(stats).data)
    
    @action(detail=False, methods=['post'])
    def suggest_intervention(self, request):
        """Suggérer un type d'intervention"""
        description = request.data.get('description', '').lower()
        symptoms = request.data.get('symptoms', [])
        
        symptom_mapping = {
            'ne_demarre_pas': ['batterie', 'demarreur', 'alternateur'],
            'engine_stopped': ['courroie', 'injection', 'batterie'],
            'strange_noise': ['courroie', 'roulements', 'echappement'],
            'overheating': ['radiateur', 'thermostat', 'liquide_refroidissement'],
            'smoke': ['joints', 'huile_moteur', 'turbo'],
            'brake_issue': ['plaquettes_frein', 'disques', 'liquide_frein'],
            'flat_tire': ['pneu'],
        }
        
        suggestions = []
        for symptom in symptoms:
            if symptom in symptom_mapping:
                for intervention in symptom_mapping[symptom]:
                    if intervention not in [s['type'] for s in suggestions]:
                        suggestions.append({'type': intervention, 'confidence': 0.7})
        
        if not suggestions:
            suggestions = [{'type': 'diagnostic_general', 'confidence': 1.0}]
        
        return Response({
            'suggested_types': suggestions[:3],
            'recommendation': suggestions[0]['type']
        })


class ChatViewSet(viewsets.ViewSet):
    """ViewSet pour le chat"""
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        """Lister toutes les conversations actives de l'utilisateur connecté."""
        user = request.user
        if user.user_type == 'client' and hasattr(user, 'client_profile'):
            conversations = ChatConversation.objects.filter(
                reservation__client=user.client_profile,
                is_active=True,
            ).select_related('reservation__client__user', 'reservation__technician__user').order_by('-created_at')
        elif user.user_type == 'technician' and hasattr(user, 'technician_profile'):
            conversations = ChatConversation.objects.filter(
                reservation__technician=user.technician_profile,
                is_active=True,
            ).select_related('reservation__client__user', 'reservation__technician__user').order_by('-created_at')
        else:
            conversations = ChatConversation.objects.none()

        data = []
        for convo in conversations:
            last_msg = ChatMessage.objects.filter(conversation=convo).order_by('-created_at').first()
            unread = ChatMessage.objects.filter(
                conversation=convo, is_read=False
            ).exclude(sender=user).count()
            data.append({
                'conversation_id': convo.id,
                'reservation_id': convo.reservation_id,
                'is_active': convo.is_active,
                'unread_count': unread,
                'last_message': ChatMessageSerializer(last_msg).data if last_msg else None,
            })
        return Response(data)

    @action(detail=False, methods=['get'], url_path='reservation/(?P<reservation_id>[^/.]+)/messages')
    def messages(self, request, reservation_id=None):
        """Récupérer les messages"""
        try:
            reservation = Reservation.objects.get(id=reservation_id)
        except Reservation.DoesNotExist:
            return Response({'error': 'Réservation non trouvée'}, status=status.HTTP_404_NOT_FOUND)
        
        user = request.user
        if user.user_type == 'client' and reservation.client.user != user:
            return Response({'error': 'Non autorisé'}, status=status.HTTP_403_FORBIDDEN)
        elif user.user_type == 'technician' and reservation.technician.user != user:
            return Response({'error': 'Non autorisé'}, status=status.HTTP_403_FORBIDDEN)
        
        conversation, _ = ChatConversation.objects.get_or_create(reservation=reservation)
        
        messages = ChatMessage.objects.filter(conversation=conversation).order_by('created_at')
        messages.filter(is_read=False).exclude(sender=user).update(is_read=True, read_at=timezone.now())
        
        return Response(ChatMessageSerializer(messages, many=True).data)
    
    @action(detail=False, methods=['post'], url_path='reservation/(?P<reservation_id>[^/.]+)/send')
    def send_message(self, request, reservation_id=None):
        """Envoyer un message"""
        try:
            reservation = Reservation.objects.get(id=reservation_id)
        except Reservation.DoesNotExist:
            return Response({'error': 'Réservation non trouvée'}, status=status.HTTP_404_NOT_FOUND)
        
        conversation, _ = ChatConversation.objects.get_or_create(reservation=reservation)

        message_type = request.data.get('message_type', 'text')
        payload = {
            'conversation': conversation,
            'sender': request.user,
            'message_type': message_type,
            'content': request.data.get('content', ''),
            'attachment_url': request.data.get('attachment_url', '')
        }

        # Support "location": stocker réellement les coordonnées
        # Body attendu: { message_type: 'location', latitude: <float>, longitude: <float>, content?: string }
        if message_type == 'location':
            try:
                lat = request.data.get('latitude', None)
                lon = request.data.get('longitude', None)
                if lat is not None and lon is not None:
                    lat = float(lat)
                    lon = float(lon)
                    payload['location'] = Point(lon, lat, srid=4326)
            except (TypeError, ValueError):
                # On ne bloque pas l'envoi du message; les champs latitude/longitude resteront null.
                pass

        message = ChatMessage.objects.create(**payload)

        # ------------------------------
        # Notification "Message reçu" (client <-> technicien)
        # Objectif: que le technicien voie immédiatement le message dans l’onglet Notifications
        # (et le client aussi si le technicien répond)
        # ------------------------------
        try:
            from apps.users.models import Notification
            from apps.users.services import send_expo_push_to_user

            sender = request.user
            recipient = None
            if sender.user_type == 'client' and reservation.technician:
                recipient = reservation.technician.user
            elif sender.user_type == 'technician':
                recipient = reservation.client.user

            if recipient:
                preview = (payload.get('content') or '').strip()
                if message_type == 'location':
                    preview = '📍 Position partagée'
                if not preview:
                    preview = 'Nouveau message'

                title = 'Nouveau message'
                body = preview[:120]
                data = {
                    'type': 'chat_message',
                    'reservation_id': reservation.id,
                    'message_id': message.id,
                }
                Notification.objects.create(user=recipient, title=title, body=body, data=data)
                # best effort push
                try:
                    send_expo_push_to_user(recipient, title=title, body=body, data=data)
                except Exception:
                    pass
        except Exception:
            pass
        
        return Response(ChatMessageSerializer(message).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], url_path='unread_count')
    def unread_count(self, request):
        """Retourne le nombre total de messages non lus pour l'utilisateur courant.

        L'app mobile s'en sert pour afficher un badge sur l'onglet *Messages*.
        """
        user = request.user

        qs = ChatMessage.objects.filter(is_read=False).exclude(sender=user)

        if user.user_type == 'client' and hasattr(user, 'client_profile'):
            qs = qs.filter(conversation__reservation__client=user.client_profile)
        elif user.user_type == 'technician' and hasattr(user, 'technician_profile'):
            qs = qs.filter(conversation__reservation__technician=user.technician_profile)
        else:
            qs = qs.none()

        return Response({'unread_messages': qs.count()})


class TechnicianAvailabilityViewSet(viewsets.ModelViewSet):
    """ViewSet pour les disponibilités"""
    queryset = TechnicianAvailability.objects.all()
    serializer_class = TechnicianAvailabilitySerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        queryset = TechnicianAvailability.objects.all()
        
        if user.user_type == 'technician':
            queryset = queryset.filter(technician__user=user)
        
        tech_id = self.request.query_params.get('technician_id')
        if tech_id:
            queryset = queryset.filter(technician_id=tech_id)
        
        date = self.request.query_params.get('date')
        if date:
            queryset = queryset.filter(date=date)
        
        only_available = self.request.query_params.get('available_only', 'false')
        if only_available.lower() == 'true':
            queryset = queryset.filter(is_available=True)
        
        return queryset.order_by('date', 'start_time')
    
    def perform_create(self, serializer):
        user = self.request.user
        if user.user_type == 'technician':
            serializer.save(technician=user.technician_profile)
        else:
            serializer.save()
    
    @action(detail=False, methods=['get'])
    def available_slots(self, request):
        """Créneaux disponibles"""
        tech_id = request.query_params.get('technician_id')
        date = request.query_params.get('date')
        
        if not tech_id or not date:
            return Response({'error': 'technician_id et date requis'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            target_date = datetime.strptime(date, '%Y-%m-%d').date()
        except ValueError:
            return Response({'error': 'Format invalide'}, status=status.HTTP_400_BAD_REQUEST)
        
        slots = TechnicianAvailability.objects.filter(
            technician_id=tech_id,
            date=target_date,
            is_available=True
        ).order_by('start_time')
        
        reservations = Reservation.objects.filter(
            technician_id=tech_id,
            date__date=target_date,
            status__in=['confirmed', 'in_progress', 'technician_dispatched']
        )
        
        available_slots = []
        for slot in slots:
            slot_start = datetime.combine(target_date, slot.start_time)
            slot_end = datetime.combine(target_date, slot.end_time)
            
            bookings_count = reservations.filter(date__range=(slot_start, slot_end)).count()
            
            if bookings_count < slot.max_bookings:
                available_slots.append({
                    'id': slot.id,
                    'date': slot.date,
                    'start_time': slot.start_time,
                    'end_time': slot.end_time,
                    'remaining_spots': slot.max_bookings - bookings_count
                })
        
        return Response(available_slots)


class EvaluationViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet pour les évaluations"""
    queryset = Evaluation.objects.select_related('client__user', 'technician__user', 'reservation')
    serializer_class = EvaluationSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        queryset = Evaluation.objects.select_related('client__user', 'technician__user', 'reservation')
        
        if user.user_type == 'client':
            queryset = queryset.filter(client__user=user)
        elif user.user_type == 'technician':
            queryset = queryset.filter(technician__user=user)
        elif user.user_type != 'administrator':
            queryset = queryset.none()
        
        technician_id = self.request.query_params.get('technician')
        if technician_id:
            queryset = queryset.filter(technician_id=technician_id)
        
        min_rating = self.request.query_params.get('min_rating')
        if min_rating:
            queryset = queryset.filter(note__gte=int(min_rating))
        
        return queryset.order_by('-created_at')
    
    @action(detail=False, methods=['get'])
    def technician_ratings(self, request):
        """Moyennes par technicien"""
        from django.db.models import Avg, Count
        
        technician_id = request.query_params.get('technician_id')
        
        if not technician_id:
            return Response({'error': 'technician_id requis'}, status=status.HTTP_400_BAD_REQUEST)
        
        ratings = Evaluation.objects.filter(technician_id=technician_id).aggregate(
            avg_rating=Avg('note'),
            avg_response_time=Avg('response_time_rating'),
            avg_diagnosis_quality=Avg('diagnosis_quality_rating'),
            avg_communication=Avg('communication_rating'),
            avg_professionalism=Avg('professionalism'),
            avg_value_for_money=Avg('value_for_money'),
            total_reviews=Count('id')
        )
        
        distribution = {
            '5_stars': Evaluation.objects.filter(technician_id=technician_id, note=5).count(),
            '4_stars': Evaluation.objects.filter(technician_id=technician_id, note=4).count(),
            '3_stars': Evaluation.objects.filter(technician_id=technician_id, note=3).count(),
            '2_stars': Evaluation.objects.filter(technician_id=technician_id, note=2).count(),
            '1_star': Evaluation.objects.filter(technician_id=technician_id, note=1).count(),
        }
        
        ratings['distribution'] = distribution
        
        return Response(ratings)
    
    @action(detail=False, methods=['get'])
    def recent(self, request):
        """Dernières évaluations"""
        limit = int(request.query_params.get('limit', 10))
        
        evaluations = Evaluation.objects.select_related(
            'client__user', 'technician__user'
        ).order_by('-created_at')[:limit]
        
        return Response(EvaluationSerializer(evaluations, many=True).data)