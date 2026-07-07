from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from config.media_views import serve_media_file

urlpatterns = [
    # Django Admin
    path('admin/', admin.site.urls),
    
    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    
    # API Users (inclut JWT auth)
    path('api/', include('apps.users.urls')),
    
    # API Reservations
    path('api/', include('apps.reservations.urls')),
    
    # API Vehicles
    path('api/', include('apps.vehicles.urls')),
    
    # API Marketplace
    path('api/', include('apps.marketplace.urls')),

    # API Payments
    path('api/', include('apps.payments.urls')),

    # API Admin Panel
    path('api/admin/', include('apps.admin_panel.urls')),

    # Core / health check
    path('api/', include('apps.core.urls')),

    # API Voice / WebRTC
    path('api/', include('apps.voice_calls.urls')),
]

# Servir les fichiers media uploadés. Nécessaire sur Render avec DEBUG=False
# pour permettre la visualisation des documents techniciens dans l'admin.
if getattr(settings, 'SERVE_MEDIA_IN_PRODUCTION', False) or settings.DEBUG:
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve_media_file, name='media-file'),
    ]

# Servir les fichiers statiques en développement uniquement.
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
