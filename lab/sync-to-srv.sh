#!/usr/bin/env bash
# 把实验环境运行目录更新到 GitHub 上最新的 main
# 用法: bash lab/sync-to-srv.sh [-n]      -n 只显示将要更新的提交，不实际更新
#
# 运行目录 /srv/netsentinel/lab 是指向 /srv/netsentinel/lab-repo/lab 的软链接；
# lab-repo 是 knettf 的 sparse checkout（只检出 lab/），remote 用 HTTPS，拉取不依赖个人密钥。
# 数据、.env、.venv、日志被 .gitignore 排除，git pull 不会动它们。
# 运行目录里有已跟踪文件被改过时拒绝更新（不要在运行目录里改代码）。
set -euo pipefail

REPO="${KNETTF_LAB_REPO:-/srv/netsentinel/lab-repo}"
BRANCH=main

die() { printf '\033[1;31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

umask 002
[ -d "$REPO/.git" ] || die "找不到 $REPO（见 lab/README.md「运行目录」一节的初始化步骤）"
[ "$(git -C "$REPO" branch --show-current)" = "$BRANCH" ] || die "$REPO 不在 $BRANCH 分支上"
[ -z "$(git -C "$REPO" status --porcelain --untracked-files=no)" ] \
  || { git -C "$REPO" status --short --untracked-files=no; die "运行目录有本地改动，不允许更新（改动请走 PR）"; }

git -C "$REPO" fetch -q origin "$BRANCH"
if [ "${1:-}" = "-n" ]; then
  git -C "$REPO" log --oneline "HEAD..origin/$BRANCH" -- lab
  echo "（dry-run，未更新）"
  exit 0
fi
git -C "$REPO" merge --ff-only -q "origin/$BRANCH"
git -C "$REPO" log --oneline -1
echo "✓ 运行目录已更新到 origin/$BRANCH"
