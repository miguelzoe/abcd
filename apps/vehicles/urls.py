from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.vehicles.views import VehicleViewSet, MaintenanceRecordViewSet, VehicleCatalogViewSet

# Configuration du router
router = DefaultRouter()
router.register(r'vehicles', VehicleViewSet, basename='vehicle')
router.register(r'maintenance', MaintenanceRecordViewSet, basename='maintenance')
router.register(r'vehicle-catalog', VehicleCatalogViewSet, basename='vehicle-catalog')

urlpatterns = [
    # Compatibilité avec les anciennes pages admin qui appelaient /api/vehicles/vehicle-catalog/.
    path('vehicles/vehicle-catalog/', VehicleCatalogViewSet.as_view({'get': 'list', 'post': 'create'}), name='vehicle-catalog-legacy-list'),
    path('vehicles/vehicle-catalog/<int:pk>/', VehicleCatalogViewSet.as_view({'get': 'retrieve', 'patch': 'partial_update', 'put': 'update', 'delete': 'destroy'}), name='vehicle-catalog-legacy-detail'),
    path('', include(router.urls)),
]