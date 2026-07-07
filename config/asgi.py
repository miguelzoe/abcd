import os

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', os.getenv('DJANGO_SETTINGS_MODULE', 'config.settings.base'))

django_asgi_app = get_asgi_application()

from apps.voice_calls.middleware import JwtAuthMiddleware  # noqa: E402
from apps.voice_calls.routing import websocket_urlpatterns as voice_websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': JwtAuthMiddleware(
        URLRouter(voice_websocket_urlpatterns)
    ),
})
