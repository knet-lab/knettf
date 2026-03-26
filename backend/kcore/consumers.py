import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from kcore.models import KubeCluster
from common.kclient import KubeClient


class PodLogConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.cluster_id = self.scope['url_route']['kwargs']['cluster_id']
        self.namespace = self.scope['url_route']['kwargs']['namespace']
        self.pod_name = self.scope['url_route']['kwargs']['pod_name']

        # Authenticate user and check permissions here
        # For simplicity, we skip authentication in this example

        await self.accept()

        # Start sending logs
        await self.stream_logs()

    async def disconnect(self, close_code):
        # Clean up resources if needed
        pass

    async def stream_logs(self):
        cluster = await sync_to_async(KubeCluster.objects.get)(pk=self.cluster_id)
        kube = KubeClient(cluster.kubeconfig)

        log_stream = await sync_to_async(kube.core.read_namespaced_pod_log)(
            name=self.pod_name,
            namespace=self.namespace,
            follow=True,
            _preload_content=False
        )

        for raw_line in log_stream:
            line = raw_line.decode(
                'utf-8') if isinstance(raw_line, bytes) else raw_line
            await self.send(text_data=json.dumps({'log': line}))
