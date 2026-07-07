from rest_framework import viewsets, status, permissions
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q, Count, Avg, Sum
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes, force_str, DjangoUnicodeDecodeError
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils import timezone
from datetime import datetime
from urllib.parse import quote

from apps.marketplace.models import Produit, Piece, Commande, LigneCommande, Avis, MarketplaceArticleType, MarketplaceVehicle, MarketplaceOrder, MarketplacePartnerApplication
from apps.marketplace.serializers import (
    ProduitSerializer, ProduitListSerializer, ProduitCreateSerializer,
    ProduitUpdateSerializer, ProduitDetailSerializer,
    PieceSerializer, PieceCreateSerializer,
    CommandeSerializer, CommandeListSerializer, CommandeCreateSerializer,
    CommandeUpdateStatusSerializer,
    AvisSerializer, AvisCreateSerializer,
    MarketplaceStatsSerializer, MarketplaceArticleTypeSerializer,
    MarketplaceVehicleSerializer, MarketplaceVehicleCreateUpdateSerializer,
    MarketplaceOrderSerializer, MarketplaceOrderCreateSerializer, MarketplaceOrderStatusSerializer,
    MarketplaceRegisterSerializer, MarketplaceLoginSerializer, MarketplaceAuthUserSerializer,
    MarketplacePartnerApplicationSerializer, MarketplacePartnerApplicationCreateSerializer,
    MarketplacePasswordResetRequestSerializer, MarketplacePasswordResetConfirmSerializer
)
from apps.marketplace.permissions import (
    IsVendorOrAdmin, IsProductOwner, IsCommandeOwner,
    CanCreateCommande, CanReview
)
from apps.marketplace.services import (
    update_commande_status, cancel_commande, get_best_selling_products,
    get_low_stock_products, get_marketplace_stats, process_payment
)


class MarketplacePageNumberPagination(PageNumberPagination):
    """Pagination compatible mobile/admin : ?page=1&limit=20."""
    page_size_query_param = 'limit'
    max_page_size = 100


User = get_user_model()
MARKETPLACE_USER_TYPES = ['marketplace_customer', 'vendor', 'auto_shop', 'administrator']


def _is_marketplace_user(user):
    return bool(user and user.is_authenticated and getattr(user, 'user_type', None) in MARKETPLACE_USER_TYPES)


def _order_belongs_to_user(order, user):
    if not user or not user.is_authenticated:
        return False
    if getattr(order, 'marketplace_user_id', None) == user.id:
        return True
    if getattr(order, 'client', None) and order.client.user_id == user.id:
        return True
    return False


# ==================== MARKETPLACE AUTH / ACCRÉDITATION ====================

class MarketplaceAuthRegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = MarketplaceRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = __import__('rest_framework_simplejwt.tokens', fromlist=['RefreshToken']).RefreshToken.for_user(user)
        return Response({'message': 'Compte marketplace créé avec succès.', 'user': MarketplaceAuthUserSerializer(user).data, 'access': str(refresh.access_token), 'refresh': str(refresh)}, status=status.HTTP_201_CREATED)


class MarketplaceAuthLoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = MarketplaceLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        return Response({'message': 'Connexion marketplace réussie.', 'user': MarketplaceAuthUserSerializer(user).data, 'access': serializer.validated_data['access'], 'refresh': serializer.validated_data['refresh']})


class MarketplaceAuthMeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not _is_marketplace_user(request.user):
            return Response({'error': "Ce compte appartient à l'application intervention. Utilisez un compte marketplace séparé."}, status=status.HTTP_403_FORBIDDEN)
        return Response(MarketplaceAuthUserSerializer(request.user).data)


