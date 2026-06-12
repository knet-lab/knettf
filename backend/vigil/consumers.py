import json
from channels.generic.websocket import AsyncWebsocketConsumer


class VigilConsumer(AsyncWebsocketConsumer):
    GROUP_NAME = "vigil_detections"

    async def connect(self):
        await self.channel_layer.group_add(self.GROUP_NAME, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.GROUP_NAME, self.channel_name)

    async def detection_event(self, event):
        await self.send(text_data=json.dumps(event["data"]))
