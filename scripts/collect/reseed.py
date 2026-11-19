"""整库覆盖（reseed）：线上采集表全量读取（只读）→ 压缩保存 → 清空开发库采集表后重新导入。

用于：开发库数据损坏、需要和线上完全对齐、首次建立开发副本。
会覆盖开发库（pg-dev / vigil_dev）里的采集表，不影响线上。
"""

import gzip
from datetime import datetime

from knettf_common import (DATA_DIR, TABLE, check_static, dst_replace_all, dst_scalar,
                           enforce_retention, src_copy_out, verify_dst, verify_src)


def run(_args=None):
    check_static()
    verify_src()
    verify_dst()

    print("1/3 线上全量读取（只读）")
    data = src_copy_out(f"COPY (SELECT * FROM {TABLE} ORDER BY id) TO STDOUT WITH CSV HEADER")
    rows = len(data.splitlines()) - 1
    if rows <= 0:
        raise SystemExit("❌ 线上采集表为空，已中止（为避免清空开发库）")

    out = DATA_DIR / "snapshots" / f"reseed-{datetime.now().strftime('%Y%m%d-%H%M%S')}.csv.gz"
    with gzip.open(out, "wt", encoding="utf-8", newline="") as f:
        f.write(data)
    print(f"    已保存 {rows} 条 → {out}")

    print("2/3 清空开发库采集表并导入")
    dst_replace_all(data)

    print("3/3 核对")
    dst_n = int(dst_scalar(f"SELECT COUNT(*) FROM {TABLE}"))
    if dst_n != rows:
        raise SystemExit(f"❌ 开发库 {dst_n} 条，导出 {rows} 条，不一致")
    kept = enforce_retention(DATA_DIR / "snapshots", "reseed-*.csv.gz")
    print(f"完成：开发库 {dst_n} 条。快照目录约 {kept / 1024 / 1024:.1f}MB")
