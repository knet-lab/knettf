#!/usr/bin/env bash
# 把仓库里 lab/ 的代码同步到运行目录（默认 /srv/netsentinel/lab）
# 用法: bash lab/sync-to-srv.sh [-n]      -n 只列出会改动的文件，不实际同步
# 只同步 Git 跟踪的文件；运行目录里的数据、.env、.venv、日志等不会被覆盖或删除。
set -euo pipefail

LAB_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="${KNETTF_LAB_DIR:-/srv/netsentinel/lab}"
DRY=""
[ "${1:-}" = "-n" ] && DRY="--dry-run"

[ -d "$DEST" ] || { echo "运行目录不存在: $DEST" >&2; exit 1; }
if [ -n "$(git -C "$LAB_SRC" status --porcelain -- .)" ]; then
  echo "! lab/ 有未提交的改动，它们也会被同步" >&2
fi

umask 002
git -C "$LAB_SRC" ls-files -z -- . \
  | rsync -a --from0 --files-from=- --itemize-changes $DRY "$LAB_SRC/" "$DEST/"
echo "✓ 已同步 $LAB_SRC → $DEST${DRY:+（dry-run）}"
