"""
从平台数据库导出检测过的流（35 个特征）为 CSV，给模型训练 / 测试用。只读，不改数据库。

在服务器上、平台后端目录里运行（需要平台的数据库配置）：
  cd <线上部署目录>/apps/backend
  ../../.venv/bin/python <仓库>/model-kit/export_flows.py \
      --since "2026-11-15 17:12" --label 0 --out ~/flows_normal.csv

--label：给导出的每条流打上的标签。"0" = 正常，"1" = 攻击，不填 = 空（未知）。
         只在确定这段时间里只有正常流量（或只有攻击流量）时使用。
--kind：只导出 ns（南北向，客户端区 172.30.*）/ ew（东西向，Pod↔Pod）/ all（默认）。
"""

import argparse
import csv
import os
import sys
from dataclasses import fields
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")

import django  # noqa: E402

django.setup()

from vigil.detection.base import DetectionInput  # noqa: E402
from vigil.models import CollectRecord, DetectionRecord  # noqa: E402

COLUMNS = [f.name for f in fields(DetectionInput)]


def kind_of(src: str, dst: str) -> str:
    if src.startswith("172.30.") or dst.startswith("172.30."):
        return "ns"
    if src.startswith("10.") and dst.startswith("10."):
        return "ew"
    return "other"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", required=True, help='本地时间（Asia/Seoul），如 "2026-11-15 17:12"')
    ap.add_argument("--until", help="本地时间，不填 = 现在")
    ap.add_argument("--label", choices=["0", "1"], help="给每条流打的标签")
    ap.add_argument("--kind", choices=["ns", "ew", "all"], default="all")
    ap.add_argument("--limit", type=int, default=0, help="最多导出多少条（0 = 不限）")
    ap.add_argument("--source", choices=["collect", "detection"], default="collect",
                    help="collect = CollectRecord（只采集模式）；detection = DetectionRecord（检测模式，每条流只取一个模型）")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    tz = ZoneInfo("Asia/Seoul")
    since = datetime.fromisoformat(a.since).replace(tzinfo=tz)
    until = datetime.fromisoformat(a.until).replace(tzinfo=tz) if a.until else None
    if a.source == "collect":
        q = CollectRecord.objects.filter(created_at__gte=since)
        if until:
            q = q.filter(created_at__lt=until)
        q = q.order_by("id")
    else:
        q = DetectionRecord.objects.filter(created_at__gte=since)
        if until:
            q = q.filter(created_at__lt=until)
        # 同一条流会被每个已加载的模型各检测一次，只取一个模型的记录，避免重复
        first_model = q.values_list("model_name", flat=True).first()
        q = q.filter(model_name=first_model).order_by("id")

    n = 0
    with open(os.path.expanduser(a.out), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS + ["kind"])
        w.writeheader()
        for r in q.iterator():
            k = kind_of(r.src_ip, r.dst_ip)
            if a.kind != "all" and k != a.kind:
                continue
            row = {c: r.flow_input.get(c, "") for c in COLUMNS}
            row["label"] = a.label if a.label is not None else row.get("label", "")
            row["kind"] = k
            w.writerow(row)
            n += 1
            if a.limit and n >= a.limit:
                break
    print(f"导出 {n} 条 → {a.out}")


if __name__ == "__main__":
    main()
