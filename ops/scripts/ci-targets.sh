#!/usr/bin/env bash
# 按改动的文件决定 CI 要检查哪些部分，输出 check.sh 的目标（空格分隔）
# 用法: ops/scripts/ci-targets.sh <基准提交>      基准为空或不存在 → 全部检查
#
#   apps/backend/、model-kit/、pyproject.toml、uv.lock → backend
#   apps/frontend/                                  → frontend
#   lab/                                            → lab（lab/shipper 依赖后端 ingest，改后端时也查 lab）
#   ops/                                            → ops
#   .github/（CI 自身）                              → 全部
#   其他（docs/、*.md 等）                           → ops（至少跑一项，保证有检查结果供自动部署判断）
set -euo pipefail

BASE="${1:-}"
ALL="backend frontend lab ops"
if [ -z "$BASE" ] || [ "$BASE" = "0000000000000000000000000000000000000000" ] \
   || ! git cat-file -e "${BASE}^{commit}" 2>/dev/null; then
  echo "$ALL"; exit 0
fi

changed=$(git diff --name-only "$BASE" HEAD)
has() { grep -qE "$1" <<<"$changed"; }

if has '^\.github/'; then echo "$ALL"; exit 0; fi

targets=()
has '^(apps/backend/|model-kit/|pyproject\.toml$|uv\.lock$)' && targets+=(backend lab)
has '^apps/frontend/' && targets+=(frontend)
has '^lab/'           && targets+=(lab)
has '^ops/'           && targets+=(ops)
[ ${#targets[@]} -eq 0 ] && targets+=(ops)

printf '%s\n' "${targets[@]}" | awk '!seen[$0]++' | paste -sd' '
