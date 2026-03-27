from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.marketplace.views import ProduitViewSet, PieceViewSet, CommandeViewSet, AvisViewSet

# Configuration du router
router = DefaultRouter()
router.register(r'produits', ProduitViewSet, basename='produit')
router.register(r'pieces', PieceViewSet, basename='piece')
router.register(r'commandes', CommandeViewSet, basename='commande')
router.register(r'avis', AvisViewSet, basename='avis')

urlpatterns = [
    path('', include(router.urls)),
]