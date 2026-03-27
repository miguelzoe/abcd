from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.core.views import HealthCheckView

router = DefaultRouter()

urlpatterns = [
    path("", include(router.urls)),
    path("health/", HealthCheckView.as_view(), name="health-check"),
]
