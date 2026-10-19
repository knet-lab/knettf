#!/usr/bin/env bash
# NetSentinel 部署脚本
# 用法: scripts/deploy.sh [-frontend] [-backend] [-all]
#   -frontend  pnpm install + pnpm build → 重启 netsentinel（WhiteNoise 启动时才扫描 dist）
#   -backend   uv sync → manage.py check → collectstatic → migrate(default) → 重启 netsentinel → 检查 8080
#   -all       两者都做（先后端，再前端）
# 生产目录是 /srv/netsentinel/prod（netsentinel 账户运行的系统服务），只部署 GitHub 上已 push 的 main：
# 先在自己的 clone 里 commit 并 push，脚本会在生产目录 git pull 后再构建/重启。
# 运行者须在 netsentinel 组（id 能看到），git pull 用运行者自己的 GitHub 密钥。
# vigil 库（PostgreSQL）不会自动 migrate：大表 ALTER 可能很慢，有未应用的迁移时只提示。
set -euo pipefail

DEV_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="${NETSENTINEL_PROD:-/srv/netsentinel/prod}"
PY="$ROOT/.venv/bin/python"
SERVICE=netsentinel
PORT=8080

usage() {
  sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

log() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
die() { printf '\033[1;31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

# 生产目录归 netsentinel 组，新文件要保持组可写
umask 002
id -nG | tr ' ' '\n' | grep -qx netsentinel || die "当前账户不在 netsentinel 组（加组后需重新登录）"

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
  log "同步代码：GitHub origin/main → $ROOT"
  [ -d "$ROOT/.git" ] || die "找不到生产目录 $ROOT"
  if [ -n "$(git -C "$DEV_ROOT" status --porcelain)" ]; then
    printf '\033[1;33m! 开发目录有未提交的改动，它们不会被部署\033[0m\n'
  fi
  [ -z "$(git -C "$ROOT" status --porcelain --untracked-files=no)" ] || die "生产目录有本地改动，不允许部署（不要在生产目录里改代码）"
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

  if "$PY" manage.py showmigrations vigil --database=vigil 2>/dev/null | grep -q "\[ \]"; then
    printf '\033[1;33m! vigil 库有未应用的迁移，请确认后手动执行:\n  cd %s/backend && %s manage.py migrate --database=vigil\033[0m\n' "$ROOT" "$PY"
  fi

}

# DEBUG=False 时 WhiteNoise 只在启动时扫描 dist，前端构建后也必须重启
restart_service() {
  log "重启 $SERVICE"
  sudo systemctl restart "$SERVICE.service"

  for _ in $(seq 1 20); do
    code=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/" || true)
    [ "$code" = 200 ] && { echo "✓ $SERVICE active，HTTP 200"; return; }
    sleep 1
  done
  sudo journalctl -u "$SERVICE.service" -n 30 --no-pager || true
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
  echo "✓ 前端已构建到 frontend/dist"
}

sync_code
[ $DO_BACKEND -eq 1 ] && deploy_backend
[ $DO_FRONTEND -eq 1 ] && deploy_frontend
restart_service
log "完成"
