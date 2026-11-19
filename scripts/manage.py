#!/usr/bin/env python3
"""knettf 数据脚本的唯一入口。

用法：
  python scripts/manage.py check                              # 显示配置并做安全检查
  python scripts/manage.py collect sync                       # 增量同步（每小时定时任务）
  python scripts/manage.py collect snapshot                   # 整库快照（手动）
  python scripts/manage.py collect restore [--merge] [文件…]    # 归档还原为 CSV
  python scripts/manage.py collect export --since T1 --until T2 [--label 0|1] [--kind ns|ew|all]
  python scripts/manage.py lab inject run <攻击类型> <秒数>      # 异常注入（默认演练，见 lab/traffic/inject_attack.sh）

数据目录由 KNETTF_DATA_DIR 控制（默认 ~/knettf-data），各项配置见 scripts/knettf_common.py。
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))

import knettf_common as common # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="manage.py", description="knettf 数据脚本统一入口")
    groups = p.add_subparsers(dest="group", required=True)

    groups.add_parser("check", help="显示配置并做安全检查")

    c = groups.add_parser("collect", help="线上采集数据：同步、快照、还原、导出")
    cc = c.add_subparsers(dest="cmd", required=True)
    cc.add_parser("sync", help="增量同步 + 压缩归档（写入开发库）")
    cc.add_parser("snapshot", help="整库快照（压缩）并导入开发库")
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


def main(argv=None):
    a = build_parser().parse_args(argv)

    if a.group == "check":
        print(f"REPO       {common.REPO}")
        print(f"DATA_DIR   {common.DATA_DIR}")
        print(f"线上库     {common.PG_CONTAINER} / {common.SRC_DB}（读取，用户 {common.SRC_USER}）")
        print(f"开发库     {common.PG_CONTAINER} / {common.DST_DB}（写入，用户 {common.DST_USER}）")
        print(f"容量上限   {common.MAX_GB:g} GB，重叠 {common.OVERLAP} 条")
        common.check_safety()
        print("✓ 静态安全检查通过")
        # 连接检查（需要容器和数据库可用）
        acc = common.src_access()
        ok_src = not acc["can_write"] and not acc["superuser"] and acc["database"] == common.SRC_DB
        print(f"线上连接   用户={acc['user']} 库={acc['database']} 可写={'是' if acc['can_write'] else '否'} "
              f"超级用户={'是' if acc['superuser'] else '否'} → {'✓ 只读' if ok_src else '✗ 不满足只读，同步/快照会拒绝运行'}")
        dst_name = common.dst_scalar("SELECT current_database()")
        print(f"开发连接   库={dst_name} → {'✓' if dst_name == common.DST_DB else '✗'}")
        return 0 if ok_src else 1

    if a.group == "lab":
        script = REPO / "lab" / "traffic" / "inject_attack.sh"
        return subprocess.call(["bash", str(script), *a.args], env=os.environ)

    # collect
    if a.cmd == "sync":
        from collect import sync
        sync.run(a)
    elif a.cmd == "snapshot":
        from collect import snapshot
        snapshot.run(a)
    elif a.cmd == "restore":
        from collect import restore
        restore.run(a)
    elif a.cmd == "export":
        from collect import export
        export.run(a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
