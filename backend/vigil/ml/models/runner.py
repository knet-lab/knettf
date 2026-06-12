"""
Unified runner — run all or one model on a DetectionInput.
Also provides flow_from_dict() for converting raw dicts (CSV rows, API payloads).
"""

from .base import DetectionInput, DetectionResult
from .registry import registry


def run_all(flow: DetectionInput) -> list[DetectionResult]:
    return [registry.get(name).predict(flow) for name in registry.list_models()]


def run_one(model_name: str, flow: DetectionInput) -> DetectionResult:
    return registry.get(model_name).predict(flow)


def flow_from_dict(d: dict) -> DetectionInput:
    """Convert a raw dict (from API or bridge) to DetectionInput."""
    int_fields = {
        "src_port", "dst_port",
        "total_packets", "fwd_packets", "bwd_packets",
        "syn_count", "ack_count", "fin_count", "rst_count", "psh_count", "urg_count",
        "reply_count", "forwarded_count", "drop_count",
        # boolean flags stored as 0/1
        "is_bidirectional", "is_tcp", "is_udp", "is_icmp", "is_well_known_port",
    }
    float_fields = {
        "flow_duration", "fwd_ratio", "packets_per_second",
        "iat_mean", "iat_std", "iat_min", "iat_max",
        "syn_ratio", "ack_ratio", "fin_ratio", "rst_ratio",
        "reply_ratio", "drop_ratio",
    }
    kwargs: dict = {}
    for k, v in d.items():
        if k == "model":
            continue  # API-only field, not part of DetectionInput
        if k in int_fields:
            kwargs[k] = int(v) if v not in (None, "") else 0
        elif k in float_fields:
            kwargs[k] = float(v) if v not in (None, "") else 0.0
        else:
            kwargs[k] = v if v is not None else ""
    return DetectionInput(**kwargs)