class MarketplaceForgotPasswordView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = MarketplacePasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        identifier = serializer.validated_data['identifier']
        user = User.objects.filter(Q(email__iexact=identifier) | Q(username__iexact=identifier) | Q(telephone=identifier), user_type__in=MARKETPLACE_USER_TYPES, is_active=True).first()
        payload = {'message': 'Si ce compte marketplace existe, un lien de réinitialisation a été préparé.'}
        if not user:
            return Response(payload)
        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        reset_token = f'{uidb64}:{token}'
        frontend_base = getattr(settings, 'MARKETPLACE_FRONTEND_URL', 'marketplacecartronic://auth/forgot-password').rstrip('/')
        separator = '&' if '?' in frontend_base else '?'
        reset_url = f"{frontend_base}{separator}token={quote(reset_token, safe='')}"
        if user.email:
            send_mail('Réinitialisation de votre mot de passe Marketplace Cartronic', f'Lien : {reset_url}\nCode : {reset_token}', getattr(settings, 'DEFAULT_FROM_EMAIL', None), [user.email], fail_silently=True)
        if getattr(settings, 'MARKETPLACE_PASSWORD_RESET_EXPOSE_TOKEN', False):
            payload.update({'reset_token': reset_token, 'reset_url': reset_url})
        return Response(payload)


