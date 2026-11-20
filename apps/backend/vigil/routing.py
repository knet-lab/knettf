from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path("ws/detector/push/",   consumers.DetectorPushConsumer.as_asgi()),  # pyright: ignore[reportCallIssue, reportArgumentType]  channels 官方用法
]
