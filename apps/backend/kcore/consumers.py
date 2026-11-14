import asyncio
import json
import threading
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from kcore.models import KubeCluster
from common.kclient import KubeClient


class PodLogConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.cluster_id = self.scope['url_route']['kwargs']['cluster_id']
        self.namespace = self.scope['url_route']['kwargs']['namespace']
        self.pod_name = self.scope['url_route']['kwargs']['pod_name']
        self._streaming = True

        await self.accept()
        await self.stream_logs()

    async def disconnect(self, close_code):
        self._streaming = False

    async def stream_logs(self):
        cluster = await sync_to_async(KubeCluster.objects.get)(pk=self.cluster_id)
        kube = KubeClient(cluster.kubeconfig)

        queue = asyncio.Queue()
        loop = asyncio.get_event_loop()

        def producer():
            try:
                log_stream = kube.core.read_namespaced_pod_log(
                    name=self.pod_name,
                    namespace=self.namespace,
                    follow=True,
                    _preload_content=False,
                )
                for raw_line in log_stream:
                    if not self._streaming:
                        break
                    line = raw_line.decode('utf-8') if isinstance(raw_line, bytes) else raw_line
                    loop.call_soon_threadsafe(queue.put_nowait, line)
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        threading.Thread(target=producer, daemon=True).start()

        while True:
            line = await queue.get()
            if line is None:
                break
            await self.send(text_data=json.dumps({'log': line}))
