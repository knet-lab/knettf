"""检测模型：统一接口（base）、模型注册表（registry）、具体模型（ads_ml 等）。"""

from .base import BaseDetectionModel, DetectionInput, DetectionResult, flow_from_dict
from .registry import registry, run_all, run_one

__all__ = [
    "BaseDetectionModel", "DetectionInput", "DetectionResult", "flow_from_dict",
    "registry", "run_all", "run_one",
]
