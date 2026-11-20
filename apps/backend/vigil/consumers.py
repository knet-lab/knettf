import json
import logging

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings

logger = logging.getLogger("vigil.consumers")


class DetectorPushConsumer(AsyncWebsocketConsumer):
    """Detector Pod 推送入口 — 接收推理结果，存 DB。"""

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

    async def disconnect(self, code):
        logger.info("detector pod disconnected: %s", code)

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return
        try:
            payload = json.loads(text_data)
            results = payload.get("results", [])
            if not results:
                return
            saved = await sync_to_async(_save_results)(results)
            logger.info("detector push: saved %d result(s)", len(saved))
        except Exception as e:
            logger.warning("DetectorPushConsumer receive error: %s", e)


def _save_results(results: list) -> list:
    from vigil.models import DetectionRecord
    from vigil.response import policy_for_result, apply_action
    from vigil.detection import DetectionResult
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
