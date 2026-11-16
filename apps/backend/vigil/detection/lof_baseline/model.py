"""
lof_baseline_v1 —— 零正样本（只用正常流训练）的 LOF 异常检测模型。实验用，不在 Git 里。

接口与 model-kit/my_model.py 相同，可直接用 try_my_model.py / check_model 检查。
只用行为特征，不用 IP / 端口 / 协议字符串（避免靠地址区分）。
"""

import math
import os
from pathlib import Path

try:
    from vigil.detection.base import BaseDetectionModel, DetectionInput, DetectionResult
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "model-kit"))
    from base import BaseDetectionModel, DetectionInput, DetectionResult

MODEL_DIR_ENV = "LOF_BASELINE_V1_DIR"

# 35 个特征去掉 IP、端口、协议字符串和端口派生特征
EXCLUDE = {"src_ip", "dst_ip", "protocol", "src_port", "dst_port", "is_well_known_port"}
FEATURES = [f for f in DetectionInput.__dataclass_fields__ if f not in EXCLUDE]


def to_matrix(flows):
    import numpy as np
    X = np.array([[float(getattr(f, c) or 0.0) for c in FEATURES] for f in flows], dtype=float)
    return np.sign(X) * np.log1p(np.abs(X))


class LofBaselineModel(BaseDetectionModel):

    def __init__(self, model_dir=None):
        import joblib
        model_dir = Path(model_dir or os.environ.get(MODEL_DIR_ENV) or Path(__file__).parent / "files")
        b = joblib.load(model_dir / "lof.joblib")
        self.scaler, self.lof, self.threshold, self.scale = b["scaler"], b["lof"], b["threshold"], b["scale"]

    @property
    def name(self) -> str:
        return "lof_baseline_v1"

    def _result(self, s: float) -> DetectionResult:
        # s 越小越异常；低于阈值判为攻击
        is_attack = bool(s < self.threshold)
        z = (self.threshold - s) / self.scale
        conf = 1.0 / (1.0 + math.exp(-max(min(z, 50.0), -50.0)))
        return DetectionResult(
            model_name=self.name, is_attack=is_attack,
            confidence=float(conf if is_attack else 1.0 - conf),
            attack_type="Anomaly" if is_attack else None,
            raw_output={"score": float(s), "threshold": float(self.threshold)},
            explanation="LOF score below normal threshold" if is_attack else "normal",
        )

    def predict_batch(self, flows):
        scores = self.lof.score_samples(self.scaler.transform(to_matrix(flows)))
        return [self._result(float(s)) for s in scores]

    def predict(self, flow):
        return self.predict_batch([flow])[0]
