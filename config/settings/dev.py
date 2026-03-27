from .base import *

DEBUG = True

ALLOWED_HOSTS = list(dict.fromkeys(ALLOWED_HOSTS + ["localhost", "127.0.0.1", "0.0.0.0"]))
CORS_ALLOW_ALL_ORIGINS = True
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
    "anon": "1000/minute",
    "user": "1000/minute",
    "auth": "100/minute",
    "location_update": "1000/minute",
    "register": "1000/minute",
}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}
