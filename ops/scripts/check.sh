#!/usr/bin/env bash
# 本地代码检查：提交 / 开 PR 前在自己的仓库检出里运行
# 用法: ops/scripts/check.sh [backend] [frontend] [lab] [ops]   不带参数 = 全部
# 只做静态检查和构建，不连 Kafka、不发包、不改数据库。
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
FAILED=()
TARGETS=("$@"); [ ${#TARGETS[@]} -eq 0 ] && TARGETS=(backend frontend lab ops)

log()  { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
step() { local name="$1"; shift; if "$@"; then echo "  ✓ $name"; else echo "  ✗ $name"; FAILED+=("$name"); fi; }

command -v uv >/dev/null || PATH="$HOME/.local/bin:$PATH"

check_shell() { local rc=0 f; while IFS= read -r -d '' f; do bash -n "$f" || rc=1; done < <(git ls-files -z -- "$@" | grep -z '\.sh$'); return $rc; }
check_py()    { git ls-files -z -- "$@" | grep -z '\.py$' | xargs -0 -r python3 -m py_compile; }

for t in "${TARGETS[@]}"; do
  case "$t" in
    backend)
      log "后端（apps/backend）"
      step "uv sync"            uv sync --frozen -q
      step "manage.py check"    bash -c 'cd apps/backend && ../../.venv/bin/python manage.py check'
      step "未生成的迁移"        bash -c 'cd apps/backend && ../../.venv/bin/python manage.py makemigrations --check --dry-run >/dev/null'
      step "Django 测试"        bash -c 'cd apps/backend && ../../.venv/bin/python manage.py test --noinput -v 1'
      ;;
    frontend)
      log "前端（apps/frontend）"
      command -v pnpm >/dev/null || { export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"; [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"; }
      step "pnpm install"       bash -c 'cd apps/frontend && pnpm install --frozen-lockfile --silent'
      step "pnpm build"         bash -c 'cd apps/frontend && pnpm build >/dev/null'
      ;;
    lab)
      log "实验脚本（lab）"
      step "Python 语法"        check_py lab
      step "Shell 语法"         check_shell lab
      ;;
    ops)
      log "运维脚本（ops）"
      step "Shell 语法"         check_shell ops
      ;;
    *) echo "未知目标: $t（可选 backend frontend lab ops）"; exit 2 ;;
  esac
done

echo
if [ ${#FAILED[@]} -eq 0 ]; then echo "✓ 全部通过"; else printf '✗ 失败: %s\n' "${FAILED[*]}"; exit 1; fi
