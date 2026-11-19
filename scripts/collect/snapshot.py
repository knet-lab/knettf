"""整库快照：线上采集表 pg_dump（只读）→ 压缩保存 → 导入开发库。手动使用。"""

import gzip
import re
from datetime import datetime

from knettf_common import (DATA_DIR, TABLE, check_safety, dst_script, dst_scalar, src_dump_table,
                           verify_dst, verify_src)


def _dump_row_count(dump: bytes) -> int:
    """数出 pg_dump 里 COPY 数据块的行数（不含 \\. 结束行）。"""
    m = re.search(rb"^COPY public\.%s [^\n]*FROM stdin;\n(.*?)\n\\\.\n" % TABLE.encode(), dump, re.S | re.M)
    if not m:
        return 0
    body = m.group(1)
    return body.count(b"\n") + (1 if body else 0)


def run(_args=None):
    check_safety()
    verify_src()
    verify_dst()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = DATA_DIR / "snapshots" / f"collectrecord-{stamp}.sql.gz"

    print("1/3 线上整库导出（只读）→", out)
    dump = src_dump_table()
    if not dump.strip():
        raise SystemExit("❌ 导出为空，已中止")
    with gzip.open(out, "wb") as f:
        f.write(dump)

    print("2/3 导入开发库（只覆盖采集表）")
    dst_script(dump)

    print("3/3 核对：开发库行数应等于导出的行数")
    dump_n = _dump_row_count(dump)
    dst_n = int(dst_scalar(f"SELECT count(*) FROM {TABLE}"))
    if dump_n != dst_n:
        raise SystemExit(f"❌ 开发库 {dst_n} 条，导出 {dump_n} 条，不一致")
    print(f"完成：{dst_n} 条。快照：{out}")
