"""scripts 公共配置与安全检查。

所有数据路径和数据库连接都来自环境变量，仓库里不写入任何数据：

  KNETTF_DATA_DIR        数据目录（快照、归档、导出结果），默认 ~/knettf-data（权限 700）
  KNETTF_PG_CONTAINER    Postgres 容器名，默认 pg
  KNETTF_SRC_DB/_USER    线上库（只读来源），默认 vigil / vigil（见下文，应改为只读角色）
  KNETTF_SRC_PASSWORD    线上只读账号的密码（可选，经环境变量传给容器，不进命令行）
  KNETTF_DST_DB/_USER    开发库（唯一写入目标），默认 vigil_dev / vigil
  KNETTF_DST_PASSWORD    开发库账号密码（可选）
  KNETTF_MAX_GB          归档目录容量上限，默认 20
  KNETTF_OVERLAP         增量同步的重叠条数，默认 5000

安全规则：
  - check_safety()：写入目标必须是 vigil_dev；线上库和开发库不能相同；
    数据目录不能在开发仓库内，也不能在线上部署目录 /srv/netsentinel 下。
  - verify_src()：线上连接账号不能对采集表有 INSERT/UPDATE/DELETE/TRUNCATE 权限，不能是超级用户，
    连接的数据库必须是 SRC_DB。不满足则拒绝读取。
  - verify_dst()：连接的数据库必须是 DST_DB，写入前确认。
"""

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("KNETTF_DATA_DIR", str(Path.home() / "knettf-data"))).expanduser().resolve()
PG_CONTAINER = os.environ.get("KNETTF_PG_CONTAINER", "pg")
SRC_DB = os.environ.get("KNETTF_SRC_DB", "vigil")
SRC_USER = os.environ.get("KNETTF_SRC_USER", "vigil")
SRC_PASSWORD = os.environ.get("KNETTF_SRC_PASSWORD", "")
DST_DB = os.environ.get("KNETTF_DST_DB", "vigil_dev")
DST_USER = os.environ.get("KNETTF_DST_USER", "vigil")
DST_PASSWORD = os.environ.get("KNETTF_DST_PASSWORD", "")
MAX_GB = float(os.environ.get("KNETTF_MAX_GB", "20"))
OVERLAP = int(os.environ.get("KNETTF_OVERLAP", "5000"))
TABLE = "vigil_collectrecord"
SUBDIRS = ("snapshots", "increments", "exports", "restored")


def die(msg: str):
    print(f"❌ {msg}", file=sys.stderr)
    sys.exit(1)


def check_safety():
    """所有会访问数据库或写数据的命令都先调用这里（静态检查，不连数据库）。"""
    if DST_DB != "vigil_dev":
        die(f"写入目标必须是 vigil_dev（当前：{DST_DB}）")
    if SRC_DB == DST_DB:
        die("线上库和开发库相同，已中止")
    if DATA_DIR == REPO or REPO in DATA_DIR.parents:
        die(f"数据目录位于开发仓库内，已中止：{DATA_DIR}")
    if str(DATA_DIR).startswith("/srv/netsentinel"):
        die(f"数据目录位于线上部署目录内，已中止：{DATA_DIR}")
    for sub in SUBDIRS:
        (DATA_DIR / sub).mkdir(parents=True, exist_ok=True)
    DATA_DIR.chmod(0o700)  # 数据含流量明细，只允许本人读写


def _run(args, stdin: bytes | None = None, env: dict | None = None) -> bytes:
    res = subprocess.run(args, input=stdin, capture_output=True, env=env)
    if res.returncode != 0:
        die(f"命令失败：{' '.join(args[:4])} …\n{res.stderr.decode(errors='replace')}")
    return res.stdout


