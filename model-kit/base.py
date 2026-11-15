"""
检测模型的统一接口：输入 DetectionInput（35 个流特征），输出 DetectionResult。
新模型继承 BaseDetectionModel，并在 settings.VIGIL_MODELS 里登记。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DetectionInput:
    """
    35 flow-level features matching ebpf_35_features in the ads_ml pipeline.
    Categorical: src_ip, dst_ip, protocol (OrdinalEncoder)
    Numeric: all remaining fields
    """
    # ── categorical (OrdinalEncoder) ──────────────────────────────────────────
    src_ip: str
    dst_ip: str
    protocol: str

    # ── port ──────────────────────────────────────────────────────────────────
    src_port: int = 0
    dst_port: int = 0

    # ── timing / volume ───────────────────────────────────────────────────────
    flow_duration: float = 0.0
    total_packets: int = 0
    fwd_packets: int = 0
    bwd_packets: int = 0
    fwd_ratio: float = 0.0
    packets_per_second: float = 0.0

    # ── inter-arrival time ────────────────────────────────────────────────────
    iat_mean: float = 0.0
    iat_std: float = 0.0
    iat_min: float = 0.0
    iat_max: float = 0.0

    # ── TCP flags ─────────────────────────────────────────────────────────────
    syn_count: int = 0
    ack_count: int = 0
    fin_count: int = 0
    rst_count: int = 0
    psh_count: int = 0
    urg_count: int = 0

    syn_ratio: float = 0.0
    ack_ratio: float = 0.0
    fin_ratio: float = 0.0
    rst_ratio: float = 0.0

    # ── reply / verdict ───────────────────────────────────────────────────────
    reply_count: int = 0
    reply_ratio: float = 0.0
    forwarded_count: int = 0
    drop_count: int = 0
    drop_ratio: float = 0.0

    # ── boolean flags (stored as 0/1 int) ─────────────────────────────────────
    is_bidirectional: int = 0
    is_tcp: int = 0
    is_udp: int = 0
    is_icmp: int = 0
    is_well_known_port: int = 0

    # ── metadata (not fed to model) ───────────────────────────────────────────
    label: str = ""    # "0" = normal, "1" = attack, "" = unknown


@dataclass
class DetectionResult:
    model_name: str
    is_attack: bool
    confidence: float        # 0.0 – 1.0
    attack_type: str | None  # e.g. "syn_flood", None if normal
    raw_output: dict[str, Any] = field(default_factory=dict)
    explanation: str = ""
    recommended_action: str | None = None  # filled by cilium/policy.py


class BaseDetectionModel(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def predict(self, flow: DetectionInput) -> DetectionResult: ...

    def predict_batch(self, flows: list[DetectionInput]) -> list[DetectionResult]:
        return [self.predict(f) for f in flows]


_INT_FIELDS = {
    "src_port", "dst_port",
    "total_packets", "fwd_packets", "bwd_packets",
    "syn_count", "ack_count", "fin_count", "rst_count", "psh_count", "urg_count",
    "reply_count", "forwarded_count", "drop_count",
    "is_bidirectional", "is_tcp", "is_udp", "is_icmp", "is_well_known_port",
}
_FLOAT_FIELDS = {
    "flow_duration", "fwd_ratio", "packets_per_second",
    "iat_mean", "iat_std", "iat_min", "iat_max",
    "syn_ratio", "ack_ratio", "fin_ratio", "rst_ratio",
    "reply_ratio", "drop_ratio",
}


def flow_from_dict(d: dict) -> DetectionInput:
    """把原始 dict（API 请求、bridge 聚合结果、CSV 行）转成 DetectionInput。"""
    kwargs: dict = {}
    for k, v in d.items():
        if k == "model":
            continue  # 只用于 API 选择模型，不是特征
        if k in _INT_FIELDS:
            kwargs[k] = int(v) if v not in (None, "") else 0
        elif k in _FLOAT_FIELDS:
            kwargs[k] = float(v) if v not in (None, "") else 0.0
        else:
            kwargs[k] = v if v is not None else ""
    return DetectionInput(**kwargs)
