import logging
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.contrib.gis.db.models.functions import Distance
from django.db.models import Avg

from django.utils import timezone

from apps.users.models import Client, Technician, Vendor, Administrator, PushToken, Notification
from apps.users.serializers import (
    UserSerializer,
    UserRegistrationSerializer,
    TechnicianRegisterSerializer,
    UserUpdateSerializer,
    ChangePasswordSerializer,
    UpdateLocationSerializer,
    ClientSerializer,
    TechnicianSerializer,
    TechnicianListSerializer,
    TechnicianUpdateSerializer,
    VendorSerializer,
    VendorUpdateSerializer,
    AdministratorSerializer,
    UserProfileDetailSerializer,
    CustomTokenObtainPairSerializer,
    PushTokenSerializer,
    NotificationSerializer,
)
from apps.users.permissions import IsOwnerOrAdmin, IsAdministrator
from apps.users.throttles import AuthRateThrottle, RegisterRateThrottle, LocationUpdateThrottle

User = get_user_model()
logger = logging.getLogger('apps.users.views')


# ==================== JWT TOKEN VIEW ====================

class CustomTokenObtainPairView(TokenObtainPairView):
    """Vue personnalisée pour obtenir les tokens JWT avec infos utilisateur"""
    serializer_class = CustomTokenObtainPairSerializer
    throttle_classes = [AuthRateThrottle]


# ==================== USER VIEWSET ====================

