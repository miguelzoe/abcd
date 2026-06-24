from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.reservations.views import (
    ReservationViewSet, EvaluationViewSet,
    ChatViewSet, TechnicianAvailabilityViewSet, ReservationReminderViewSet
)

router = DefaultRouter()
router.register(r'reservations', ReservationViewSet, basename='reservation')
router.register(r'evaluations', EvaluationViewSet, basename='evaluation')
router.register(r'chat', ChatViewSet, basename='chat')
router.register(r'availabilities', TechnicianAvailabilityViewSet, basename='availability')
router.register(r'reminders', ReservationReminderViewSet, basename='reservation-reminder')

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
