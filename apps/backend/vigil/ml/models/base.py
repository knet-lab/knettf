"""
Base interface for all AI detection models.
Every model adapter must implement this abstract class.
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
