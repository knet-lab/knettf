import logging
from dataclasses import asdict

from .base import BaseDetectionModel, DetectionInput, DetectionResult
from vigil.ml.ads_ml.main import _load_resources, main as _run

logger = logging.getLogger("vigil.ads_ml")


class AdsMLModel(BaseDetectionModel):

    def __init__(self):
        _load_resources()
        logger.info("AdsMLModel loaded")

    @property
    def name(self) -> str:
        return "ads_ml_ocsvm"

    def predict(self, flow: DetectionInput) -> DetectionResult:
        return self.predict_batch([flow])[0]

    def predict_batch(self, flows: list[DetectionInput]) -> list[DetectionResult]:
        results = []
        for flow in flows:
            data = asdict(flow)
            data.pop("extra", None)
            data.pop("label", None)

            prediction, zsl_seen, zsl_preds, zsl_sims = _run(**data)

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
