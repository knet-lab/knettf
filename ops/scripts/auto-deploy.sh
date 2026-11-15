#!/usr/bin/env bash
# 自动部署：由 systemd timer（netsentinel-autodeploy.timer）每 2 分钟以 netsentinel 账户运行
#   GitHub main 有新提交 → 确认该提交的 GitHub Actions 检查全部通过 → 按改动路径选择：
#     apps/backend/、pyproject.toml、uv.lock  → deploy.sh -backend
#     apps/frontend/                         → deploy.sh -frontend
#     其他（文档、ops 等）                    → deploy.sh（只拉代码并重启）
#     lab/                                   → lab/sync-to-srv.sh
# 部署失败的提交记在 STATE_DIR/failed，不会每 2 分钟重试；修复后合入新提交即可。
# 平台最后一次部署成功的提交记在 STATE_DIR/deployed，改动范围从它算起，
# 这样中途失败过的前端/后端改动会在下一次成功部署时补上。
# lab 同步失败不阻塞平台部署，也不记 failed，下一轮自动重试。
# 手动运行：sudo -u netsentinel /srv/netsentinel/prod/ops/scripts/auto-deploy.sh
# 日志：/srv/netsentinel/logs/auto-deploy.log
set -euo pipefail

PROD="${NETSENTINEL_PROD:-/srv/netsentinel/prod}"
LAB_REPO="${KNETTF_LAB_REPO:-/srv/netsentinel/lab-repo}"
STATE_DIR="${AUTODEPLOY_STATE:-/srv/netsentinel/logs/auto-deploy}"
REPO_API="https://api.github.com/repos/knet-lab/knettf"
BRANCH=main

ts()  { date '+%F %T'; }
say() { echo "[$(ts)] $*"; }

mkdir -p "$STATE_DIR"
exec 9>"$STATE_DIR/lock"
flock -n 9 || exit 0                      # 上一次还没跑完

git -C "$PROD" fetch -q origin "$BRANCH"
NEW=$(git -C "$PROD" rev-parse "origin/$BRANCH")
CUR=$(cat "$STATE_DIR/deployed" 2>/dev/null || true)
git -C "$PROD" cat-file -e "${CUR:-x}^{commit}" 2>/dev/null || CUR=""   # 没记录：整套部署
LAB_CUR=$(git -C "$LAB_REPO" rev-parse HEAD)
[ "$NEW" = "$CUR" ] && [ "$NEW" = "$LAB_CUR" ] && exit 0
[ "$(cat "$STATE_DIR/failed" 2>/dev/null)" = "$NEW" ] && exit 0

# 检查 GitHub Actions：全部完成且成功才部署；还在跑就等下一轮
checks=$(curl -fsS -H 'Accept: application/vnd.github+json' "$REPO_API/commits/$NEW/check-runs?per_page=100") \
  || { say "查询检查状态失败，下一轮重试"; exit 0; }
total=$(jq '.total_count' <<<"$checks")
pending=$(jq '[.check_runs[]|select(.status!="completed")]|length' <<<"$checks")
bad=$(jq -r '[.check_runs[]|select(.status=="completed" and (.conclusion|IN("success","skipped","neutral")|not))|.name]|join(", ")' <<<"$checks")
[ "$total" -gt 0 ] || { say "${NEW:0:7} 还没有检查结果，等待"; exit 0; }
[ "$pending" -eq 0 ] || exit 0
if [ -n "$bad" ]; then
  say "✗ ${NEW:0:7} 检查未通过（$bad），不部署"; echo "$NEW" >"$STATE_DIR/failed"; exit 0
fi

say "==== 部署 ${CUR:0:7} → ${NEW:0:7}：$(git -C "$PROD" log -1 --format=%s "$NEW")"
rc=0
if [ "$NEW" != "$CUR" ]; then
  if [ -n "$CUR" ]; then
    changed=$(git -C "$PROD" diff --name-only "$CUR" "$NEW")
  else
    changed=$'apps/backend/\napps/frontend/'
  fi
  args=()
  grep -qE '^(apps/backend/|pyproject\.toml$|uv\.lock$)' <<<"$changed" && args+=(-backend)
  grep -qE '^apps/frontend/' <<<"$changed" && args+=(-frontend)
  if [ ${#args[@]} -eq 0 ] && grep -qvE '^lab/' <<<"$changed"; then args+=(-none); fi
  if [ ${#args[@]} -gt 0 ]; then
    say "deploy.sh ${args[*]}"
    "$PROD/ops/scripts/deploy.sh" "${args[@]}" || rc=$?
  else
    git -C "$PROD" pull --ff-only -q origin "$BRANCH" || rc=$?   # 只改了 lab/，平台不用重启
  fi
  [ $rc -eq 0 ] && echo "$NEW" >"$STATE_DIR/deployed"
fi

lab_rc=0
if [ "$NEW" != "$LAB_CUR" ]; then
  say "sync-to-srv.sh"
  bash "$LAB_REPO/lab/sync-to-srv.sh" || lab_rc=$?
  [ $lab_rc -eq 0 ] || say "⚠ lab 同步失败（rc=$lab_rc），不影响平台；下一轮重试"
fi

if [ $rc -eq 0 ]; then
  rm -f "$STATE_DIR/failed"; [ $lab_rc -eq 0 ] && say "✓ 完成 ${NEW:0:7}"
else
  echo "$NEW" >"$STATE_DIR/failed"; say "✗ 平台部署失败（rc=$rc），见上方输出；合入修复提交后会再次部署"
fi
