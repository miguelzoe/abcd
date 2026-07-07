from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.marketplace.views import (
    ProduitViewSet,
    PieceViewSet,
    CommandeViewSet,
    AvisViewSet,
    MarketplaceArticleTypeViewSet,
    MarketplaceVehicleViewSet,
    MarketplaceOrderViewSet,
    MarketplaceAuthRegisterView, MarketplaceAuthLoginView, MarketplaceAuthMeView,
    MarketplaceForgotPasswordView, MarketplaceResetPasswordView,
    MarketplacePartnerApplicationViewSet,
)

router = DefaultRouter()
router.register(r'produits', ProduitViewSet, basename='produit')
router.register(r'pieces', PieceViewSet, basename='piece')
router.register(r'commandes', CommandeViewSet, basename='commande')
router.register(r'avis', AvisViewSet, basename='avis')
router.register(r'article-types', MarketplaceArticleTypeViewSet, basename='article-type')
router.register(r'marketplace-vehicles', MarketplaceVehicleViewSet, basename='marketplace-vehicle')
router.register(r'marketplace-orders', MarketplaceOrderViewSet, basename='marketplace-order')
router.register(r'marketplace-partner-applications', MarketplacePartnerApplicationViewSet, basename='marketplace-partner-application')

urlpatterns = [
    path('marketplace-auth/register/', MarketplaceAuthRegisterView.as_view(), name='marketplace-auth-register'),
    path('marketplace-auth/login/', MarketplaceAuthLoginView.as_view(), name='marketplace-auth-login'),
    path('marketplace-auth/me/', MarketplaceAuthMeView.as_view(), name='marketplace-auth-me'),
    path('marketplace-auth/forgot-password/', MarketplaceForgotPasswordView.as_view(), name='marketplace-auth-forgot-password'),
    path('marketplace-auth/reset-password/', MarketplaceResetPasswordView.as_view(), name='marketplace-auth-reset-password'),
    # Compatibilité avec les anciennes pages admin qui appelaient /api/marketplace/...
    path('marketplace/article-types/', MarketplaceArticleTypeViewSet.as_view({'get': 'list', 'post': 'create'}), name='article-types-legacy-list'),
    path('marketplace/article-types/<int:pk>/', MarketplaceArticleTypeViewSet.as_view({'get': 'retrieve', 'patch': 'partial_update', 'put': 'update', 'delete': 'destroy'}), name='article-types-legacy-detail'),
    path('marketplace/vehicles/', MarketplaceVehicleViewSet.as_view({'get': 'list', 'post': 'create'}), name='marketplace-vehicles-legacy-list'),
    path('marketplace/vehicles/<str:pk>/', MarketplaceVehicleViewSet.as_view({'get': 'retrieve', 'patch': 'partial_update', 'put': 'update', 'delete': 'destroy'}), name='marketplace-vehicles-legacy-detail'),
    path('marketplace/orders/', MarketplaceOrderViewSet.as_view({'get': 'list', 'post': 'create'}), name='marketplace-orders-legacy-list'),
    path('marketplace/orders/<str:pk>/', MarketplaceOrderViewSet.as_view({'get': 'retrieve', 'patch': 'partial_update', 'put': 'update', 'delete': 'destroy'}), name='marketplace-orders-legacy-detail'),
    path('', include(router.urls)),
]
