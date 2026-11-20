"""
flow_transformer_v1 —— 只用正常流训练的 Transformer 异常检测（重构误差）。实验模型的推理代码。

网络：每个数值特征一个 token，加一个 CLS token，经过 2 层 pre-norm Transformer 编码器，
CLS 输出压缩到 8 维瓶颈，再解码回全部特征。异常分数 = 重构误差的均值，超过阈值判为攻击。

推理只用 numpy（平台没有 torch），参数在 files/weights.npz，预处理与阈值在 files/prep.json。
训练代码不在仓库里（experiments/flow_transformer/，本地排除）。

不使用 IP、端口、协议字符串，以及 Cilium 策略相关的 reply / forwarded / drop 特征（规范第 7 节待定）。
"""

import json
import math
import os
from pathlib import Path

import numpy as np

try:
    from vigil.detection.base import BaseDetectionModel, DetectionInput, DetectionResult
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[5] / "model-kit"))
    from base import BaseDetectionModel, DetectionInput, DetectionResult

MODEL_DIR_ENV = "FLOW_TRANSFORMER_V1_DIR"
FILES = Path(__file__).resolve().parent / "files"

NAME = "flow_transformer_v1"


def _layer_norm(x, g, b, eps=1e-5):
    mu = x.mean(axis=-1, keepdims=True)
    var = x.var(axis=-1, keepdims=True)
    return (x - mu) / np.sqrt(var + eps) * g + b


def _attention(a, p, n_heads):
    b, t, d = a.shape
    dh = d // n_heads

    def split(x):
        return x.reshape(b, t, n_heads, dh).transpose(0, 2, 1, 3)

    q = split(a @ p["q_w"] + p["q_b"])
    k = split(a @ p["k_w"] + p["k_b"])
    v = split(a @ p["v_w"] + p["v_b"])
    s = q @ k.transpose(0, 1, 3, 2) / math.sqrt(dh)
    s = s - s.max(axis=-1, keepdims=True)
    e = np.exp(s)
    w = e / e.sum(axis=-1, keepdims=True)
    o = (w @ v).transpose(0, 2, 1, 3).reshape(b, t, d)
    return o @ p["o_w"] + p["o_b"]


class FlowTransformerV1(BaseDetectionModel):

    def __init__(self, model_dir=None):
        model_dir = Path(model_dir or os.environ.get(MODEL_DIR_ENV) or FILES)
        with open(model_dir / "prep.json") as f:
            prep = json.load(f)
        w = np.load(model_dir / "weights.npz")

        self.features = prep["features"]
        self.mean = np.asarray(prep["mean"], dtype=np.float64)
        self.std = np.asarray(prep["std"], dtype=np.float64)
        self.threshold = float(prep["threshold"])
        self.scale = float(prep["score_scale"])
        self.n_heads = int(prep["n_heads"])
        self.n_layers = int(prep["n_layers"])

        self.num_w = w["num_w"]
        self.num_b = w["num_b"]
        self.cls = w["cls"]
        self.pos = w["pos"]
        self.blocks = []
        for i in range(self.n_layers):
            pre = f"blk{i}_"
            self.blocks.append({
                k[len(pre):]: w[k] for k in w.files if k.startswith(pre)
            })
        self.lnf_g, self.lnf_b = w["lnf_g"], w["lnf_b"]
        self.enc_w, self.enc_b = w["enc_w"], w["enc_b"]
        self.dec_w, self.dec_b = w["dec_w"], w["dec_b"]

    @property
    def name(self) -> str:
        return NAME

    def _to_matrix(self, flows):
        X = np.array([[float(getattr(f, c) or 0.0) for c in self.features] for f in flows], dtype=np.float64)
        X = np.sign(X) * np.log1p(np.abs(X))
        return (X - self.mean) / self.std

    def _reconstruction_error(self, X):
        b = X.shape[0]
        tok = X[:, :, None] * self.num_w + self.num_b                         # [B, F, d]
        h = np.concatenate([np.broadcast_to(self.cls, (b, 1, self.cls.shape[-1])), tok], axis=1)
        h = h + self.pos
        for p in self.blocks:
            a = _layer_norm(h, p["ln1_g"], p["ln1_b"])
            h = h + _attention(a, p, self.n_heads)
            f = _layer_norm(h, p["ln2_g"], p["ln2_b"])
            f = np.maximum(f @ p["ff1_w"] + p["ff1_b"], 0.0)
            h = h + f @ p["ff2_w"] + p["ff2_b"]
        h = _layer_norm(h, self.lnf_g, self.lnf_b)
        z = h[:, 0] @ self.enc_w + self.enc_b
        rec = z @ self.dec_w + self.dec_b
        return np.mean((rec - X) ** 2, axis=1)

    def _result(self, s: float) -> DetectionResult:
        is_attack = bool(s > self.threshold)
        z = (s - self.threshold) / self.scale
        conf = 1.0 / (1.0 + math.exp(-max(min(z, 50.0), -50.0)))
        return DetectionResult(
            model_name=self.name,
            is_attack=is_attack,
            confidence=float(conf if is_attack else 1.0 - conf),
            attack_type="Anomaly" if is_attack else None,
            raw_output={"score": float(s), "threshold": float(self.threshold)},
            explanation="reconstruction error above normal threshold" if is_attack else "normal",
        )

    def predict(self, flow):
        return self.predict_batch([flow])[0]

    def predict_batch(self, flows):
        if not flows:
            return []
        scores = self._reconstruction_error(self._to_matrix(flows))
        return [self._result(float(s)) for s in scores]
