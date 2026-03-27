from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

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

    # Core / Health
    path('', include('apps.core.urls')),
]

# Servir les fichiers media en développement
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)