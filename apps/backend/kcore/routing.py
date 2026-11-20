from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path('ws/clusters/<int:cluster_id>/pods/<str:namespace>/<str:pod_name>/logs/',  # pyright: ignore[reportCallIssue]  channels 官方用法
         consumers.PodLogConsumer.as_asgi()),  # pyright: ignore[reportArgumentType]
]
