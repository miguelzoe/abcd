from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView, TokenBlacklistView

from apps.users.views import (
    UserViewSet, ClientViewSet, TechnicianViewSet, 
    VendorViewSet, AdministratorViewSet, CustomTokenObtainPairView
)

# Configuration du router
router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'clients', ClientViewSet, basename='client')
router.register(r'technicians', TechnicianViewSet, basename='technician')
router.register(r'vendors', VendorViewSet, basename='vendor')
router.register(r'administrators', AdministratorViewSet, basename='administrator')

urlpatterns = [
    # JWT Authentication
    path('token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    path('token/blacklist/', TokenBlacklistView.as_view(), name='token_blacklist'),
    
    # Router URLs
    path('', include(router.urls)),
]