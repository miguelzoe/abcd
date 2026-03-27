from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q, Count, Avg, Sum
from datetime import datetime

from apps.marketplace.models import Produit, Piece, Commande, LigneCommande, Avis
from apps.marketplace.serializers import (
    ProduitSerializer, ProduitListSerializer, ProduitCreateSerializer,
    ProduitUpdateSerializer, ProduitDetailSerializer,
    PieceSerializer, PieceCreateSerializer,
    CommandeSerializer, CommandeListSerializer, CommandeCreateSerializer,
    CommandeUpdateStatusSerializer,
    AvisSerializer, AvisCreateSerializer,
    MarketplaceStatsSerializer
)
from apps.marketplace.permissions import (
    IsVendorOrAdmin, IsProductOwner, IsCommandeOwner,
    CanCreateCommande, CanReview
)
from apps.marketplace.services import (
    update_commande_status, cancel_commande, get_best_selling_products,
    get_low_stock_products, get_marketplace_stats, process_payment
)


# ==================== PRODUIT VIEWSET ====================

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
        if not user.is_authenticated or user.user_type not in ['vendor', 'administrator']:
            queryset = queryset.filter(is_active=True)
        
        # Si vendeur, voir uniquement ses produits
        if user.is_authenticated and user.user_type == 'vendor':
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
        if request.user.user_type not in ['vendor', 'administrator']:
            return Response(
                {'error': 'Non autorisé'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        threshold = int(request.query_params.get('threshold', 10))
        
        if request.user.user_type == 'vendor':
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
        if request.user.user_type != 'vendor':
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
    queryset = Piece.objects.select_related('produit')
    serializer_class = PieceSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return PieceCreateSerializer
        return PieceSerializer
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsVendorOrAdmin()]
        return [permissions.IsAuthenticatedOrReadOnly()]
    
    def get_queryset(self):
        queryset = Piece.objects.select_related('produit')
        
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
        
        return queryset
    
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