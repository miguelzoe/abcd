from django.urls import include, path
from rest_framework.routers import DefaultRouter
from apps.voice_calls.views import VoiceCallSessionViewSet

router = DefaultRouter()
router.register(r'voice-calls', VoiceCallSessionViewSet, basename='voice-call')

urlpatterns = [
    path('', include(router.urls)),
]
