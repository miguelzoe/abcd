from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenVerifyView

from apps.users.views import (
    UserViewSet, ClientViewSet, TechnicianViewSet,
    VendorViewSet, AdministratorViewSet,
    CookieTokenObtainPairView, CookieTokenRefreshView, CookieTokenBlacklistView,
    ForgotPasswordView, ResetPasswordView,
)

# Configuration du router
router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'clients', ClientViewSet, basename='client')
router.register(r'technicians', TechnicianViewSet, basename='technician')
router.register(r'vendors', VendorViewSet, basename='vendor')
router.register(r'administrators', AdministratorViewSet, basename='administrator')

urlpatterns = [
    # JWT Authentication (cookie-aware)
    path('token/', CookieTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', CookieTokenRefreshView.as_view(), name='token_refresh'),
    path('token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    path('token/blacklist/', CookieTokenBlacklistView.as_view(), name='token_blacklist'),

    # Password reset
    path('auth/forgot-password/', ForgotPasswordView.as_view(), name='auth-forgot-password'),
    path('auth/reset-password/', ResetPasswordView.as_view(), name='auth-reset-password'),
    
    # Router URLs
    path('', include(router.urls)),
]