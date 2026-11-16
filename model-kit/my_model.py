"""
模型模板 —— 复制这个文件并改写。只需要改标了 TODO 的地方。

规则只有三条：
  1. 类继承 BaseDetectionModel
  2. name 返回一个固定的模型名（英文、不带空格）
  3. predict(flow) 输入一条流（35 个特征），返回 DetectionResult

训练好的模型文件（.joblib / .pkl 等）放在本文件旁边的 files/ 目录，在 __init__ 里加载一次。
平台创建模型时不传参数，就从 files/ 加载；自测时可以用 --model-dir 指定别的目录。
训练代码不放进这个目录（见 README 第 5 节）。
"""

from pathlib import Path

try:   # 在平台里运行
    from vigil.detection.base import BaseDetectionModel, DetectionInput, DetectionResult
except ImportError:   # 在 model-kit 里单独运行（base.py 是平台接口的副本，不要改）
    from base import BaseDetectionModel, DetectionInput, DetectionResult


FILES = Path(__file__).resolve().parent / "files"


class MyModel(BaseDetectionModel):

    def __init__(self, model_dir: str | Path | None = None):
        model_dir = model_dir or FILES
        self.model_dir = Path(model_dir)
        # TODO：在这里加载模型文件（只加载一次，之后每条流直接推理）
        # import joblib
        # self.pipeline = joblib.load(self.model_dir / "pipeline.joblib")

    @property
    def name(self) -> str:
        return "my_model_v1"  # TODO：改成模型名

    def predict(self, flow: DetectionInput) -> DetectionResult:
        # flow 的每个特征都是属性：flow.flow_duration、flow.total_packets、flow.syn_count …
        # 全部字段和单位见 README.md 的“输入：35 个特征”。
        #
        # TODO：把下面的示例规则换成模型推理
        is_attack = flow.syn_ratio > 0.8 and flow.total_packets > 20
        score = 0.9 if is_attack else 0.1

        return DetectionResult(
            model_name=self.name,
            is_attack=is_attack,                               # 必填：True / False
            confidence=float(score),                           # 必填：0.0 ~ 1.0
            attack_type="SYN flood" if is_attack else None,    # 攻击类型名；正常时为 None
            raw_output={"score": score},                       # 可选：任何想保存的中间结果（会存进数据库，必须能转成 JSON）
            explanation="syn_ratio high" if is_attack else "normal",  # 可选：一句话说明，页面上显示
        )

    # 可选：一次处理多条流（比逐条快时再实现，比如向量化推理）
    # def predict_batch(self, flows: list[DetectionInput]) -> list[DetectionResult]:
    #     ...
