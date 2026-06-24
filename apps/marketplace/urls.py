from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.marketplace.views import ProduitViewSet, PieceViewSet, CommandeViewSet, AvisViewSet, MarketplaceArticleTypeViewSet

# Configuration du router
router = DefaultRouter()
router.register(r'produits', ProduitViewSet, basename='produit')
router.register(r'pieces', PieceViewSet, basename='piece')
router.register(r'commandes', CommandeViewSet, basename='commande')
router.register(r'avis', AvisViewSet, basename='avis')
router.register(r'article-types', MarketplaceArticleTypeViewSet, basename='article-type')

urlpatterns = [
    # Compatibilité avec les anciennes pages admin qui appelaient /api/marketplace/article-types/.
    path('marketplace/article-types/', MarketplaceArticleTypeViewSet.as_view({'get': 'list', 'post': 'create'}), name='article-types-legacy-list'),
    path('marketplace/article-types/<int:pk>/', MarketplaceArticleTypeViewSet.as_view({'get': 'retrieve', 'patch': 'partial_update', 'put': 'update', 'delete': 'destroy'}), name='article-types-legacy-detail'),
    path('', include(router.urls)),
]