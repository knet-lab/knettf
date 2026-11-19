"""scripts 公共配置、连接与安全检查。

架构（见 docs/LAYOUT.md 与 docs/ONBOARDING.md）：
  - 线上库：容器 pg，端口 5432，库 vigil。脚本只用只读账号 knettf_reader 通过 TCP+密码读取。
  - 开发库：容器 pg-dev，端口 5433（只监听 127.0.0.1），库 vigil_dev，账号 knettf_dev。脚本只写这里。
  - 所有连接都是 TCP + 密码（psycopg2），不使用 docker exec。

配置来自环境变量（由 ~/.config/knettf/*.env 提供，权限 600，不在仓库里）：
  KNETTF_SRC_HOST / _PORT / _DB / _USER / _PASSWORD    线上只读来源（默认 127.0.0.1:5432 vigil knettf_reader）
  KNETTF_DST_HOST / _PORT / _DB / _USER / _PASSWORD    开发库写入目标（默认 127.0.0.1:5433 vigil_dev knettf_dev）
  KNETTF_DATA_DIR      数据目录（快照、归档、导出结果），默认 ~/knettf-data
  KNETTF_MAX_GB        归档目录容量上限，默认 20
  KNETTF_OVERLAP       增量同步的重叠条数，默认 5000

安全规则（每次运行都检查）：
  - 写入目标必须是 vigil_dev，且端口不是线上的 5432，主机是本机。
  - 线上连接账号不能有 INSERT/UPDATE/DELETE/TRUNCATE 权限，不能是超级用户，库名必须是 SRC_DB。
  - 线上和开发不能是同一个 host:port/db。
  - 数据目录不能在仓库内，也不能在 /srv/netsentinel 下。
"""

import io
import os
import sys
from pathlib import Path

import psycopg2

REPO = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("KNETTF_DATA_DIR", str(Path.home() / "knettf-data"))).expanduser().resolve()
TABLE = "vigil_collectrecord"
SUBDIRS = ("snapshots", "increments", "exports", "restored")
MAX_GB = float(os.environ.get("KNETTF_MAX_GB", "20"))
OVERLAP = int(os.environ.get("KNETTF_OVERLAP", "5000"))

SRC = {
    "host": os.environ.get("KNETTF_SRC_HOST", "127.0.0.1"),
    "port": int(os.environ.get("KNETTF_SRC_PORT", "5432")),
    "dbname": os.environ.get("KNETTF_SRC_DB", "vigil"),
    "user": os.environ.get("KNETTF_SRC_USER", "knettf_reader"),
    "password": os.environ.get("KNETTF_SRC_PASSWORD", ""),
}
DST = {
    "host": os.environ.get("KNETTF_DST_HOST", "127.0.0.1"),
    "port": int(os.environ.get("KNETTF_DST_PORT", "5433")),
    "dbname": os.environ.get("KNETTF_DST_DB", "vigil_dev"),
    "user": os.environ.get("KNETTF_DST_USER", "knettf_dev"),
    "password": os.environ.get("KNETTF_DST_PASSWORD", ""),
}


def die(msg: str):
    print(f"❌ {msg}", file=sys.stderr)
    sys.exit(1)


def _dsn(c: dict) -> dict:
    return {"host": c["host"], "port": c["port"], "dbname": c["dbname"],
            "user": c["user"], "password": c["password"], "connect_timeout": 5}


def check_static(need_src: bool = True):
    """不连数据库的检查：目标是否是开发库，两端是否相同，数据目录位置。
    need_src=False 时（如导出）只检查开发库一侧。"""
    if DST["dbname"] != "vigil_dev":
        die(f"写入目标库必须是 vigil_dev（当前：{DST['dbname']}）")
    if DST["host"] not in ("127.0.0.1", "localhost"):
        die(f"开发库必须在本机（当前主机：{DST['host']}）")
    if not DST["password"]:
        die("缺少开发库密码：请设置 KNETTF_DST_PASSWORD（见 ~/.config/knettf/dev.env）")
    if need_src:
        if DST["port"] == SRC["port"] and DST["host"] == SRC["host"]:
            die("开发库和线上库是同一个 host:port，已中止（开发库必须是独立实例，例如 pg-dev 的 5433）")
        if not SRC["password"]:
            die("缺少线上只读账号密码：请设置 KNETTF_SRC_PASSWORD（见 ~/.config/knettf/reader.env）")
    if DATA_DIR == REPO or REPO in DATA_DIR.parents:
        die(f"数据目录位于开发仓库内，已中止：{DATA_DIR}")
    if str(DATA_DIR).startswith("/srv/netsentinel"):
        die(f"数据目录位于线上部署目录内，已中止：{DATA_DIR}")
    for sub in SUBDIRS:
        (DATA_DIR / sub).mkdir(parents=True, exist_ok=True)
    DATA_DIR.chmod(0o700)


