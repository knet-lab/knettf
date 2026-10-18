#!/usr/bin/env bash
# NetSentinel 部署脚本
# 用法: scripts/deploy.sh [-frontend] [-backend] [-all]
#   -frontend  pnpm install + pnpm build（不用重启服务）
#   -backend   装依赖 → manage.py check → migrate(default) → 重启 netsentinel → 检查 8080
#   -all       两者都做（先后端，再前端）
# vigil 库（PostgreSQL）不会自动 migrate：大表 ALTER 可能很慢，有未应用的迁移时只提示。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$ROOT/.venv/bin/python"
SERVICE=netsentinel
PORT=8080

usage() {
  sed -n '2,7p' "$0" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

log() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
die() { printf '\033[1;31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

DO_FRONTEND=0
DO_BACKEND=0
[ $# -eq 0 ] && usage 1
for arg in "$@"; do
  case "$arg" in
    -frontend|--frontend) DO_FRONTEND=1 ;;
    -backend|--backend)   DO_BACKEND=1 ;;
    -all|--all)           DO_FRONTEND=1; DO_BACKEND=1 ;;
    -h|--help)            usage 0 ;;
    *) printf '未知参数: %s\n\n' "$arg" >&2; usage 1 ;;
  esac
done

deploy_backend() {
  log "后端：安装依赖"
  [ -x "$PY" ] || die "找不到 $PY，先按手册创建 .venv"
  "$PY" -m pip install -q -r "$ROOT/backend/requirements.txt"

  cd "$ROOT/backend"
  log "后端：manage.py check"
  "$PY" manage.py check

  log "后端：migrate（default）"
  "$PY" manage.py migrate --noinput

  if "$PY" manage.py showmigrations --database=vigil --plan 2>/dev/null | grep -q '^\[ \]'; then
    printf '\033[1;33m! vigil 库有未应用的迁移，请确认后手动执行:\n  cd %s/backend && %s manage.py migrate --database=vigil\033[0m\n' "$ROOT" "$PY"
  fi

  log "后端：重启 $SERVICE"
  systemctl --user restart "$SERVICE"

  for _ in $(seq 1 20); do
    code=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/" || true)
    [ "$code" = 200 ] && { echo "✓ $SERVICE active，HTTP 200"; return; }
    sleep 1
  done
  journalctl --user -u "$SERVICE" -n 30 --no-pager || true
  die "$SERVICE 重启后 20 秒内没有返回 200（最后状态码: ${code:-无}）"
}

deploy_frontend() {
  log "前端：pnpm install && pnpm build"
  if ! command -v pnpm >/dev/null; then
    # 非交互 shell 下 nvm 不会自动加载
    export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
    # shellcheck disable=SC1091
    [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
    command -v pnpm >/dev/null || die "找不到 pnpm（检查 nvm / node 是否安装）"
  fi
  cd "$ROOT/frontend"
  pnpm install --frozen-lockfile
  pnpm build
  echo "✓ 前端已构建到 frontend/dist，浏览器强制刷新即可看到"
}

[ $DO_BACKEND -eq 1 ] && deploy_backend
[ $DO_FRONTEND -eq 1 ] && deploy_frontend
log "完成"
