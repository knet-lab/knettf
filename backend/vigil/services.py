"""
Vigil service layer — orchestrates ML inference, Cilium feedback, and DB persistence.
"""

from dataclasses import asdict

from .ml.models import flow_from_dict, run_all, run_one, registry
from .ml.cilium import policy_for_result, apply_action
from .models import DetectionRecord


def _broadcast(record_dict: dict):
    """Push to WebSocket clients in a background thread — never blocks the request."""
    import threading

    def _send():
        try:
            from asgiref.sync import async_to_sync
            from channels.layers import get_channel_layer
            layer = get_channel_layer()
            async_to_sync(layer.group_send)(
                "vigil_detections",
                {"type": "detection_event", "data": record_dict},
            )
        except Exception:
            pass

    threading.Thread(target=_send, daemon=True).start()


def detect_flow(flow_data: dict) -> list[dict]:
    """
    Run detection on a single flow dict.
    Returns a list of result dicts (one per model that ran).
    """
    flow_data = dict(flow_data)
    model_name = flow_data.pop("model", None)
    flow = flow_from_dict(flow_data)

    results = [run_one(model_name, flow)] if model_name else run_all(flow)

    flow_meta = {
        "src_ip": flow.src_ip, "dst_ip": flow.dst_ip,
        "src_port": flow.src_port, "dst_port": flow.dst_port,
        "protocol": flow.protocol,
    }

    output = []
    for result in results:
        action = policy_for_result(result, flow_meta)
        result.recommended_action = action.action
        apply_action(action)

        record = DetectionRecord.objects.create(
            src_ip=flow.src_ip,
            dst_ip=flow.dst_ip,
            src_port=flow.src_port,
            dst_port=flow.dst_port,
            protocol=flow.protocol,
            flow_input=asdict(flow),
            model_name=result.model_name,
            is_attack=result.is_attack,
            confidence=result.confidence,
            attack_type=result.attack_type,
            explanation=result.explanation,
            raw_output=result.raw_output,
            cilium_action=action.action,
            cilium_reason=action.reason,
            label=int(flow.label) if flow.label != "" else None,
        )
        item = {
            **asdict(result),
            "record_id": record.pk,
            "cilium_action": action.action,
            "cilium_reason": action.reason,
            "src_ip": flow.src_ip,
            "dst_ip": flow.dst_ip,
            "src_port": flow.src_port,
            "dst_port": flow.dst_port,
            "protocol": flow.protocol,
            "created_at": record.created_at.isoformat(),
        }
        _broadcast(item)
        output.append(item)
    return output


def detect_batch(flows_data: list[dict], model_name: str | None = None) -> list[dict]:
    results = []
    for d in flows_data:
        if model_name:
            d = {**d, "model": model_name}
        results.extend(detect_flow(d))
    return results


def get_stats() -> dict:
    from django.db.models import Count
    from .serializers import DetectionRecordSerializer

    total = DetectionRecord.objects.count()
    attacks = DetectionRecord.objects.filter(is_attack=True).count()
    by_type = list(
        DetectionRecord.objects.filter(is_attack=True)
        .values("attack_type")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    by_model = list(
        DetectionRecord.objects.values("model_name").annotate(count=Count("id"))
    )
    recent = DetectionRecord.objects.all()[:10]

    return {
        "total": total,
        "attacks": attacks,
        "normal": total - attacks,
        "attack_rate": round(attacks / total, 4) if total else 0.0,
        "by_attack_type": by_type,
        "by_model": by_model,
        "recent": DetectionRecordSerializer(recent, many=True).data,
    }


def list_models() -> list[str]:
    return registry.list_models()
