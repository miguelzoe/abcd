import os
from pathlib import Path
from datetime import timedelta

import dj_database_url
from decouple import Csv, config

from .geospatial import configure_geospatial_environment

BASE_DIR = Path(__file__).resolve().parent.parent.parent

configure_geospatial_environment()

GDAL_LIBRARY_PATH = config('GDAL_LIBRARY_PATH', default=os.environ.get('GDAL_LIBRARY_PATH'))
GEOS_LIBRARY_PATH = config('GEOS_LIBRARY_PATH', default=os.environ.get('GEOS_LIBRARY_PATH'))

if os.name == 'nt':
    osgeo4w_root = config('OSGEO4W_ROOT', default=os.environ.get('OSGEO4W_ROOT', r'C:\OSGeo4W'))
    if os.path.isdir(osgeo4w_root):
        os.environ.setdefault('OSGEO4W_ROOT', osgeo4w_root)
        os.environ.setdefault('GDAL_DATA', os.path.join(osgeo4w_root, 'share', 'gdal'))
        os.environ.setdefault('PROJ_LIB', os.path.join(osgeo4w_root, 'share', 'proj'))
        os.environ['PATH'] = os.path.join(osgeo4w_root, 'bin') + os.pathsep + os.environ.get('PATH', '')

SECRET_KEY = config('SECRET_KEY', default='change-me-in-production')
DEBUG = config('DEBUG', default=False, cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1,.onrender.com', cast=Csv())
CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS', default='https://efgh-3h6w.vercel.app,http://localhost:4200,http://127.0.0.1:4200', cast=Csv())
CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS', default='https://efgh-3h6w.vercel.app,https://*.vercel.app,http://localhost:4200,http://127.0.0.1:4200', cast=Csv())
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_ORIGINS = config('CORS_ALLOW_ALL_ORIGINS', default=False, cast=bool)
CORS_ALLOWED_ORIGIN_REGEXES = [
    r'^https://.*\.vercel\.app$',
]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.gis',
    'rest_framework',
    'rest_framework_gis',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'channels',
    'django_filters',
    'drf_spectacular',
    'apps.users',
    'apps.vehicles',
    'apps.reservations',
    'apps.marketplace',
    'apps.payments',
    'apps.admin_panel',
    'apps.core',
    'apps.voice_calls',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.media',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

DATABASE_URL = config(
    'DATABASE_URL',
    default='postgresql://postgres:postgres@localhost:5432/willy_db',
)
DB_CONN_MAX_AGE = config('DB_CONN_MAX_AGE', default=60, cast=int)
DB_SSLMODE = config('DB_SSLMODE', default='', cast=str)

parsed_database = dj_database_url.parse(DATABASE_URL, conn_max_age=DB_CONN_MAX_AGE)
parsed_database['ENGINE'] = 'django.contrib.gis.db.backends.postgis'
if DB_SSLMODE:
    parsed_database.setdefault('OPTIONS', {})['sslmode'] = DB_SSLMODE

DATABASES = {
    'default': parsed_database,
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'Africa/Douala'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = Path(config('MEDIA_ROOT', default=str(BASE_DIR / 'media')))
SERVE_MEDIA_IN_PRODUCTION = config('SERVE_MEDIA_IN_PRODUCTION', default=True, cast=bool)
MEDIA_INLINE_CONTENT_TYPES = {
    'application/pdf',
    'image/jpeg',
    'image/png',
    'image/webp',
    'image/gif',
}
X_FRAME_OPTIONS = config('X_FRAME_OPTIONS', default='SAMEORIGIN')

STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage',
    },
}

AUTH_USER_MODEL = 'users.User'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ('apps.users.authentication.CookieJWTAuthentication',),
    'DEFAULT_PERMISSION_CLASSES': ('rest_framework.permissions.IsAuthenticated',),
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 25,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'EXCEPTION_HANDLER': 'config.exception_handler.custom_exception_handler',
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '30/minute',
        'user': '200/minute',
        'auth': '10/minute',
        'register': '5/minute',
    },
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', cast=int, default=587)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', cast=bool, default=True)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default=f'Cartronic <{EMAIL_HOST_USER}>')
FRONTEND_URL = config('FRONTEND_URL', default='https://efgh-3h6w.vercel.app')
PASSWORD_RESET_EXPOSE_LINK = config('PASSWORD_RESET_EXPOSE_LINK', default=True, cast=bool)

USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=False, cast=bool)
SESSION_COOKIE_SECURE = config('SESSION_COOKIE_SECURE', default=False, cast=bool)
CSRF_COOKIE_SECURE = config('CSRF_COOKIE_SECURE', default=False, cast=bool)
SESSION_COOKIE_SAMESITE = config('SESSION_COOKIE_SAMESITE', default='Lax')
CSRF_COOKIE_SAMESITE = config('CSRF_COOKIE_SAMESITE', default='Lax')
AUTH_COOKIE_SAMESITE = config('AUTH_COOKIE_SAMESITE', default='Lax')

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {'format': '[{levelname}] {asctime} {name} — {message}', 'style': '{'},
    },
    'handlers': {'console': {'class': 'logging.StreamHandler', 'formatter': 'verbose'}},
    'root': {'handlers': ['console'], 'level': 'WARNING'},
    'loggers': {
        'apps': {'handlers': ['console'], 'level': 'DEBUG', 'propagate': False},
        'django.request': {'handlers': ['console'], 'level': 'ERROR', 'propagate': False},
    },
}


# WebSocket / VoIP internal calls
CHANNEL_REDIS_URL = config('CHANNEL_REDIS_URL', default=os.environ.get('REDIS_URL', ''), cast=str)
if CHANNEL_REDIS_URL:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {'hosts': [CHANNEL_REDIS_URL]},
        }
    }
else:
    # Suffisant en développement/local. En production multi-instance, configurer CHANNEL_REDIS_URL.
    CHANNEL_LAYERS = {
        'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}
    }

# Paramètres ICE renvoyés au mobile. Ajouter TURN_* en production pour les réseaux mobiles stricts.
STUN_SERVERS = config('STUN_SERVERS', default='stun:stun.l.google.com:19302', cast=Csv())
TURN_SERVER_URL = config('TURN_SERVER_URL', default='', cast=str)
TURN_SERVER_USERNAME = config('TURN_SERVER_USERNAME', default='', cast=str)
TURN_SERVER_CREDENTIAL = config('TURN_SERVER_CREDENTIAL', default='', cast=str)
