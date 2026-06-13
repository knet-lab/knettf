from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path("ws/vigil/",           consumers.VigilConsumer.as_asgi()),
    path("ws/detector/push/",   consumers.DetectorPushConsumer.as_asgi()),
]
