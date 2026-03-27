from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.vehicles.views import VehicleViewSet, MaintenanceRecordViewSet

# Configuration du router
router = DefaultRouter()
router.register(r'vehicles', VehicleViewSet, basename='vehicle')
router.register(r'maintenance', MaintenanceRecordViewSet, basename='maintenance')

urlpatterns = [
    path('', include(router.urls)),
]