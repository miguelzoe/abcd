from django.urls import re_path
from apps.reservations import consumers

websocket_urlpatterns = [
    re_path(r'^ws/trip/(?P<reservation_id>\d+)/$', consumers.TripTrackingConsumer.as_asgi()),
]
