from django.urls import re_path
from apps.voice_calls.consumers import VoiceCallConsumer, VoicePresenceConsumer

websocket_urlpatterns = [
    re_path(r'^ws/voice/user/$', VoicePresenceConsumer.as_asgi()),
    re_path(r'^ws/voice/calls/(?P<session_id>[0-9a-f-]+)/$', VoiceCallConsumer.as_asgi()),
]
