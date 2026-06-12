"""
Model registry — register all model instances here.

To add a new model:
  1. Write a class extending BaseDetectionModel
  2. Import it below and call registry.register(MyModel())
"""

from .base import BaseDetectionModel
from .example_threshold import ThresholdModel


def _load_ads_ml():
    try:
        from .ads_ml_model import AdsMLModel
        return AdsMLModel()
    except Exception as e:
        import logging
        logging.getLogger("vigil.registry").warning("AdsMLModel not loaded: %s", e)
        return None


class ModelRegistry:
    def __init__(self) -> None:
        self._models: dict[str, BaseDetectionModel] = {}

    def register(self, model: BaseDetectionModel) -> None:
        self._models[model.name] = model

    def get(self, name: str) -> BaseDetectionModel:
        if name not in self._models:
            raise KeyError(f"Model '{name}' not registered. Available: {list(self._models)}")
        return self._models[name]

    def list_models(self) -> list[str]:
        return list(self._models.keys())


registry = ModelRegistry()

# ── Register models here ──────────────────────────────────────────────────────
registry.register(ThresholdModel())

_ads = _load_ads_ml()
if _ads:
    registry.register(_ads)
