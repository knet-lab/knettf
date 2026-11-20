"""
上线前检查检测模型的接口：能否加载、name、predict / predict_batch 的返回类型。
只检查接口，不评判检测结果好坏；不写数据库、不影响正在运行的服务。

  python manage.py check_model                                        # settings.VIGIL_MODELS 里的全部模型
  python manage.py check_model --model vigil.detection.ads_ml.AdsMLModel \\
      --config <路径>/config.yaml                                     # ads_ml：指定别的配置文件
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from vigil.detection.base import BaseDetectionModel, DetectionInput, DetectionResult
from vigil.detection.registry import load_model

SAMPLE = DetectionInput(src_ip="192.168.100.20", dst_ip="192.168.100.210", protocol="TCP",
                        src_port=50000, dst_port=80, total_packets=10, fwd_packets=10, is_tcp=1)


def check(model: BaseDetectionModel) -> list[str]:
    errors = []
    if not isinstance(model.name, str) or not model.name:
        errors.append("name 必须是非空字符串")
    r = model.predict(SAMPLE)
    if not isinstance(r, DetectionResult):
        return errors + [f"predict 返回 {type(r).__name__}，应为 DetectionResult"]
    if r.model_name != model.name:
        errors.append(f"DetectionResult.model_name={r.model_name!r} 与 name={model.name!r} 不一致")
    if not isinstance(r.is_attack, bool):
        errors.append("is_attack 必须是 bool")
    if not isinstance(r.confidence, float) or not 0.0 <= r.confidence <= 1.0:
        errors.append(f"confidence 必须是 0~1 的 float，实际 {r.confidence!r}")
    if r.attack_type is not None and not isinstance(r.attack_type, str):
        errors.append("attack_type 必须是 str 或 None")
    if not isinstance(r.raw_output, dict):
        errors.append("raw_output 必须是 dict（会存进 JSON 字段）")
    batch = model.predict_batch([SAMPLE, SAMPLE])
    if len(batch) != 2:
        errors.append(f"predict_batch 输入 2 条返回 {len(batch)} 条")
    return errors


class Command(BaseCommand):
    help = "检查检测模型的接口（不写库）"

    def add_arguments(self, parser):
        parser.add_argument("--model", action="append", help="模型类的完整路径，可多次给出；默认 settings.VIGIL_MODELS")
        parser.add_argument("--config", help="传给模型构造函数的 config_path（ads_ml 用来指定模型目录）")

    def handle(self, *args, model, config, **opts):
        failed = False
        for path in model or settings.VIGIL_MODELS:
            try:
                m = load_model(path, **({"config_path": config} if config else {}))
                errors = check(m)
            except Exception as e:
                errors, m = [f"{type(e).__name__}: {e}"], None
            if errors:
                failed = True
                self.stdout.write(self.style.ERROR(f"✗ {path}"))
                for e in errors:
                    self.stdout.write(f"    {e}")
            elif m is not None:   # 没有错误时 m 一定已加载
                self.stdout.write(self.style.SUCCESS(f"✓ {path}（name={m.name}）"))
        if failed:
            raise CommandError("有模型未通过接口检查")
