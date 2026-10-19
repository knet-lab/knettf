import logging
from dataclasses import asdict
from pathlib import Path

from .base import BaseDetectionModel, DetectionInput, DetectionResult
from vigil.ml.ads_ml.main import _load_resources
from vigil.ml.ads_ml.utils.data_preprocessing import preprocess_data
from vigil.ml.ads_ml.utils.anomaly_detection import ad
from vigil.ml.ads_ml.utils.zero_shot_learning import zero_shot_learning

logger = logging.getLogger("vigil.ads_ml")


class AdsMLModel(BaseDetectionModel):
    """
    OCSVM + 余弦复核 + 零样本学习。
    模型资源（pipeline、攻击原型、训练集）只在构造时加载一次，之后每条流直接推理，
    不再走 ads_ml/main.py 的 main()（它每次都重新读文件并重写报告 CSV）。
    config_path 在加载时 resolve()：切换 current 软链接不影响正在运行的进程，重启后才换成新模型。
    """

    def __init__(self, config_path: str | Path | None = None):
        if config_path is None:
            from django.conf import settings
            config_path = settings.VIGIL_ADS_ML_CONFIG
        self.config_path = Path(config_path).resolve()
        self._pipeline, self._prototypes, self._X_train, _ = _load_resources(self.config_path)
        logger.info("AdsMLModel loaded from %s", self.config_path.parent)

    @property
    def name(self) -> str:
        return "ads_ml_ocsvm"

    @property
    def attack_types(self) -> list[str]:
        return list(self._prototypes)

    def predict(self, flow: DetectionInput) -> DetectionResult:
        return self.predict_batch([flow])[0]

    def predict_batch(self, flows: list[DetectionInput]) -> list[DetectionResult]:
        results = []
        for flow in flows:
            data = asdict(flow)
            data.pop("label", None)

            X_pca = preprocess_data(data, self._pipeline)
            prediction = ad(X_pca, self._pipeline["detector"], self._X_train)
            zsl_seen, zsl_preds, zsl_sims = zero_shot_learning(X_pca, prediction, self._prototypes)

            is_attack   = bool(prediction[0] == 1)
            attack_type = zsl_preds[0] if is_attack else None
            similarity  = float(zsl_sims[0])

            results.append(DetectionResult(
                model_name  = self.name,
                is_attack   = is_attack,
                confidence  = round(similarity, 4),
                attack_type = attack_type,
                explanation = f"OCSVM zsl_seen={zsl_seen[0]}" + (
                    f", zsl_sim={similarity:.3f}" if is_attack else ""
                ),
                raw_output  = {
                    "zsl_similarity":  similarity,
                    "zsl_attack":      attack_type,
                    "zsl_seen_status": zsl_seen[0],
                },
            ))
        return results
