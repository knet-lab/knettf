"""
在自己电脑上测试模型：检查接口是否符合平台要求，并在 CSV 数据上跑一遍看结果。
不需要 Django、数据库、集群。

  python try_my_model.py                                         # 默认：my_model.py 的 MyModel + 样本数据
  python try_my_model.py --model my_model.py:MyModel --model-dir ./my_model_files \
                         --data data/normal_baseline_sample.csv

CSV 至少要有 35 个特征列（列名见 README.md）；有 label 列（"0" 正常 / "1" 攻击）时会算准确率。
"""

import argparse
import collections
import csv
import importlib.util
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from base import BaseDetectionModel, DetectionInput, DetectionResult, flow_from_dict  # noqa: E402

FEATURES = list(DetectionInput.__dataclass_fields__)


def load_class(spec: str):
    file, cls = spec.split(":")
    path = (HERE / file) if not Path(file).is_absolute() else Path(file)
    sys.path.insert(0, str(path.parent))
    s = importlib.util.spec_from_file_location(path.stem, path)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return getattr(m, cls)


def check_interface(model) -> list[str]:
    """与平台上线前的检查（manage.py check_model）相同的规则。"""
    errors = []
    if not isinstance(model, BaseDetectionModel):
        return ["模型类必须继承 BaseDetectionModel"]
    if not isinstance(model.name, str) or not model.name or " " in model.name:
        errors.append("name 必须是非空、不带空格的字符串")
    sample = DetectionInput(src_ip="172.30.1.11", dst_ip="10.0.3.230", protocol="TCP",
                            src_port=50000, dst_port=8080, total_packets=10, fwd_packets=6,
                            bwd_packets=4, flow_duration=1_000_000.0, is_tcp=1)
    r = model.predict(sample)
    if not isinstance(r, DetectionResult):
        return errors + [f"predict 返回 {type(r).__name__}，应为 DetectionResult"]
    if r.model_name != model.name:
        errors.append(f"DetectionResult.model_name={r.model_name!r} 与 name={model.name!r} 不一致")
    if not isinstance(r.is_attack, bool):
        errors.append(f"is_attack 必须是 bool（不能是 numpy.bool_ / int），实际 {type(r.is_attack).__name__}")
    if not isinstance(r.confidence, float) or not 0.0 <= r.confidence <= 1.0:
        errors.append(f"confidence 必须是 0~1 的 float（不能是 numpy.float64），实际 {r.confidence!r}")
    if r.attack_type is not None and not isinstance(r.attack_type, str):
        errors.append("attack_type 必须是 str 或 None")
    if not isinstance(r.raw_output, dict):
        errors.append("raw_output 必须是 dict")
    else:
        import json
        try:
            json.dumps(r.raw_output)
        except TypeError as e:
            errors.append(f"raw_output 必须能转成 JSON（numpy 数值请先 float()/int()）：{e}")
    if len(model.predict_batch([sample, sample])) != 2:
        errors.append("predict_batch 输入 2 条应返回 2 条")
    return errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="my_model.py:MyModel", help="文件:类名")
    ap.add_argument("--model-dir", default=None, help="传给模型构造函数的 model_dir")
    ap.add_argument("--data", default=str(HERE / "data/normal_baseline_sample.csv"))
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    cls = load_class(a.model)
    model = cls(model_dir=a.model_dir) if a.model_dir else cls()

    print("== 1. 接口检查")
    errors = check_interface(model)
    if errors:
        for e in errors:
            print("   ✗", e)
        sys.exit(1)
    print(f"   ✓ 通过（模型名 {model.name}）")

    print(f"\n== 2. 在数据上运行：{a.data}")
    with open(a.data, newline="") as f:
        rows = list(csv.DictReader(f))
    if a.limit:
        rows = rows[: a.limit]
    missing = [c for c in FEATURES if c not in rows[0]]
    if missing:
        sys.exit(f"   ✗ CSV 缺少列：{missing}")
    flows = [flow_from_dict({k: r[k] for k in FEATURES}) for r in rows]

    t0 = time.perf_counter()
    results = model.predict_batch(flows)
    dt = time.perf_counter() - t0
    print(f"   {len(flows)} 条流，耗时 {dt:.2f}s（平均 {1000 * dt / max(len(flows), 1):.2f} ms/条）")

    n_attack = sum(r.is_attack for r in results)
    print(f"   判为攻击：{n_attack}/{len(results)}（{100 * n_attack / len(results):.1f}%）")
    types = collections.Counter(r.attack_type for r in results if r.is_attack)
    if types:
        print("   攻击类型：", dict(types.most_common(8)))

    labeled = [(r, row["label"]) for r, row in zip(results, rows) if row.get("label") in ("0", "1")]
    if labeled:
        correct = sum(r.is_attack == (lab == "1") for r, lab in labeled)
        print(f"   有标签 {len(labeled)} 条，准确率 {100 * correct / len(labeled):.1f}%")
    if rows and "kind" in rows[0]:
        print("   按流量类型：")
        by = collections.defaultdict(list)
        for r, row in zip(results, rows):
            by[row["kind"]].append(r.is_attack)
        names = {"ns": "南北向（外部客户端→集群）", "ew": "东西向（服务之间）", "other": "其他"}
        for k, v in by.items():
            print(f"     {names.get(k, k)}：{len(v)} 条，判为攻击 {100 * sum(v) / len(v):.1f}%")


if __name__ == "__main__":
    main()
