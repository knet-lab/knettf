"""
Rule-based threshold classifier — reference implementation.
Replace with a trained ML model (sklearn, torch, etc.) when ready.
"""

from .base import BaseDetectionModel, DetectionInput, DetectionResult


class ThresholdModel(BaseDetectionModel):
    def __init__(
        self,
        syn_ratio_threshold: float = 0.8,
        packets_per_second_threshold: float = 500.0,
        reply_ratio_threshold: float = 0.05,
    ):
        self._syn_ratio_thresh = syn_ratio_threshold
        self._pps_thresh = packets_per_second_threshold
        self._reply_ratio_thresh = reply_ratio_threshold

    @property
    def name(self) -> str:
        return "threshold_v1"

    def predict(self, flow: DetectionInput) -> DetectionResult:
        reasons: list[str] = []

        if flow.syn_ratio >= self._syn_ratio_thresh:
            reasons.append(f"syn_ratio={flow.syn_ratio:.2f}")
        if flow.packets_per_second >= self._pps_thresh:
            reasons.append(f"pps={flow.packets_per_second:.0f}")
        if flow.reply_ratio <= self._reply_ratio_thresh and flow.total_packets > 20:
            reasons.append(f"reply_ratio={flow.reply_ratio:.2f}")

        is_attack = len(reasons) > 0
        confidence = min(1.0, len(reasons) / 3.0 + 0.4) if is_attack else 0.1

        attack_type: str | None = None
        if is_attack:
            if any("syn_ratio" in r for r in reasons):
                attack_type = "syn_flood"
            elif any("pps" in r for r in reasons):
                attack_type = "flood"
            else:
                attack_type = "anomaly"

        return DetectionResult(
            model_name=self.name,
            is_attack=is_attack,
            confidence=round(confidence, 3),
            attack_type=attack_type,
            raw_output={"triggered_rules": reasons},
            explanation="; ".join(reasons) if reasons else "normal traffic",
        )
