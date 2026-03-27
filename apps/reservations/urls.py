from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.reservations.views import (
    ReservationViewSet, EvaluationViewSet, VehicleViewSet,
    ChatViewSet, TechnicianAvailabilityViewSet
)

router = DefaultRouter()
router.register(r'reservations', ReservationViewSet, basename='reservation')
router.register(r'evaluations', EvaluationViewSet, basename='evaluation')
router.register(r'vehicles', VehicleViewSet, basename='vehicle')
router.register(r'chat', ChatViewSet, basename='chat')
router.register(r'availabilities', TechnicianAvailabilityViewSet, basename='availability')

urlpatterns = [
    path('', include(router.urls)),

    # Aliases (compat mobile) : /api/technicians/me/availabilities/
    path(
        'technicians/me/availabilities/',
        TechnicianAvailabilityViewSet.as_view({'get': 'list', 'post': 'create'}),
        name='technician-me-availabilities',
    ),
    path(
        'technicians/me/availabilities/<int:pk>/',
        TechnicianAvailabilityViewSet.as_view({'get': 'retrieve', 'patch': 'partial_update', 'delete': 'destroy'}),
        name='technician-me-availabilities-detail',
    ),
]
