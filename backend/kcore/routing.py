from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path('ws/clusters/<int:cluster_id>/pods/<str:namespace>/<str:pod_name>/logs/',
         consumers.PodLogConsumer.as_asgi()),
]