class MarketplaceResetPasswordView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = MarketplacePasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token_value = serializer.validated_data['token']
        if ':' not in token_value:
            return Response({'error': 'Token invalide.'}, status=status.HTTP_400_BAD_REQUEST)
        uidb64, token = token_value.split(':', 1)
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid, user_type__in=MARKETPLACE_USER_TYPES, is_active=True)
        except (User.DoesNotExist, DjangoUnicodeDecodeError, ValueError, TypeError):
            return Response({'error': 'Token invalide ou expiré.'}, status=status.HTTP_400_BAD_REQUEST)
        if not default_token_generator.check_token(user, token):
            return Response({'error': 'Token invalide ou expiré.'}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(serializer.validated_data['new_password'])
        user.password_changed_at = timezone.now()
        user.password_expiry_notified_at = None
        user.save(update_fields=['password', 'password_changed_at', 'password_expiry_notified_at', 'updated_at'])
        return Response({'message': 'Mot de passe marketplace réinitialisé avec succès.'})


class MarketplacePartnerApplicationViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = MarketplacePageNumberPagination

    def get_serializer_class(self):
        if self.action == 'create':
            return MarketplacePartnerApplicationCreateSerializer
        return MarketplacePartnerApplicationSerializer

    def get_queryset(self):
        user = self.request.user
        qs = MarketplacePartnerApplication.objects.select_related('user', 'reviewed_by')
        if getattr(user, 'user_type', None) == 'administrator' or getattr(user, 'is_staff', False):
            status_filter = self.request.query_params.get('status')
            partner_type = self.request.query_params.get('partner_type') or self.request.query_params.get('type')
            search = self.request.query_params.get('search')
            if status_filter:
                qs = qs.filter(status=status_filter)
            if partner_type:
                qs = qs.filter(partner_type=partner_type)
            if search:
                qs = qs.filter(Q(company_name__icontains=search) | Q(user__email__icontains=search) | Q(user__telephone__icontains=search))
            return qs
        return qs.filter(user=user)

    @action(detail=False, methods=['get'])
    def mine(self, request):
        qs = MarketplacePartnerApplication.objects.filter(user=request.user).order_by('-created_at')
        return Response(MarketplacePartnerApplicationSerializer(qs, many=True).data)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        if getattr(request.user, 'user_type', None) != 'administrator' and not getattr(request.user, 'is_staff', False):
            return Response({'error': 'Réservé aux administrateurs.'}, status=status.HTTP_403_FORBIDDEN)
        application = self.get_object()
        application.approve(admin_user=request.user)
        return Response(MarketplacePartnerApplicationSerializer(application).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        if getattr(request.user, 'user_type', None) != 'administrator' and not getattr(request.user, 'is_staff', False):
            return Response({'error': 'Réservé aux administrateurs.'}, status=status.HTTP_403_FORBIDDEN)
        application = self.get_object()
        application.reject(admin_user=request.user, reason=request.data.get('reason') or request.data.get('rejection_reason') or '')
        return Response(MarketplacePartnerApplicationSerializer(application).data)


# ==================== PRODUIT VIEWSET ====================



class MarketplaceArticleTypeViewSet(viewsets.ModelViewSet):
    """Types d’articles marketplace administrables."""
    queryset = MarketplaceArticleType.objects.all()
    serializer_class = MarketplaceArticleTypeSerializer
    pagination_class = MarketplacePageNumberPagination

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticatedOrReadOnly()]

    def get_queryset(self):
        qs = MarketplaceArticleType.objects.all()
        kind = self.request.query_params.get('kind')
        if kind:
            qs = qs.filter(kind=kind)
        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(Q(label__icontains=search) | Q(code__icontains=search))
        if self.request.query_params.get('active', 'true').lower() == 'true':
            qs = qs.filter(is_active=True)
        return qs.order_by('kind', 'label')

    def _ensure_admin(self):
        if getattr(self.request.user, 'user_type', None) != 'administrator':
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Réservé aux administrateurs.')

    def perform_create(self, serializer):
        self._ensure_admin()
        serializer.save()

    def perform_update(self, serializer):
        self._ensure_admin()
        serializer.save()

    def perform_destroy(self, instance):
        self._ensure_admin()
        instance.delete()

class ProduitViewSet(viewsets.ModelViewSet):
    """ViewSet pour les produits"""
    queryset = Produit.objects.prefetch_related('pieces', 'avis')
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ProduitListSerializer
        elif self.action == 'create':
            return ProduitCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return ProduitUpdateSerializer
        elif self.action == 'retrieve':
            return ProduitDetailSerializer
        return ProduitSerializer
    
    def get_permissions(self):
        if self.action in ['create']:
            return [IsVendorOrAdmin()]
        elif self.action in ['update', 'partial_update', 'destroy']:
            return [IsProductOwner()]
        return [permissions.IsAuthenticatedOrReadOnly()]
    
    def get_queryset(self):
        queryset = Produit.objects.prefetch_related('pieces', 'avis')
        
        # Filtrer les produits actifs pour les non-vendeurs
        user = self.request.user
        if not user.is_authenticated or user.user_type not in ['vendor', 'auto_shop', 'administrator']:
            queryset = queryset.filter(is_active=True)
        
        # Si vendeur, voir uniquement ses produits
        if user.is_authenticated and user.user_type in ['vendor', 'auto_shop']:
            if self.action in ['list', 'retrieve']:
                queryset = queryset.filter(Q(vendeur=user) | Q(is_active=True))
        
        # Filtres par query params
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)
        
        marque = self.request.query_params.get('marque')
        if marque:
            queryset = queryset.filter(marque__icontains=marque)
        
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(nom__icontains=search) |
                Q(description__icontains=search) |
                Q(marque__icontains=search)
            )
        
        prix_min = self.request.query_params.get('prix_min')
        prix_max = self.request.query_params.get('prix_max')
        
        if prix_min:
            queryset = queryset.filter(prix__gte=float(prix_min))
        if prix_max:
            queryset = queryset.filter(prix__lte=float(prix_max))
        
        en_stock = self.request.query_params.get('en_stock')
        if en_stock == 'true':
            queryset = queryset.filter(stock__gt=0)
        
        featured = self.request.query_params.get('featured')
        if featured == 'true':
            queryset = queryset.filter(is_featured=True)
        
        return queryset.order_by('-created_at')
    
    @action(detail=False, methods=['get'])
    def best_sellers(self, request):
        """GET /api/produits/best_sellers/?limit=10"""
        limit = int(request.query_params.get('limit', 10))
        products = get_best_selling_products(limit)
        serializer = ProduitListSerializer(products, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        """GET /api/produits/low_stock/?threshold=10"""
        if request.user.user_type not in ['vendor', 'auto_shop', 'administrator']:
            return Response(
                {'error': 'Non autorisé'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        threshold = int(request.query_params.get('threshold', 10))
        
        if request.user.user_type in ['vendor', 'auto_shop']:
            products = get_low_stock_products(threshold).filter(vendeur=request.user)
        else:
            products = get_low_stock_products(threshold)
        
        serializer = ProduitListSerializer(products, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], permission_classes=[IsProductOwner])
    def update_stock(self, request, pk=None):
        """POST /api/produits/{id}/update_stock/"""
        produit = self.get_object()
        new_stock = request.data.get('stock')
        
        if new_stock is None:
            return Response(
                {'error': 'stock requis'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            produit.stock = int(new_stock)
            produit.save()
            return Response(ProduitSerializer(produit).data)
        except ValueError:
            return Response(
                {'error': 'Stock invalide'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['get'])
    def reviews(self, request, pk=None):
        """GET /api/produits/{id}/reviews/"""
        produit = self.get_object()
        avis = produit.avis.all()
        serializer = AvisSerializer(avis, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def my_products(self, request):
        """GET /api/produits/my_products/"""
        if request.user.user_type not in ['vendor', 'auto_shop']:
            return Response(
                {'error': 'Disponible uniquement pour les vendeurs'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        products = Produit.objects.filter(vendeur=request.user)
        serializer = ProduitListSerializer(products, many=True)
        return Response(serializer.data)


# ==================== PIECE VIEWSET ====================

class PieceViewSet(viewsets.ModelViewSet):
    """ViewSet pour les pièces détachées"""
    queryset = Piece.objects.select_related('produit', 'produit__vendeur')
    serializer_class = PieceSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    pagination_class = MarketplacePageNumberPagination
    
    def get_serializer_class(self):
        if self.action == 'create':
            return PieceCreateSerializer
        return PieceSerializer
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsVendorOrAdmin()]
        return [permissions.IsAuthenticatedOrReadOnly()]
    
    def get_queryset(self):
        queryset = Piece.objects.select_related('produit', 'produit__vendeur')
        
        # Filtrer par produit
        produit_id = self.request.query_params.get('produit')
        if produit_id:
            queryset = queryset.filter(produit_id=produit_id)
        
        # En stock
        en_stock = self.request.query_params.get('en_stock')
        if en_stock == 'true':
            queryset = queryset.filter(stock__gt=0)
        
        # Recherche par référence
        reference = self.request.query_params.get('reference')
        if reference:
            queryset = queryset.filter(reference__icontains=reference)

        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(nom__icontains=search) |
                Q(reference__icontains=search) |
                Q(description__icontains=search) |
                Q(produit__nom__icontains=search)
            )
        
        return queryset.order_by('-created_at')
    
    @action(detail=False, methods=['get'])
    def search_by_reference(self, request):
        """GET /api/pieces/search_by_reference/?reference=XXX"""
        reference = request.query_params.get('reference')
        
        if not reference:
            return Response(
                {'error': 'Référence requise'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            piece = Piece.objects.get(reference=reference)
            serializer = PieceSerializer(piece)
            return Response(serializer.data)
        except Piece.DoesNotExist:
            return Response(
                {'error': 'Pièce non trouvée'},
                status=status.HTTP_404_NOT_FOUND
            )


# ==================== COMMANDE VIEWSET ====================

class CommandeViewSet(viewsets.ModelViewSet):
    """ViewSet pour les commandes"""
    queryset = Commande.objects.select_related('client__user').prefetch_related('lignes__produit')
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return CommandeListSerializer
        elif self.action == 'create':
            return CommandeCreateSerializer
        return CommandeSerializer
    
    def get_permissions(self):
        if self.action == 'create':
            return [CanCreateCommande()]
        elif self.action in ['update', 'partial_update', 'destroy']:
            return [IsCommandeOwner()]
        return [permissions.IsAuthenticated()]
    
    def get_queryset(self):
        user = self.request.user
        queryset = Commande.objects.select_related('client__user').prefetch_related('lignes__produit')
        
        if user.user_type == 'client':
            queryset = queryset.filter(client__user=user)
        elif user.user_type != 'administrator':
            queryset = queryset.none()
        
        # Filtres
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        payment_status = self.request.query_params.get('payment_status')
        if payment_status:
            queryset = queryset.filter(payment_status=payment_status)
        
        return queryset.order_by('-date')
    
    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """POST /api/commandes/{id}/update_status/"""
        if request.user.user_type != 'administrator':
            return Response(
                {'error': 'Réservé aux administrateurs'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        commande = self.get_object()
        serializer = CommandeUpdateStatusSerializer(data=request.data)
        
        if serializer.is_valid():
            new_status = serializer.validated_data['status']
            notes_admin = serializer.validated_data.get('notes_admin', '')
            
            if notes_admin:
                commande.notes_admin += f"\n{notes_admin}"
            
            update_commande_status(commande, new_status)
            
            return Response(CommandeSerializer(commande).data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """POST /api/commandes/{id}/cancel/"""
        commande = self.get_object()
        
        # Vérifier permissions
        can_cancel = (
            request.user == commande.client.user or
            request.user.user_type == 'administrator'
        )
        
        if not can_cancel:
            return Response(
                {'error': 'Non autorisé'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            cancel_commande(commande)
            return Response(CommandeSerializer(commande).data)
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def pay(self, request, pk=None):
        """POST /api/commandes/{id}/pay/"""
        commande = self.get_object()
        
        if commande.client.user != request.user:
            return Response(
                {'error': 'Non autorisé'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if commande.payment_status == 'paid':
            return Response(
                {'error': 'Commande déjà payée'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        payment_method = request.data.get('payment_method', 'cash')
        success = process_payment(commande, payment_method)
        
        if success:
            return Response(CommandeSerializer(commande).data)
        
        return Response(
            {'error': 'Échec du paiement'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    @action(detail=False, methods=['get'])
    def my_orders(self, request):
        """GET /api/commandes/my_orders/"""
        if request.user.user_type != 'client':
            return Response(
                {'error': 'Disponible uniquement pour les clients'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        commandes = Commande.objects.filter(
            client__user=request.user
        ).order_by('-date')
        
        serializer = CommandeListSerializer(commandes, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def pending_orders(self, request):
        """GET /api/commandes/pending_orders/"""
        if request.user.user_type != 'administrator':
            return Response(
                {'error': 'Réservé aux administrateurs'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        commandes = Commande.objects.filter(status='pending').order_by('date')
        serializer = CommandeSerializer(commandes, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """GET /api/commandes/stats/"""
        if request.user.user_type != 'administrator':
            return Response(
                {'error': 'Réservé aux administrateurs'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        if start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
        if end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d')
        
        stats = get_marketplace_stats(start_date, end_date)
        serializer = MarketplaceStatsSerializer(stats)
        return Response(serializer.data)


# ==================== AVIS VIEWSET ====================

class AvisViewSet(viewsets.ModelViewSet):
    """ViewSet pour les avis"""
    queryset = Avis.objects.select_related('client__user', 'produit')
    serializer_class = AvisSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return AvisCreateSerializer
        return AvisSerializer
    
    def get_permissions(self):
        if self.action == 'create':
            return [CanReview()]
        elif self.action in ['update', 'partial_update', 'destroy']:
            return [CanReview()]
        return [permissions.IsAuthenticatedOrReadOnly()]
    
    def get_queryset(self):
        queryset = Avis.objects.select_related('client__user', 'produit')
        
        # Filtrer par produit
        produit_id = self.request.query_params.get('produit')
        if produit_id:
            queryset = queryset.filter(produit_id=produit_id)
        
        # Filtrer par note
        min_rating = self.request.query_params.get('min_rating')
        if min_rating:
            queryset = queryset.filter(note__gte=int(min_rating))
        
        # Achats vérifiés uniquement
        verified_only = self.request.query_params.get('verified_only')
        if verified_only == 'true':
            queryset = queryset.filter(commande__isnull=False)
        
        return queryset.order_by('-created_at')
    
    @action(detail=False, methods=['get'])
    def my_reviews(self, request):
        """GET /api/avis/my_reviews/"""
        if request.user.user_type != 'client':
            return Response(
                {'error': 'Disponible uniquement pour les clients'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        avis = Avis.objects.filter(client__user=request.user)
        serializer = AvisSerializer(avis, many=True)
        return Response(serializer.data)

# ==================== MARKETPLACE MOBILE VEHICLES VIEWSET ====================

class MarketplaceVehicleViewSet(viewsets.ModelViewSet):
    """API mobile pour les véhicules de vente/location de marketplace_cartronic."""
    queryset = MarketplaceVehicle.objects.all()
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    pagination_class = MarketplacePageNumberPagination

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return MarketplaceVehicleCreateUpdateSerializer
        return MarketplaceVehicleSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsVendorOrAdmin()]
        return [permissions.IsAuthenticatedOrReadOnly()]

    def get_queryset(self):
        qs = MarketplaceVehicle.objects.select_related('partner')
        user = self.request.user
        if not user.is_authenticated or getattr(user, 'user_type', None) not in ['vendor', 'auto_shop', 'administrator']:
            qs = qs.filter(is_active=True)
        elif getattr(user, 'user_type', None) == 'vendor':
            qs = qs.filter(Q(partner=user) | Q(is_active=True))

        vehicle_type = self.request.query_params.get('type')
        if vehicle_type:
            qs = qs.filter(type=vehicle_type)

        brand = self.request.query_params.get('brand')
        if brand:
            qs = qs.filter(brand__icontains=brand)

        body_type = self.request.query_params.get('bodyType') or self.request.query_params.get('body_type')
        if body_type:
            qs = qs.filter(body_type=body_type)

        fuel = self.request.query_params.get('fuel')
        if fuel:
            qs = qs.filter(fuel=fuel)

        transmission = self.request.query_params.get('transmission')
        if transmission:
            qs = qs.filter(transmission=transmission)

        seats = self.request.query_params.get('seats')
        if seats:
            qs = qs.filter(seats__gte=int(seats))

        min_price = self.request.query_params.get('minPrice') or self.request.query_params.get('min_price')
        max_price = self.request.query_params.get('maxPrice') or self.request.query_params.get('max_price')
        if min_price:
            qs = qs.filter(price__gte=float(min_price))
        if max_price:
            qs = qs.filter(price__lte=float(max_price))

        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(
                Q(name__icontains=search) |
                Q(brand__icontains=search) |
                Q(model__icontains=search) |
                Q(description__icontains=search) |
                Q(location__icontains=search)
            )

        featured = self.request.query_params.get('featured')
        if featured and featured.lower() == 'true':
            qs = qs.filter(is_featured=True)

        return qs.order_by('-is_featured', '-created_at')

    @action(detail=False, methods=['get'])
    def featured(self, request):
        limit = int(request.query_params.get('limit', 5))
        qs = self.get_queryset().filter(is_featured=True)[:limit]
        if not qs:
            qs = self.get_queryset()[:limit]
        return Response(MarketplaceVehicleSerializer(qs, many=True).data)

    @action(detail=True, methods=['get'])
    def availability(self, request, pk=None):
        vehicle = self.get_object()
        start_date = request.query_params.get('start_date') or request.query_params.get('startDate')
        end_date = request.query_params.get('end_date') or request.query_params.get('endDate')
        if vehicle.type != 'rental':
            return Response({'available': False, 'reason': 'Ce véhicule n’est pas en location.'})
        if not start_date or not end_date:
            return Response({'available': True})
        try:
            start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        except ValueError:
            return Response({'error': 'Dates invalides'}, status=status.HTTP_400_BAD_REQUEST)
        if end <= start:
            return Response({'available': False, 'reason': 'Période invalide.'})

        conflicts = False
        for order in MarketplaceOrder.objects.filter(
            type='vehicle_rental',
            status__in=['pending', 'confirmed', 'ready', 'in_progress'],
            rental_start_date__lt=end,
            rental_end_date__gt=start,
        ):
            if any(str(item.get('id')) == str(vehicle.id) for item in (order.items or [])):
                conflicts = True
                break
        return Response({'available': not conflicts})

    @action(detail=True, methods=['get'])
    def reviews(self, request, pk=None):
        """GET /api/marketplace-vehicles/{id}/reviews/
        Endpoint stable pour marketplace_cartronic. Les avis véhicules peuvent
        être branchés plus tard sans casser le frontend.
        """
        self.get_object()
        return Response([])


# ==================== MARKETPLACE MOBILE ORDERS VIEWSET ====================

class MarketplaceOrderViewSet(viewsets.ModelViewSet):
    """API mobile pour les commandes de marketplace_cartronic."""
    queryset = MarketplaceOrder.objects.select_related('client__user', 'marketplace_user')
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = MarketplacePageNumberPagination

    def get_serializer_class(self):
        if self.action == 'create':
            return MarketplaceOrderCreateSerializer
        return MarketplaceOrderSerializer

    def get_queryset(self):
        user = self.request.user
        qs = MarketplaceOrder.objects.select_related('client__user', 'marketplace_user')
        if getattr(user, 'user_type', None) in ['marketplace_customer', 'client']:
            qs = qs.filter(Q(marketplace_user=user) | Q(client__user=user))
        elif getattr(user, 'user_type', None) not in ['administrator', 'vendor', 'auto_shop']:
            qs = qs.none()

        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status__in=status_filter.split(','))
        type_filter = self.request.query_params.get('type')
        if type_filter:
            qs = qs.filter(type__in=type_filter.split(','))

        start_date = self.request.query_params.get('start_date') or self.request.query_params.get('startDate')
        end_date = self.request.query_params.get('end_date') or self.request.query_params.get('endDate')
        if start_date:
            try:
                qs = qs.filter(created_at__gte=datetime.fromisoformat(start_date.replace('Z', '+00:00')))
            except ValueError:
                pass
        if end_date:
            try:
                qs = qs.filter(created_at__lte=datetime.fromisoformat(end_date.replace('Z', '+00:00')))
            except ValueError:
                pass

        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(Q(id__icontains=search) | Q(items__icontains=search))
        return qs.order_by('-created_at')

    def perform_create(self, serializer):
        if getattr(self.request.user, 'user_type', None) not in ['marketplace_customer', 'client']:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Disponible uniquement pour les clients marketplace.')
        serializer.save()

    @action(detail=False, methods=['get'])
    def my_orders(self, request):
        qs = self.get_queryset().filter(Q(marketplace_user=request.user) | Q(client__user=request.user))
        return Response(MarketplaceOrderSerializer(qs, many=True).data)

    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        order = self.get_object()
        user = request.user
        is_admin_or_vendor = getattr(user, 'user_type', None) in ['administrator', 'vendor', 'auto_shop']
        is_owner_cancel = _order_belongs_to_user(order, user) and request.data.get('status') == 'cancelled'
        if not (is_admin_or_vendor or is_owner_cancel):
            return Response({'error': 'Non autorisé'}, status=status.HTTP_403_FORBIDDEN)

        serializer = MarketplaceOrderStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        order.status = data['status']
        if data.get('actualPickupDate'):
            order.actual_pickup_date = data['actualPickupDate']
        if data.get('actualReturnDate'):
            order.actual_return_date = data['actualReturnDate']
        if data.get('notes'):
            order.notes = data['notes']
        if data.get('cancellationReason'):
            order.cancellation_reason = data['cancellationReason']
        order.save()
        return Response(MarketplaceOrderSerializer(order).data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        order = self.get_object()
        if not _order_belongs_to_user(order, request.user) and getattr(request.user, 'user_type', None) not in ['administrator', 'vendor', 'auto_shop']:
            return Response({'error': 'Non autorisé'}, status=status.HTTP_403_FORBIDDEN)
        if order.status in ['delivered', 'completed', 'cancelled']:
            return Response({'error': 'Cette commande ne peut plus être annulée.'}, status=status.HTTP_400_BAD_REQUEST)
        order.status = 'cancelled'
        order.cancellation_reason = request.data.get('reason') or request.data.get('cancellationReason') or 'Commande annulée par l’utilisateur'
        order.save()
        return Response(MarketplaceOrderSerializer(order).data)

    @action(detail=True, methods=['post'])
    def pay(self, request, pk=None):
        order = self.get_object()
        if not _order_belongs_to_user(order, request.user):
            return Response({'error': 'Non autorisé'}, status=status.HTTP_403_FORBIDDEN)
        if order.payment_status == 'paid':
            return Response({'error': 'Commande déjà payée'}, status=status.HTTP_400_BAD_REQUEST)
        order.payment_method = request.data.get('paymentMethod') or request.data.get('payment_method') or order.payment_method
        order.payment_status = 'paid'
        from django.utils import timezone
        order.payment_date = timezone.now()
        order.save()
        return Response(MarketplaceOrderSerializer(order).data)

