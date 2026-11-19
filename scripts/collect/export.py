"""从 CollectRecord 导出 CSV + 说明 txt，输出到 数据目录/exports/{nn}/。

读取的是开发库（vigil_dev）。不沿用采集时写入的标签，只用 --label 显式指定。
文件名：{time1}-{time2}.csv / .txt，time1/time2 为 Asia/Seoul 本地时间（YYYYMMDD-HHMM）。
"""

import csv
import os
import sys
from collections import Counter
from dataclasses import fields
from datetime import datetime
from zoneinfo import ZoneInfo

from knettf_common import DATA_DIR, DST_DB, REPO, check_safety, die, next_number, verify_dst

TZ = ZoneInfo("Asia/Seoul")


def _setup_django():
    sys.path.insert(0, str(REPO / "apps" / "backend"))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
    import django
    django.setup()
    # Django 连接的 vigil 库必须是开发库，否则拒绝导出（防止误连线上库）
    from django.conf import settings
    if settings.DATABASES["vigil"]["NAME"] != DST_DB:
        die(f"导出脚本的 Django 连接指向 {settings.DATABASES['vigil']['NAME']}，不是 {DST_DB}，已中止")


def kind_of(src: str, dst: str) -> str:
    if src.startswith("172.30.") or dst.startswith("172.30."):
        return "ns"
    if src.startswith("10.") and dst.startswith("10."):
        return "ew"
    return "other"


def _local(s: str) -> datetime:
    return datetime.fromisoformat(s).replace(tzinfo=TZ)


def _stamp(dt: datetime) -> str:
    return dt.strftime("%Y%m%d-%H%M")


def run(args):
    check_safety()
    verify_dst()
    _setup_django()
    from vigil.detection.base import DetectionInput
    from vigil.models import CollectRecord

    columns = [f.name for f in fields(DetectionInput)]
    t1, t2 = _local(args.since), _local(args.until)
    if t2 <= t1:
        die("--until 必须晚于 --since")

    q = CollectRecord.objects.filter(created_at__gte=t1, created_at__lt=t2).order_by("id")
    kinds, protos, rows = Counter(), Counter(), []
    for r in q.iterator():
        k = kind_of(r.src_ip, r.dst_ip)
        if args.kind != "all" and k != args.kind:
            continue
        row = {c: r.flow_input.get(c, "") for c in columns}
        row["label"] = args.label if args.label is not None else ""
        row["kind"] = k
        rows.append(row)
        kinds[k] += 1
        protos[r.protocol] += 1

    out_root = DATA_DIR / "exports"
    folder = out_root / next_number(out_root)
    folder.mkdir(parents=True, exist_ok=True)
    stem = f"{_stamp(t1)}-{_stamp(t2)}"
    csv_path, txt_path = folder / f"{stem}.csv", folder / f"{stem}.txt"

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns + ["kind"])
        w.writeheader()
        w.writerows(rows)

    types = (
        "kind: " + ", ".join(f"{k}={v}" for k, v in sorted(kinds.items()))
        + " ; protocol: " + ", ".join(f"{p}={v}" for p, v in sorted(protos.items()))
    ) if rows else "（无数据）"
    now = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(f"collect date: {now} (KST)\n")
        f.write(f"data period: from {args.since} to {args.until}\n")
        f.write(f"sum: {len(rows)}\n")
        f.write(f"types: {types}\n")

    print(f"导出 {len(rows)} 条 → {csv_path}")
    print(f"说明 → {txt_path}")
