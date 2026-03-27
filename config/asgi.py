"""
ASGI config for willy_project.

Expose l'application ASGI en tant que variable module-level nommée ``application``.
Route le trafic HTTP vers le handler Django standard et le trafic WebSocket
vers Django Channels.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')

# Initialiser Django ASGI en premier pour peupler le registre d'apps
# avant tout import qui pourrait déclencher des imports de modèles.
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter          # noqa: E402
from channels.security.websocket import AllowedHostsOriginValidator  # noqa: E402
from apps.reservations.routing import websocket_urlpatterns          # noqa: E402

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': AllowedHostsOriginValidator(
        URLRouter(websocket_urlpatterns)
    ),
})