class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des utilisateurs
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or getattr(user, "user_type", None) == 'administrator':
            return User.objects.all()
        return User.objects.filter(id=user.id)

    def get_serializer_class(self):
        if self.action in ['update', 'partial_update']:
            return UserUpdateSerializer
        elif self.action in ['me', 'retrieve']:
            return UserProfileDetailSerializer
        return UserSerializer

    def get_permissions(self):
        if self.action in ['list', 'destroy']:
            return [IsAdministrator()]
        elif self.action in ['update', 'partial_update']:
            return [IsOwnerOrAdmin()]
        elif self.action == 'register':
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(
        detail=False,
        methods=['post'],
        permission_classes=[permissions.AllowAny],
        throttle_classes=[RegisterRateThrottle],
        parser_classes=[MultiPartParser, FormParser, JSONParser],
    )
    def register(self, request):
        """
        POST /api/users/register/

        ✅ CLIENT (JSON):
        {
          "username": "...",
          "email": "...",
          "password": "...",
          "password_confirm": "...",
          "first_name": "...",
          "last_name": "...",
          "telephone": "+237...",
          "user_type": "client"
        }

        ✅ TECHNICIAN (multipart/form-data recommandé):
        - user_type="technician"
        - username, email, password, password_confirm, first_name, last_name, telephone
        - address
        - specialties (string ex: "mecanique, electronique")
        - documents (1..n fichiers) : clé "documents" répétée
        """
        user_type = (request.data.get('user_type') or '').strip().lower()

        if not user_type:
            return Response(
                {"user_type": ["Ce champ est obligatoire."]},
                status=status.HTTP_400_BAD_REQUEST
            )

        # -------------------------
        # ✅ CLIENT => JSON normal
        # -------------------------
        if user_type == 'client':
            serializer = UserRegistrationSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            user = serializer.save()
            return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)

        # ------------------------------
        # ✅ TECHNICIAN => multipart+docs
        # ------------------------------
        if user_type == 'technician':
            # ⚠️ Si tu veux rendre documents obligatoires :
            # docs = request.FILES.getlist('documents')
            # if not docs:
            #     return Response(
            #         {"documents": ["Veuillez ajouter au moins un document."]},
            #         status=status.HTTP_400_BAD_REQUEST
            #     )

            serializer = TechnicianRegisterSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            tech = serializer.save()   # retourne un Technician
            return Response(TechnicianSerializer(tech).data, status=status.HTTP_201_CREATED)

        # ------------------------------------------
        # ❌ On refuse vendor/administrator ici
        # ------------------------------------------
        return Response(
            {"user_type": ["user_type invalide. Choix autorisés: client, technician"]},
            status=status.HTTP_400_BAD_REQUEST
        )

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def change_password(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        user = request.user
        user.set_password(serializer.validated_data['new_password'])
        user.save()

        return Response({'message': 'Mot de passe changé avec succès', 'status': 'success'})

    @action(
        detail=False,
        methods=['post'],
        permission_classes=[permissions.IsAuthenticated],
        throttle_classes=[LocationUpdateThrottle],
    )
    def update_location(self, request):
        serializer = UpdateLocationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        latitude = serializer.validated_data['latitude']
        longitude = serializer.validated_data['longitude']

        user = request.user
        user.location = Point(longitude, latitude, srid=4326)
        user.save(update_fields=['location'])

        # Si technicien : mettre à jour le TripTracking de la réservation active
        # et broadcaster la position aux clients WebSocket abonnés.
        if getattr(user, 'user_type', None) == 'technician' and hasattr(user, 'technician_profile'):
            try:
                from apps.reservations.models import Reservation, TripTracking
                from asgiref.sync import async_to_sync
                from channels.layers import get_channel_layer

                tech = user.technician_profile
                active = Reservation.objects.filter(
                    technician=tech,
                    status__in=['confirmed', 'technician_dispatched', 'in_progress']
                ).order_by('-updated_at').first()

                if active:
                    trip, _ = TripTracking.objects.get_or_create(reservation=active)
                    trip.technician_current_location = Point(longitude, latitude, srid=4326)
                    try:
                        hist = trip.location_history or []
                        hist.append({
                            'lat': latitude,
                            'lon': longitude,
                            'ts': timezone.now().isoformat(),
                        })
                        trip.location_history = hist[-200:]
                    except Exception:
                        logger.warning(
                            'Échec append location_history pour trip=%s', trip.pk, exc_info=True
                        )
                    trip.save()

                    # Broadcast WebSocket → groupe trip_{reservation_id}
                    channel_layer = get_channel_layer()
                    if channel_layer is not None:
                        async_to_sync(channel_layer.group_send)(
                            f'trip_{active.pk}',
                            {
                                'type': 'trip.location.update',
                                'reservation_id': active.pk,
                                'latitude': latitude,
                                'longitude': longitude,
                                'timestamp': timezone.now().isoformat(),
                                'technician_id': user.pk,
                            }
                        )
            except Exception:
                logger.exception('Erreur broadcast localisation pour user=%s', user.pk)

        return Response({
            'message': 'Localisation mise à jour',
            'location': {'latitude': latitude, 'longitude': longitude}
        })

    # ==================== PUSH / NOTIFICATIONS ====================

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated], url_path='push-token')
    def push_token(self, request):
        """Enregistrer / mettre à jour un Expo push token pour l'utilisateur courant."""
        serializer = PushTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        token = serializer.validated_data['token']
        platform = serializer.validated_data.get('platform', 'unknown')

        obj, _ = PushToken.objects.update_or_create(
            token=token,
            defaults={'user': request.user, 'platform': platform},
        )
        return Response({'status': 'ok', 'token': obj.token, 'platform': obj.platform})

    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated], url_path='notifications')
    def notifications(self, request):
        """Lister les notifications de l'utilisateur courant.

        Params:
        - unread_only=true|false
        - limit=50
        """
        unread_only = (request.query_params.get('unread_only', 'false') or 'false').lower() == 'true'
        limit = int(request.query_params.get('limit', '50') or 50)
        limit = max(1, min(limit, 200))

        qs = Notification.objects.filter(user=request.user)
        if unread_only:
            qs = qs.filter(read_at__isnull=True)
        qs = qs.order_by('-created_at')[:limit]

        return Response(NotificationSerializer(qs, many=True).data)

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated], url_path='notifications/(?P<notif_id>[^/.]+)/read')
    def mark_notification_read(self, request, notif_id=None):
        """Marquer une notification comme lue."""
        try:
            notif = Notification.objects.get(id=notif_id, user=request.user)
        except Notification.DoesNotExist:
            return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

        if notif.read_at is None:
            notif.read_at = timezone.now()
            notif.save(update_fields=['read_at'])
        return Response({'status': 'ok', 'id': notif.id, 'read_at': notif.read_at})

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated], url_path='notifications/mark-all-read')
    def mark_all_notifications_read(self, request):
        """Marquer toutes les notifications comme lues."""
        Notification.objects.filter(user=request.user, read_at__isnull=True).update(read_at=timezone.now())
        return Response({'status': 'ok'})

    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated], url_path='notifications/unread-count')
    def notifications_unread_count(self, request):
        """Retourne le nombre de notifications non lues (pour badge UI)."""
        c = Notification.objects.filter(user=request.user, read_at__isnull=True).count()
        return Response({'unread_notifications': c})

    @action(detail=False, methods=['delete'], permission_classes=[permissions.IsAuthenticated], url_path='notifications/(?P<notif_id>[^/.]+)')
    def delete_notification(self, request, notif_id=None):
        """Supprimer une notification (effaçable individuellement)."""
        deleted, _ = Notification.objects.filter(user=request.user, id=notif_id).delete()
        if deleted == 0:
            return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'status': 'ok', 'deleted': 1})

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated], url_path='notifications/clear')
    def clear_notifications(self, request):
        """Supprimer toutes les notifications de l'utilisateur."""
        Notification.objects.filter(user=request.user).delete()
        return Response({'status': 'ok'})

    @action(detail=True, methods=['post'], permission_classes=[IsAdministrator])
    def toggle_availability(self, request, pk=None):
        user = self.get_object()
        user.is_available = not user.is_available
        user.save()

        return Response({
            'message': f"Utilisateur {'activé' if user.is_available else 'désactivé'}",
            'is_available': user.is_available
        })


