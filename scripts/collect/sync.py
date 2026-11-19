"""增量同步：线上新增记录 → 压缩归档 → 开发库。每小时定时任务调用。

每次从开发库的最大 id 往回多取 OVERLAP 条（覆盖事务延迟提交的记录）；
开发库里 id > 起点 的部分先删再写，同一事务，重复运行安全。
"""

import gzip

from knettf_common import (DATA_DIR, MAX_GB, OVERLAP, TABLE, check_safety, dst_script, dst_scalar,
                           enforce_retention, src_copy_out, verify_dst, verify_src)


def run(_args=None):
    check_safety()
    verify_src()   # 线上账号必须只读
    verify_dst()   # 写入目标必须是 vigil_dev
    dst_max = int(dst_scalar(f"SELECT COALESCE(MAX(id), 0) FROM {TABLE}"))
    from_id = dst_max - OVERLAP if dst_max > OVERLAP else 0

    print(f"1/4 读取线上 id > {from_id}（只读）")
    data = src_copy_out(f"COPY (SELECT * FROM {TABLE} WHERE id > {from_id} ORDER BY id) TO STDOUT WITH CSV HEADER")
    lines = data.splitlines()
    rows = len(lines) - 1  # 第一行是表头
    if rows <= 0:
        print("没有新记录，已结束")
        return
    to_id = int(lines[-1].split(b",")[0])

    archive = DATA_DIR / "increments" / f"collect-{from_id}-{to_id}.csv.gz"
    print(f"2/4 压缩归档 {rows} 条 → {archive}")
    with gzip.open(archive, "wb") as f:
        f.write(data)

    print("3/4 写入开发库（替换 id > 起点 的部分，同一事务）")
    script = b"".join([
        b"BEGIN;\n",
        f"DELETE FROM {TABLE} WHERE id > {from_id};\n".encode(),
        f"COPY {TABLE} FROM STDIN WITH CSV HEADER;\n".encode(),
        data if data.endswith(b"\n") else data + b"\n",
        b"\\.\n",
        f"SELECT setval(pg_get_serial_sequence('{TABLE}', 'id'), (SELECT COALESCE(MAX(id), 1) FROM {TABLE}));\n".encode(),
        b"COMMIT;\n",
    ])
    dst_script(script)

    print("4/4 核对")
    new_max = int(dst_scalar(f"SELECT COALESCE(MAX(id), 0) FROM {TABLE}"))
    if new_max < to_id:
        raise SystemExit(f"❌ 开发库最大 id（{new_max}）小于本批结束 id（{to_id}）")
    print(f"    开发库最大 id = {new_max}，本批结束 id = {to_id}，本批 {rows} 条")

    kept = enforce_retention(DATA_DIR / "increments", "collect-*.csv.gz")
    print(f"完成。归档目录约 {kept / 1024 / 1024:.1f}MB（上限 {MAX_GB:g}GB）")
