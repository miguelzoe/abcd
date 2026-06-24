from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.contrib.gis.db.models.functions import Distance
from django.db.models import Q,  Avg
from django.core.mail import send_mail
from django.http import HttpResponse

from django.utils import timezone
from datetime import timedelta, datetime
from django.utils.encoding import force_bytes, force_str, DjangoUnicodeDecodeError
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode

from apps.users.models import Client, Technician, Vendor, Administrator, TechnicianDocument, PushToken, Notification
from apps.users.serializers import (
    UserSerializer,
    UserRegistrationSerializer,
    TechnicianRegisterSerializer,
    UserUpdateSerializer,
    ChangePasswordSerializer,
    ForgotPasswordSerializer,
    ResetPasswordSerializer,
    UpdateLocationSerializer,
    ClientSerializer,
    TechnicianSerializer,
    TechnicianDocumentSerializer,
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
from apps.users.throttles import AuthRateThrottle, RegisterRateThrottle

User = get_user_model()


# ==================== JWT TOKEN VIEW ====================

class CustomTokenObtainPairView(TokenObtainPairView):
    """Vue personnalisée pour obtenir les tokens JWT avec infos utilisateur"""
    serializer_class = CustomTokenObtainPairSerializer
    throttle_classes = [AuthRateThrottle]

    def post(self, request, *args, **kwargs):
        try:
            return super().post(request, *args, **kwargs)
        except ValidationError as e:
            # Gérer les erreurs spécifiques de statut de technicien
            error_detail = str(e.detail.get('detail', [''])[0]) if hasattr(e, 'detail') and e.detail else str(e)
            
            if "bloqué" in error_detail.lower():
                return Response(
                    {'detail': error_detail, 'code': 'account_blocked'},
                    status=status.HTTP_423_LOCKED  # 423 Locked
                )
            elif "attente" in error_detail.lower():
                return Response(
                    {'detail': error_detail, 'code': 'approval_pending'},
                    status=status.HTTP_403_FORBIDDEN
                )
            elif "refusée" in error_detail.lower():
                return Response(
                    {'detail': error_detail, 'code': 'approval_rejected'},
                    status=status.HTTP_403_FORBIDDEN
                )
            else:
                # Pour les autres erreurs de validation, garder 400
                return Response(
                    {'detail': error_detail},
                    status=status.HTTP_400_BAD_REQUEST
                )


# ==================== COOKIE-BASED JWT VIEWS ====================

def _cookie_secure():
    """True en prod (HTTPS requis), False en dev."""
    return not settings.DEBUG


def _set_auth_cookies(response, access: str, refresh: str | None = None):
    """Pose les cookies HttpOnly sur la réponse."""
    secure = _cookie_secure()
    response.set_cookie(
        'access_token',
        access,
        max_age=int(settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'].total_seconds()),
        httponly=True,
        secure=secure,
        samesite=getattr(settings, 'AUTH_COOKIE_SAMESITE', 'Lax'),
        path='/',
    )
    if refresh is not None:
        response.set_cookie(
            'refresh_token',
            refresh,
            max_age=int(settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'].total_seconds()),
            httponly=True,
            secure=secure,
            samesite=getattr(settings, 'AUTH_COOKIE_SAMESITE', 'Lax'),
            path='/',
        )


class CookieTokenObtainPairView(CustomTokenObtainPairView):
    """
    POST /api/token/
    Login : retourne les tokens dans le body ET les pose en cookies HttpOnly.
    Les clients navigateur utilisent les cookies ; les clients mobiles lisent le body.
    """

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            _set_auth_cookies(
                response,
                access=response.data['access'],
                refresh=response.data['refresh'],
            )
        return response


class CookieTokenRefreshView(APIView):
    """
    POST /api/token/refresh/
    Refresh : lit le refresh_token depuis le cookie (ou le body en fallback),
    pose un nouveau access_token en cookie et retourne les tokens dans le body.
    """
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AuthRateThrottle]

    def post(self, request):
        refresh_token = request.COOKIES.get('refresh_token') or request.data.get('refresh')
        if not refresh_token:
            return Response(
                {'detail': 'Refresh token manquant.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        serializer = TokenRefreshSerializer(data={'refresh': refresh_token})
        try:
            serializer.is_valid(raise_exception=True)
        except (TokenError, InvalidToken) as e:
            return Response({'detail': str(e)}, status=status.HTTP_401_UNAUTHORIZED)

        response = Response(serializer.validated_data)
        # Nouveau access_token obligatoire ; nouveau refresh_token si rotation activée
        _set_auth_cookies(
            response,
            access=serializer.validated_data['access'],
            refresh=serializer.validated_data.get('refresh'),
        )
        return response


class CookieTokenBlacklistView(APIView):
    """
    POST /api/token/blacklist/
    Logout : blackliste le refresh token et supprime les deux cookies.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        refresh_token = request.COOKIES.get('refresh_token') or request.data.get('refresh')
        if refresh_token:
            try:
                RefreshToken(refresh_token).blacklist()
            except TokenError:
                pass  # Déjà blacklisté ou invalide — on supprime quand même les cookies

        response = Response({'detail': 'Déconnexion réussie.'})
        response.delete_cookie('access_token', path='/')
        response.delete_cookie('refresh_token', path='/')
        return response


class ForgotPasswordView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AuthRateThrottle]

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        login_value = serializer.validated_data['identifier'].strip()

        user = User.objects.filter(email__iexact=login_value).first()
        if not user:
            user = User.objects.filter(username__iexact=login_value).first()
        if not user:
            user = User.objects.filter(telephone=login_value).first()

        response_message = {
            'message': "Si un compte correspond à cet identifiant, un lien de réinitialisation a été préparé.",
            'status': 'accepted',
        }
        if not user or not user.email:
            return Response(response_message, status=status.HTTP_200_OK)

        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        combined_token = f"{uidb64}:{token}"
        frontend_base = (getattr(settings, 'FRONTEND_URL', '') or '').rstrip('/')
        if not frontend_base:
            frontend_base = 'https://efgh-3h6w.vercel.app'
        reset_url = f"{frontend_base}/auth/reinitialiser-mot-de-passe/{combined_token}"

        subject = 'Réinitialisation de votre mot de passe Cartronic'
        message = (
            "Bonjour,\n\n"
            "Vous avez demandé à réinitialiser votre mot de passe sur Cartronic.\n"
            "Cliquez sur le lien suivant ou copiez-le dans votre navigateur :\n\n"
            f"{reset_url}\n\n"
            "Si vous n'êtes pas à l'origine de cette demande, vous pouvez ignorer cet email.\n\n"
            "Cordialement,\n"
            "L'équipe Cartronic"
        )

        email_backend = getattr(settings, 'EMAIL_BACKEND', '')
        smtp_configured = bool(getattr(settings, 'EMAIL_HOST_USER', '')) and bool(getattr(settings, 'EMAIL_HOST_PASSWORD', ''))
        expose_link = getattr(settings, 'PASSWORD_RESET_EXPOSE_LINK', True)

        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
                recipient_list=[user.email],
                fail_silently=False,
            )
            payload = {
                **response_message,
                'delivery': 'email_sent',
                'channel': 'email',
            }
            if expose_link and ('console' in email_backend.lower() or not smtp_configured):
                payload['reset_url'] = reset_url
                payload['delivery'] = 'link_returned'
                payload['channel'] = 'response'
                payload['diagnostic'] = 'SMTP non configuré sur le backend déployé. Utilisez le lien ci-dessous ou configurez EMAIL_HOST_USER / EMAIL_HOST_PASSWORD.'
            return Response(payload, status=status.HTTP_200_OK)
        except Exception as exc:
            payload = {
                **response_message,
                'delivery': 'link_returned' if expose_link else 'email_failed',
                'channel': 'response' if expose_link else 'email',
                'diagnostic': str(exc),
            }
            if expose_link:
                payload['reset_url'] = reset_url
            return Response(payload, status=status.HTTP_200_OK)


class ResetPasswordView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AuthRateThrottle]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token_str = serializer.validated_data['token']

        try:
            uidb64, token = token_str.split(':', 1)
        except ValueError:
            return Response({'message': "Ce lien de réinitialisation est invalide ou a expiré."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (User.DoesNotExist, DjangoUnicodeDecodeError, TypeError, ValueError):
            return Response({'message': "Ce lien de réinitialisation est invalide ou a expiré."}, status=status.HTTP_400_BAD_REQUEST)

        if not default_token_generator.check_token(user, token):
            return Response({'message': "Ce lien de réinitialisation est invalide ou a expiré."}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(serializer.validated_data['new_password'])
        if hasattr(user, 'password_changed_at'):
            user.password_changed_at = timezone.now()
            user.password_expiry_notified_at = None
            user.save(update_fields=['password', 'password_changed_at', 'password_expiry_notified_at'])
        else:
            user.save(update_fields=['password'])

        return Response({'message': 'Mot de passe réinitialisé avec succès', 'status': 'success'})


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

    @action(detail=True, methods=['get'], permission_classes=[permissions.AllowAny], url_path='profile_photo')
    def profile_photo(self, request, pk=None):
        """Servir la photo de profil depuis PostgreSQL, visible par tout utilisateur authentifié."""
        target = User.objects.filter(pk=pk).first()
        if not target or not getattr(target, 'profile_photo_data', None):
            return Response({'detail': 'Photo de profil introuvable'}, status=status.HTTP_404_NOT_FOUND)
        content_type = target.profile_photo_content_type or 'image/jpeg'
        response = HttpResponse(bytes(target.profile_photo_data), content_type=content_type)
        filename = target.profile_photo_filename or f'profile-{target.pk}.jpg'
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response

    @action(
        detail=False,
        methods=['post'],
        permission_classes=[permissions.IsAuthenticated],
        parser_classes=[MultiPartParser, FormParser],
        url_path='upload_profile_photo',
    )
    def upload_profile_photo(self, request):
        """Enregistre la photo de profil du client/technicien en base de données."""
        uploaded = (
            request.FILES.get('profile_photo') or
            request.FILES.get('photo') or
            request.FILES.get('image') or
            request.FILES.get('file')
        )
        if not uploaded:
            return Response({'profile_photo': ['Aucun fichier image reçu.']}, status=status.HTTP_400_BAD_REQUEST)

        content_type = getattr(uploaded, 'content_type', '') or 'image/jpeg'
        if not content_type.startswith('image/'):
            return Response({'profile_photo': ['Le fichier doit être une image.']}, status=status.HTTP_400_BAD_REQUEST)

        data = uploaded.read()
        if len(data) > 5 * 1024 * 1024:
            return Response({'profile_photo': ['La photo ne doit pas dépasser 5 Mo.']}, status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        user.profile_photo_data = data
        user.profile_photo_content_type = content_type
        user.profile_photo_filename = getattr(uploaded, 'name', '') or f'profile-{user.pk}.jpg'
        user.save(update_fields=['profile_photo_data', 'profile_photo_content_type', 'profile_photo_filename', 'updated_at'])

        return Response(UserProfileDetailSerializer(user, context={'request': request}).data)

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

            serializer = TechnicianRegisterSerializer(data=request.data, context={'request': request})
            serializer.is_valid(raise_exception=True)
            tech = serializer.save()   # retourne un Technician
            return Response({
                'message': "Votre demande d’inscription technicien a été envoyée avec succès. L’administrateur va vérifier vos documents avant d’activer votre compte.",
                'approval_status': tech.approval_status,
                'technician': TechnicianSerializer(tech, context={'request': request}).data,
            }, status=status.HTTP_201_CREATED)

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

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def update_location(self, request):
        serializer = UpdateLocationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        latitude = serializer.validated_data['latitude']
        longitude = serializer.validated_data['longitude']

        user = request.user
        user.location = Point(longitude, latitude, srid=4326)
        user.save()

        # Si technicien: pousser aussi la localisation dans TripTracking de la réservation active
        try:
            if getattr(user, 'user_type', None) == 'technician' and hasattr(user, 'technician_profile'):
                from apps.reservations.models import Reservation, TripTracking
                tech = user.technician_profile
                active = Reservation.objects.filter(
                    technician=tech,
                    status__in=['confirmed', 'technician_dispatched', 'in_progress']
                ).order_by('-updated_at').first()
                if active:
                    trip, _ = TripTracking.objects.get_or_create(reservation=active)
                    trip.technician_current_location = Point(longitude, latitude, srid=4326)
                    # Historique (best effort)
                    try:
                        hist = trip.location_history or []
                        hist.append({'lat': latitude, 'lon': longitude, 'ts': timezone.now().isoformat()})
                        trip.location_history = hist[-200:]
                    except Exception:
                        pass
                    trip.save()
        except Exception:
            pass

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

        serializer = TechnicianListSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)


    @action(detail=True, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def reviews(self, request, pk=None):
        """Tous les avis émis sur ce technicien, visibles par les clients."""
        technician = self.get_object()
        from apps.reservations.models import Evaluation
        from apps.reservations.serializers import EvaluationSerializer
        qs = Evaluation.objects.filter(technician=technician).select_related('client__user', 'reservation').order_by('-created_at')
        return Response(EvaluationSerializer(qs, many=True, context={'request': request}).data)

    @action(detail=True, methods=['get'], permission_classes=[permissions.IsAuthenticated], url_path='evaluations')
    def evaluations(self, request, pk=None):
        return self.reviews(request, pk=pk)

    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def available(self, request):
        """Techniciens disponibles à une date/heure en tenant compte des créneaux déjà occupés."""
        raw_dt = request.query_params.get('datetime') or request.query_params.get('date')
        if not raw_dt:
            return Response({'error': 'datetime requis'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            target_dt = datetime.fromisoformat(str(raw_dt).replace('Z', '+00:00'))
            if timezone.is_naive(target_dt):
                target_dt = timezone.make_aware(target_dt, timezone.get_current_timezone())
        except Exception:
            return Response({'error': 'datetime invalide'}, status=status.HTTP_400_BAD_REQUEST)

        latitude = request.query_params.get('latitude')
        longitude = request.query_params.get('longitude')
        service = request.query_params.get('service') or request.query_params.get('specialization')
        radius = float(request.query_params.get('radius', request.query_params.get('radius_km', 25)) or 25)

        queryset = Technician.objects.select_related('user').filter(
            user__is_available=True,
            status='available',
        ).filter(Q(approval_status='approved') | Q(approval_status='') | Q(approval_status__isnull=True))

        if service and service not in ['scheduled_maintenance', 'preventive_maintenance', 'specific_repair', 'diagnosis']:
            queryset = queryset.filter(specializations__contains=[service])

        from apps.reservations.services import is_technician_available_at
        candidates = [tech for tech in queryset if is_technician_available_at(tech, target_dt)]

        if latitude and longitude:
            try:
                user_location = Point(float(longitude), float(latitude), srid=4326)
                def distance_km(tech):
                    if not tech.user.location:
                        return 10**9
                    return tech.user.location.distance(user_location) * 111
                candidates = [t for t in candidates if distance_km(t) <= radius]
                candidates.sort(key=lambda t: (distance_km(t), -float(t.rating or 0)))
            except Exception:
                candidates.sort(key=lambda t: -float(t.rating or 0))
        else:
            candidates.sort(key=lambda t: -float(t.rating or 0))

        serializer = TechnicianListSerializer(candidates[:30], many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['patch'], permission_classes=[IsAdministrator])
    def approve_reject(self, request, pk=None):
        technician = self.get_object()

        action = request.data.get('action')  # 'approve' or 'reject'
        rejection_reason = request.data.get('rejection_reason', '')

        if action == 'approve':
            technician.approval_status = 'approved'
            technician.rejection_reason = ''
            message = 'Technicien approuvé avec succès'
        elif action == 'reject':
            technician.approval_status = 'rejected'
            technician.rejection_reason = rejection_reason
            message = 'Technicien refusé'
        else:
            return Response(
                {'error': 'Action invalide. Utilisez "approve" ou "reject"'},
                status=status.HTTP_400_BAD_REQUEST
            )

        technician.save()

        return Response({
            'message': message,
            'approval_status': technician.approval_status,
            'rejection_reason': technician.rejection_reason
        })

    @action(detail=True, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def documents(self, request, pk=None):
        technician = self.get_object()
        if request.user != technician.user and getattr(request.user, 'user_type', None) != 'administrator':
            return Response({'error': 'Non autorisé'}, status=status.HTTP_403_FORBIDDEN)
        return Response(TechnicianDocumentSerializer(technician.documents.all(), many=True, context={'request': request}).data)

    @action(detail=True, methods=['patch'], permission_classes=[IsAdministrator], url_path='documents/(?P<document_id>[^/.]+)/validate')
    def validate_document(self, request, pk=None, document_id=None):
        technician = self.get_object()
        try:
            document = technician.documents.get(id=document_id)
        except TechnicianDocument.DoesNotExist:
            return Response({'error': 'Document introuvable'}, status=status.HTTP_404_NOT_FOUND)

        validation_status = request.data.get('validation_status')
        if validation_status not in ['non_verifie', 'valide', 'invalide']:
            return Response({'error': 'Statut de validation invalide'}, status=status.HTTP_400_BAD_REQUEST)
        document.validation_status = validation_status
        document.validation_comment = request.data.get('validation_comment', '')
        document.save(update_fields=['validation_status', 'validation_comment'])
        return Response(TechnicianDocumentSerializer(document, context={'request': request}).data)

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
        from apps.reservations.services import get_reservations_revenue

        now = timezone.now()
        start_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        start_week = now - timedelta(days=7)
        reservations = Reservation.objects.filter(technician=technician)
        evaluations = Evaluation.objects.filter(technician=technician)
        revenue_total = float(get_reservations_revenue(reservations))
        revenue_month = float(get_reservations_revenue(reservations.filter(created_at__gte=start_month)))
        revenue_week = float(get_reservations_revenue(reservations.filter(created_at__gte=start_week)))

        stats = {
            'total_interventions': technician.total_interventions,
            'rating': float(technician.rating),
            'completed': reservations.filter(status='completed').count(),
            'in_progress': reservations.filter(status='in_progress').count(),
            'cancelled': reservations.filter(status='cancelled').count(),
            'specializations': technician.specializations,
            'certifications': technician.certifications,
            'revenue_total': revenue_total,
            'revenue_month': revenue_month,
            'revenue_week': revenue_week,
            'total_revenue': revenue_total,
            'monthly_revenue': revenue_month,
            'weekly_revenue': revenue_week,
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
        from django.db.models import Q,  Sum
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
