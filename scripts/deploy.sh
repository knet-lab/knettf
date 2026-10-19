#!/usr/bin/env bash
# NetSentinel 部署脚本
# 用法: scripts/deploy.sh [-frontend] [-backend] [-all]
#   -frontend  pnpm install + pnpm build（不用重启服务）
#   -backend   uv sync → manage.py check → migrate(default) → 重启 netsentinel → 检查 8080
#   -all       两者都做（先后端，再前端）
# 生产目录是 ~/netsentinel-prod（本仓库的 clone），只部署已提交的 main：
# 先在开发目录 git commit，脚本会在生产目录 git pull 后再构建/重启。
# vigil 库（PostgreSQL）不会自动 migrate：大表 ALTER 可能很慢，有未应用的迁移时只提示。
set -euo pipefail

DEV_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="${NETSENTINEL_PROD:-$HOME/netsentinel-prod}"
PY="$ROOT/.venv/bin/python"
SERVICE=netsentinel
PORT=8080

usage() {
  sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'
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

sync_code() {
  log "同步代码：$DEV_ROOT (main) → $ROOT"
  [ -d "$ROOT/.git" ] || die "找不到生产目录 $ROOT"
  if [ -n "$(git -C "$DEV_ROOT" status --porcelain)" ]; then
    printf '\033[1;33m! 开发目录有未提交的改动，它们不会被部署\033[0m\n'
  fi
  git -C "$ROOT" pull --ff-only -q origin main
  git -C "$ROOT" log --oneline -1
}

deploy_backend() {
  log "后端：uv sync（按 uv.lock 安装依赖）"
  command -v uv >/dev/null || PATH="$HOME/.local/bin:$PATH"
  command -v uv >/dev/null || die "找不到 uv"
  uv sync --frozen --project "$ROOT"

  cd "$ROOT/backend"
  log "后端：manage.py check"
  "$PY" manage.py check

  log "后端：collectstatic"
  "$PY" manage.py collectstatic --noinput -v 0

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

sync_code
[ $DO_BACKEND -eq 1 ] && deploy_backend
[ $DO_FRONTEND -eq 1 ] && deploy_frontend
log "完成"