def src_access() -> dict:
    """连接线上（只读账号）并查询权限，返回报告。不写任何东西。"""
    with psycopg2.connect(**_dsn(SRC)) as conn, conn.cursor() as cur:
        cur.execute(
            f"SELECT has_table_privilege(current_user, '{TABLE}', 'INSERT'),"
            f" has_table_privilege(current_user, '{TABLE}', 'UPDATE'),"
            f" has_table_privilege(current_user, '{TABLE}', 'DELETE'),"
            f" has_table_privilege(current_user, '{TABLE}', 'TRUNCATE'),"
            f" (SELECT rolsuper FROM pg_roles WHERE rolname = current_user),"
            f" current_database(), current_user"
        )
        ins, upd, dele, trunc, sup, db, who = cur.fetchone()
    return {"user": who, "database": db,
            "can_write": any([ins, upd, dele, trunc]), "superuser": bool(sup)}


def verify_src():
    """读取线上前必须调用。"""
    acc = src_access()
    if acc["database"] != SRC["dbname"]:
        die(f"线上连接的数据库是 {acc['database']}，不是 {SRC['dbname']}，已中止")
    if acc["can_write"] or acc["superuser"]:
        die(f"线上连接账号 {acc['user']} 有写权限或是超级用户，拒绝读取。请使用只读角色 knettf_reader")


def verify_dst():
    """写入开发库前必须调用：确认连接的确实是 vigil_dev。"""
    with psycopg2.connect(**_dsn(DST)) as conn, conn.cursor() as cur:
        cur.execute("SELECT current_database()")
        name = cur.fetchone()[0]
    if name != DST["dbname"]:
        die(f"开发库连接指向 {name}，不是 {DST['dbname']}，已中止写入")


def src_copy_out(sql: str) -> str:
    """线上只读：COPY ... TO STDOUT，返回文本（CSV）。"""
    buf = io.StringIO()
    with psycopg2.connect(**_dsn(SRC)) as conn, conn.cursor() as cur:
        conn.set_session(readonly=True, autocommit=True)
        cur.copy_expert(sql, buf)
    return buf.getvalue()


def dst_scalar(sql: str):
    with psycopg2.connect(**_dsn(DST)) as conn, conn.cursor() as cur:
        cur.execute(sql)
        return cur.fetchone()[0]


def dst_replace_tail(from_id: int, csv_text: str):
    """开发库：删除 id > from_id，再导入 csv_text，并校正序列。同一事务。"""
    with psycopg2.connect(**_dsn(DST)) as conn, conn.cursor() as cur:
        cur.execute(f"DELETE FROM {TABLE} WHERE id > %s", (from_id,))
        cur.copy_expert(f"COPY {TABLE} FROM STDIN WITH CSV HEADER", io.StringIO(csv_text))
        cur.execute(f"SELECT setval(pg_get_serial_sequence('{TABLE}', 'id'), "
                    f"(SELECT COALESCE(MAX(id), 1) FROM {TABLE}))")
        conn.commit()


def dst_replace_all(csv_text: str):
    """开发库：清空采集表，再导入 csv_text（整库覆盖）。同一事务。"""
    with psycopg2.connect(**_dsn(DST)) as conn, conn.cursor() as cur:
        cur.execute(f"TRUNCATE {TABLE}")
        cur.copy_expert(f"COPY {TABLE} FROM STDIN WITH CSV HEADER", io.StringIO(csv_text))
        cur.execute(f"SELECT setval(pg_get_serial_sequence('{TABLE}', 'id'), "
                    f"(SELECT COALESCE(MAX(id), 1) FROM {TABLE}))")
        conn.commit()


def enforce_retention(folder: Path, pattern: str):
    """目录总大小不超过 MAX_GB，从最旧的开始删；最新一份始终保留。"""
    cap = int(MAX_GB * 1024 * 1024 * 1024)
    files = sorted(folder.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    kept = 0
    for f in files:
        size = f.stat().st_size
        if kept == 0 or kept + size <= cap:
            kept += size
        else:
            f.unlink()
    return kept


def next_number(folder: Path) -> str:
    folder.mkdir(parents=True, exist_ok=True)
    nums = [int(d.name) for d in folder.iterdir() if d.is_dir() and d.name.isdigit()]
    return f"{(max(nums) + 1 if nums else 1):02d}"