def _psql(db: str, user: str, password: str, extra: list[str], stdin: bytes | None = None) -> bytes:
    """经 docker exec 调用容器内的 psql。密码走环境变量 PGPASSWORD，不出现在命令行参数里。"""
    cmd = ["docker", "exec"]
    env = os.environ.copy()
    if stdin is not None:
        cmd.append("-i")
    if password:
        cmd += ["-e", "PGPASSWORD"]
        env["PGPASSWORD"] = password
    cmd += [PG_CONTAINER, "psql", "-U", user, "-d", db, "-X", "-q", *extra]
    return _run(cmd, stdin=stdin, env=env)


# ── 线上库：只读 ──────────────────────────────────────────────────────────────
def src_copy_out(sql: str) -> bytes:
    """只读：执行 COPY ... TO STDOUT，返回原始字节。"""
    return _psql(SRC_DB, SRC_USER, SRC_PASSWORD, ["-c", sql])


def src_scalar(sql: str) -> str:
    """只读：执行一条查询，返回文本结果（多列用 | 分隔）。"""
    return _psql(SRC_DB, SRC_USER, SRC_PASSWORD, ["-Atc", sql]).decode().strip()


def src_dump_table() -> bytes:
    """只读：pg_dump 整张采集表（schema + 数据）。"""
    cmd = ["docker", "exec"]
    env = os.environ.copy()
    if SRC_PASSWORD:
        cmd += ["-e", "PGPASSWORD"]
        env["PGPASSWORD"] = SRC_PASSWORD
    cmd += [PG_CONTAINER, "pg_dump", "-U", SRC_USER, "-d", SRC_DB,
            "-t", TABLE, "--clean", "--if-exists", "--no-owner", "--no-privileges"]
    return _run(cmd, env=env)


def src_access() -> dict:
    """查询线上连接账号的权限（只读），返回报告字典，不做判断。"""
    row = src_scalar(
        f"SELECT has_table_privilege(current_user, '{TABLE}', 'INSERT'),"
        f" has_table_privilege(current_user, '{TABLE}', 'UPDATE'),"
        f" has_table_privilege(current_user, '{TABLE}', 'DELETE'),"
        f" has_table_privilege(current_user, '{TABLE}', 'TRUNCATE'),"
        f" (SELECT rolsuper FROM pg_roles WHERE rolname = current_user),"
        f" current_database(), current_user"
    )
    ins, upd, dele, trunc, sup, db, who = row.split("|")
    return {
        "user": who, "database": db,
        "can_write": "t" in (ins, upd, dele, trunc),
        "superuser": sup == "t",
    }


def verify_src():
    """读取线上前必须调用：账号不能有写权限、不能是超级用户、数据库必须是 SRC_DB。"""
    acc = src_access()
    if acc["database"] != SRC_DB:
        die(f"线上连接的数据库是 {acc['database']}，不是 {SRC_DB}，已中止")
    if acc["can_write"] or acc["superuser"]:
        die(f"线上连接账号 {acc['user']} 有写权限或是超级用户，拒绝读取。"
            f"请改用只读角色（见 scripts/sql/readonly_role.sql，并设置 KNETTF_SRC_USER / KNETTF_SRC_PASSWORD）")


# ── 开发库：唯一写入目标 ─────────────────────────────────────────────────────
def dst_scalar(sql: str) -> str:
    return _psql(DST_DB, DST_USER, DST_PASSWORD, ["-Atc", sql]).decode().strip()


def dst_script(sql_bytes: bytes):
    """在开发库执行一段 SQL 脚本（可包含 COPY ... FROM STDIN 的数据）。"""
    _psql(DST_DB, DST_USER, DST_PASSWORD, ["-v", "ON_ERROR_STOP=1", "-f", "-"], stdin=sql_bytes)


def verify_dst():
    """写入前必须调用：连接的数据库必须是 DST_DB。"""
    name = dst_scalar("SELECT current_database()")
    if name != DST_DB:
        die(f"开发库连接指向 {name}，不是 {DST_DB}，已中止写入")


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
