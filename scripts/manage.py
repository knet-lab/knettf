#!/usr/bin/env python3
"""knettf 数据脚本的唯一入口。

用法（使用仓库的 .venv，需要 psycopg2 和 Django）：
  .venv/bin/python scripts/manage.py check                          # 检查配置与两端连接
  .venv/bin/python scripts/manage.py collect sync                   # 线上 → 开发库：增量同步（定时任务也用它）
  .venv/bin/python scripts/manage.py collect reseed                 # 线上 → 开发库：整库覆盖（手动，慎用）
  .venv/bin/python scripts/manage.py collect restore [--merge] [文件…]
  .venv/bin/python scripts/manage.py collect export --since T1 --until T2 [--label 0|1] [--kind ns|ew|all]
  .venv/bin/python scripts/manage.py lab inject run <攻击类型> <秒数>   # 异常注入（默认演练）

配置来自环境变量，建议用 ~/.config/knettf/ 下的文件加载（见 scripts/knettf_common.py 的说明）。
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))

import knettf_common as common  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="manage.py", description="knettf 数据脚本统一入口")
    groups = p.add_subparsers(dest="group", required=True)

    groups.add_parser("check", help="显示配置，检查线上只读和开发库连接")

    c = groups.add_parser("collect", help="采集数据：同步、整库覆盖、还原、导出")
    cc = c.add_subparsers(dest="cmd", required=True)
    cc.add_parser("sync", help="增量同步：线上新增 → 压缩归档 → 开发库")
    cc.add_parser("reseed", help="整库覆盖：线上全量 → 压缩保存 → 清空并重新导入开发库")
    r = cc.add_parser("restore", help="归档还原为 CSV")
    r.add_argument("--merge", action="store_true", help="合并为一个 CSV，按 id 去重")
    r.add_argument("files", nargs="*", help="归档文件（默认全部）")
    e = cc.add_parser("export", help="从开发库导出 CSV + 说明 txt")
    e.add_argument("--since", required=True, help='开始时间（Asia/Seoul），如 "2026-11-20 00:00"')
    e.add_argument("--until", required=True, help="结束时间（Asia/Seoul）")
    e.add_argument("--label", choices=["0", "1"], help="给每条流打的标签；不填 = 空")
    e.add_argument("--kind", choices=["ns", "ew", "all"], default="all")

    lab = groups.add_parser("lab", help="实验环境工具")
    lc = lab.add_subparsers(dest="cmd", required=True)
    inj = lc.add_parser("inject", help="异常注入（壳子，转发给 lab/traffic/inject_attack.sh）")
    inj.add_argument("args", nargs=argparse.REMAINDER)
    return p


def _check() -> int:
    print(f"REPO      {common.REPO}")
    print(f"DATA_DIR  {common.DATA_DIR}")
    print(f"线上来源  {common.SRC['host']}:{common.SRC['port']}/{common.SRC['dbname']} 用户={common.SRC['user']}（只读）")
    print(f"开发目标  {common.DST['host']}:{common.DST['port']}/{common.DST['dbname']} 用户={common.DST['user']}（写入）")
    print(f"容量上限  {common.MAX_GB:g} GB，重叠 {common.OVERLAP} 条")
    common.check_static()
    print("✓ 静态检查通过")
    ok = True
    try:
        acc = common.src_access()
        src_ok = (not acc["can_write"]) and (not acc["superuser"]) and acc["database"] == common.SRC["dbname"]
        ok &= src_ok
        print(f"线上连接  用户={acc['user']} 库={acc['database']} 可写={'是' if acc['can_write'] else '否'} "
              f"超级用户={'是' if acc['superuser'] else '否'} → {'✓ 只读' if src_ok else '✗ 不满足只读'}")
    except Exception as ex:  # noqa: BLE001
        ok = False
        print(f"线上连接  ✗ 失败：{str(ex).strip().splitlines()[0]}")
    try:
        name = common.dst_scalar("SELECT current_database()")
        dst_ok = name == common.DST["dbname"]
        ok &= dst_ok
        print(f"开发连接  库={name} → {'✓' if dst_ok else '✗'}")
    except Exception as ex:  # noqa: BLE001
        ok = False
        print(f"开发连接  ✗ 失败：{str(ex).strip().splitlines()[0]}")
    return 0 if ok else 1


def main(argv=None):
    a = build_parser().parse_args(argv)

    if a.group == "check":
        return _check()

    if a.group == "lab":
        script = REPO / "lab" / "traffic" / "inject_attack.sh"
        return subprocess.call(["bash", str(script), *a.args], env=os.environ)

    if a.cmd == "sync":
        from collect import sync
        sync.run(a)
    elif a.cmd == "reseed":
        from collect import reseed
        reseed.run(a)
    elif a.cmd == "restore":
        from collect import restore
        restore.run(a)
    elif a.cmd == "export":
        from collect import export
        export.run(a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