# ==================== CLIENT VIEWSET ====================

class ClientViewSet(viewsets.ModelViewSet):
    queryset = Client.objects.select_related('user').prefetch_related('vehicules')
    serializer_class = ClientSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if getattr(user, "user_type", None) == 'administrator':
            return Client.objects.all()
        elif getattr(user, "user_type", None) == 'client':
            return Client.objects.filter(user=user)
        return Client.objects.none()

    @action(detail=True, methods=['get'])
    def reservations(self, request, pk=None):
        client = self.get_object()
        from apps.reservations.serializers import ReservationSerializer
        reservations = client.reservations.all()
        serializer = ReservationSerializer(reservations, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def commandes(self, request, pk=None):
        client = self.get_object()
        from apps.marketplace.serializers import CommandeSerializer
        commandes = client.commandes.all()
        serializer = CommandeSerializer(commandes, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def vehicules(self, request, pk=None):
        client = self.get_object()
        from apps.vehicles.serializers import VehicleSerializer
        vehicules = client.vehicules.all()
        serializer = VehicleSerializer(vehicules, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        client = self.get_object()
        stats = {
            'total_reservations': client.reservations.count(),
            'reservations_completed': client.reservations.filter(status='completed').count(),
            'reservations_cancelled': client.reservations.filter(status='cancelled').count(),
            'total_commandes': client.commandes.count(),
            'total_vehicules': client.vehicules.count(),
        }
        return Response(stats)


# ==================== TECHNICIAN VIEWSET ====================

class TechnicianViewSet(viewsets.ModelViewSet):
    queryset = Technician.objects.select_related('user')
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'list':
            return TechnicianListSerializer
        elif self.action in ['update', 'partial_update']:
            return TechnicianUpdateSerializer
        return TechnicianSerializer

    def get_queryset(self):
        queryset = Technician.objects.select_related('user')

        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        specialization = self.request.query_params.get('specialization')
        if specialization:
            queryset = queryset.filter(specializations__contains=[specialization])

        available = self.request.query_params.get('available')
        if available == 'true':
            queryset = queryset.filter(user__is_available=True, status='available')

        return queryset

    @action(detail=False, methods=['get'])
    def nearest(self, request):
        latitude = request.query_params.get('latitude')
        longitude = request.query_params.get('longitude')
        radius = float(request.query_params.get('radius', 10))
        specialization = request.query_params.get('specialization')

        if not latitude or not longitude:
            return Response({'error': 'Latitude et longitude requises'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            latitude = float(latitude)
            longitude = float(longitude)
        except ValueError:
            return Response({'error': 'Latitude et longitude invalides'}, status=status.HTTP_400_BAD_REQUEST)

        user_location = Point(longitude, latitude, srid=4326)

        queryset = Technician.objects.filter(
            user__location__isnull=False,
            user__is_available=True,
            status='available'
        ).annotate(
            distance=Distance('user__location', user_location)
        ).filter(
            distance__lte=D(km=radius)
        )

        if specialization:
            queryset = queryset.filter(specializations__contains=[specialization])

        queryset = queryset.order_by('distance', '-rating')[:10]

        serializer = TechnicianListSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['patch'])
    def update_status(self, request, pk=None):
        technician = self.get_object()

        if request.user != technician.user and getattr(request.user, "user_type", None) != 'administrator':
            return Response({'error': 'Non autorisé'}, status=status.HTTP_403_FORBIDDEN)

        new_status = request.data.get('status')
        valid_statuses = [choice[0] for choice in Technician.STATUS_CHOICES]

        if new_status not in valid_statuses:
            return Response(
                {'error': f'Statut invalide. Choix: {", ".join(valid_statuses)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        technician.status = new_status
        technician.save()

        return Response({'message': 'Statut mis à jour', 'status': new_status})

    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        technician = self.get_object()

        from apps.reservations.models import Reservation, Evaluation

        reservations = Reservation.objects.filter(technician=technician)
        evaluations = Evaluation.objects.filter(technician=technician)

        stats = {
            'total_interventions': technician.total_interventions,
            'rating': float(technician.rating),
            'completed': reservations.filter(status='completed').count(),
            'in_progress': reservations.filter(status='in_progress').count(),
            'cancelled': reservations.filter(status='cancelled').count(),
            'specializations': technician.specializations,
            'certifications': technician.certifications,
            'total_evaluations': evaluations.count(),
            'evaluations_breakdown': {
                '5_stars': evaluations.filter(note=5).count(),
                '4_stars': evaluations.filter(note=4).count(),
                '3_stars': evaluations.filter(note=3).count(),
                '2_stars': evaluations.filter(note=2).count(),
                '1_star': evaluations.filter(note=1).count(),
            }
        }
        return Response(stats)


# ==================== VENDOR VIEWSET ====================

class VendorViewSet(viewsets.ModelViewSet):
    queryset = Vendor.objects.select_related('user')
    serializer_class = VendorSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ['update', 'partial_update']:
            return VendorUpdateSerializer
        return VendorSerializer

    def get_queryset(self):
        user = self.request.user
        if getattr(user, "user_type", None) == 'administrator':
            return Vendor.objects.all()
        elif getattr(user, "user_type", None) == 'vendor':
            return Vendor.objects.filter(user=user)
        return Vendor.objects.filter(is_verified=True)

    @action(detail=True, methods=['get'])
    def produits(self, request, pk=None):
        vendor = self.get_object()
        from apps.marketplace.serializers import ProduitSerializer
        produits = vendor.user.produits.all()
        serializer = ProduitSerializer(produits, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[IsAdministrator])
    def verify(self, request, pk=None):
        vendor = self.get_object()
        vendor.is_verified = True
        vendor.save()
        return Response({'message': 'Vendeur vérifié', 'is_verified': True})


# ==================== ADMINISTRATOR VIEWSET ====================

class AdministratorViewSet(viewsets.ModelViewSet):
    queryset = Administrator.objects.select_related('user')
    serializer_class = AdministratorSerializer
    permission_classes = [IsAdministrator]

    @action(detail=False, methods=['get'])
    def dashboard_stats(self, request):
        from apps.reservations.models import Reservation
        from apps.marketplace.models import Commande
        from django.db.models import Sum
        from datetime import timedelta
        from django.utils import timezone

        today = timezone.now().date()
        last_30_days = today - timedelta(days=30)

        stats = {
            'users': {
                'total': User.objects.count(),
                'clients': Client.objects.count(),
                'technicians': Technician.objects.count(),
                'vendors': Vendor.objects.count(),
                'administrators': Administrator.objects.count(),
                'new_this_month': User.objects.filter(date_joined__gte=last_30_days).count(),
            },
            'reservations': {
                'total': Reservation.objects.count(),
                'pending': Reservation.objects.filter(status='pending').count(),
                'in_progress': Reservation.objects.filter(status='in_progress').count(),
                'completed': Reservation.objects.filter(status='completed').count(),
                'cancelled': Reservation.objects.filter(status='cancelled').count(),
                'this_month': Reservation.objects.filter(created_at__gte=last_30_days).count(),
            },
            'marketplace': {
                'total_orders': Commande.objects.count(),
                'pending_orders': Commande.objects.filter(status='pending').count(),
                'revenue': float(Commande.objects.filter(status='delivered').aggregate(Sum('prix_total'))['prix_total__sum'] or 0),
            },
            'technicians_performance': {
                'avg_rating': float(Technician.objects.aggregate(Avg('rating'))['rating__avg'] or 0),
                'available': Technician.objects.filter(status='available').count(),
                'busy': Technician.objects.filter(status='busy').count(),
                'offline': Technician.objects.filter(status='offline').count(),
            }
        }
        return Response(stats)
