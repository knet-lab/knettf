import asyncio
import json
import logging

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings

logger = logging.getLogger("vigil.consumers")

PING_INTERVAL = 30  # seconds — well under Cloudflare's 100s idle timeout


async def flow_queue_drainer():
    """Async task: drain bridge.flow_queue → detect → save → broadcast.
    detect_batch internally calls _broadcast() for each result via a daemon thread."""
    from vigil.bridge import flow_queue
    from vigil import services

    loop = asyncio.get_event_loop()

    while True:
        try:
            batch = await loop.run_in_executor(None, _blocking_get, flow_queue)
            if batch is None:
                continue
            try:
                results = await sync_to_async(services.detect_batch)(batch)
                n_attacks = sum(1 for r in results if r.get("is_attack"))
                logger.info("queue: %d flows → %d attack(s)", len(batch), n_attacks)
            except Exception as e:
                logger.warning("drainer process error: %s", e)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning("drainer error: %s", e)
            await asyncio.sleep(1)


def _blocking_get(q):
    try:
        return q.get(timeout=1.0)
    except Exception:
        return None


class VigilConsumer(AsyncWebsocketConsumer):
    """前端订阅 — 只接收广播，不发送。"""
    GROUP_NAME = "vigil_detections"
    _drainer_task: asyncio.Task | None = None

    async def connect(self):
        await self.channel_layer.group_add(self.GROUP_NAME, self.channel_name)
        await self.accept()
        self._ping_task = asyncio.ensure_future(self._keepalive())
        if VigilConsumer._drainer_task is None or VigilConsumer._drainer_task.done():
            VigilConsumer._drainer_task = asyncio.ensure_future(flow_queue_drainer())

    async def disconnect(self, close_code):
        self._ping_task.cancel()
        await self.channel_layer.group_discard(self.GROUP_NAME, self.channel_name)

    async def _keepalive(self):
        try:
            while True:
                await asyncio.sleep(PING_INTERVAL)
                await self.send_json({"type": "ping"})
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    async def detection_event(self, event):
        await self.send(text_data=json.dumps(event["data"]))


class DetectorPushConsumer(AsyncWebsocketConsumer):
    """Detector Pod 推送入口 — 接收推理结果，存 DB，广播前端。"""

    async def connect(self):
        if not self._auth():
            await self.close(code=4401)
            return
        await self.accept()
        logger.info("detector pod connected from %s", self.scope.get("client"))

    def _auth(self) -> bool:
        expected = getattr(settings, "VIGIL_BRIDGE_TOKEN", None)
        if not expected:
            return False
        headers = dict(self.scope.get("headers", []))
        auth = headers.get(b"authorization", b"").decode()
        logger.debug("DetectorPushConsumer auth header: %r", auth[:30] if auth else None)
        parts = auth.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1] == expected
        return False

    async def disconnect(self, close_code):
        logger.info("detector pod disconnected: %s", close_code)

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return
        try:
            payload = json.loads(text_data)
            results = payload.get("results", [])
            if not results:
                return
            from asgiref.sync import sync_to_async
            saved = await sync_to_async(_save_results)(results)
            for item in saved:
                await self.channel_layer.group_send(
                    VigilConsumer.GROUP_NAME,
                    {"type": "detection_event", "data": item},
                )
        except Exception as e:
            logger.warning("DetectorPushConsumer receive error: %s", e)


def _save_results(results: list) -> list:
    from vigil.models import DetectionRecord
    from vigil.ml.cilium import policy_for_result, apply_action
    from vigil.ml.models.base import DetectionResult
    from dataclasses import asdict

    output = []
    for r in results:
        result = DetectionResult(
            model_name  = "ads_ml_ocsvm",
            is_attack   = r.get("is_attack", False),
            confidence  = r.get("confidence", 0.0),
            attack_type = r.get("attack_type"),
            explanation = f"OCSVM zsl_seen={r.get('zsl_seen')}",
            raw_output  = r.get("zsl_top", {}),
        )
        flow_meta = {
            "src_ip":   r.get("src_ip", ""),
            "dst_ip":   r.get("dst_ip", ""),
            "src_port": r.get("src_port", 0),
            "dst_port": r.get("dst_port", 0),
            "protocol": r.get("protocol", ""),
        }
        action = policy_for_result(result, flow_meta)
        apply_action(action)

        label_raw = r.get("label", "")
        record = DetectionRecord.objects.create(
            src_ip        = flow_meta["src_ip"],
            dst_ip        = flow_meta["dst_ip"],
            src_port      = flow_meta["src_port"],
            dst_port      = flow_meta["dst_port"],
            protocol      = flow_meta["protocol"],
            flow_input    = r,
            model_name    = result.model_name,
            is_attack     = result.is_attack,
            confidence    = result.confidence,
            attack_type   = result.attack_type,
            explanation   = result.explanation,
            raw_output    = result.raw_output,
            cilium_action = action.action,
            cilium_reason = action.reason,
            label         = int(label_raw) if label_raw not in ("", None) else None,
        )
        output.append({
            **asdict(result),
            "record_id":    record.pk,
            "cilium_action": action.action,
            "cilium_reason": action.reason,
            **flow_meta,
            "created_at": record.created_at.isoformat(),
        })
    return output
