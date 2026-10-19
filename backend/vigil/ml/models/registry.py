"""
Model registry — 按 settings.VIGIL_MODELS 加载模型实例。

新增 / 替换模型：
  1. 写一个继承 BaseDetectionModel 的类（实现 name、predict，可选 predict_batch）
  2. 把类的完整路径写进 .env 的 VIGIL_MODELS（逗号分隔），重启服务
  3. 上线前用 python manage.py check_model --model <类路径> 检查接口
"""

import logging

from django.conf import settings
from django.utils.module_loading import import_string

from .base import BaseDetectionModel

logger = logging.getLogger("vigil.registry")


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


def load_model(path: str, **kwargs) -> BaseDetectionModel:
    cls = import_string(path)
    if not (isinstance(cls, type) and issubclass(cls, BaseDetectionModel)):
        raise TypeError(f"{path} 不是 BaseDetectionModel 的子类")
    return cls(**kwargs)


registry = ModelRegistry()

for _path in settings.VIGIL_MODELS:
    try:
        registry.register(load_model(_path))
    except Exception as e:
        # 单个模型加载失败不影响后端启动，只是没有它的检测结果
        logger.warning("model %s not loaded: %s", _path, e)
