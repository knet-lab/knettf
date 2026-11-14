#!/usr/bin/env bash
# 一次性迁移：把生产环境从 soar009 的 home 搬到 /srv/netsentinel，改由 netsentinel 账户以系统服务运行
# 用法（用有 sudo 的个人账户运行，不要 sudo 整个脚本）:
#   scripts/migrate-to-srv.sh prep      不停服：建账户/组/目录，装工具链，预复制代码并建 venv
#   scripts/migrate-to-srv.sh cutover   停服切换：停旧服务 → 同步数据 → 启新系统服务 → 检查 200
#   scripts/migrate-to-srv.sh rollback  切回旧的用户级服务（cutover 出问题时用）
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OLD=/home/soar009/netsentinel-prod
OLD_KNET=/home/soar009/knetsentinel
BASE=/srv/netsentinel
PROD=$BASE/prod
KNET=$BASE/knetsentinel
NODE_SRC=/home/soar009/.nvm/versions/node/v22.21.1
NODE_DST=/opt/node-v22.21.1
TUNNEL_JSON=/home/soar009/.cloudflared/491d938b-3187-4d93-84da-66df739753e6.json
CF_DIR=/etc/cloudflared/knettf
STAMP=$(date +%Y%m%d_%H%M%S)

log() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
die() { printf '\033[1;31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

as_ns() { sudo -u netsentinel env HOME=$BASE UV_CACHE_DIR=$BASE/.cache/uv UV_PYTHON_DOWNLOADS=never "$@"; }

fix_perms() {
  sudo chown -R netsentinel:netsentinel "$1"
  sudo chmod -R g+rwX "$1"
  sudo find "$1" -type d -exec chmod g+s {} +
}

copy_tree() {  # 源 目标（不带 .venv、node_modules）
  sudo rsync -a --delete --exclude .venv --exclude node_modules "$1/" "$2/"
  fix_perms "$2"
}

prep() {
  log "账户与组"
  getent group netsentinel >/dev/null || sudo groupadd --system netsentinel
  getent passwd netsentinel >/dev/null || sudo useradd --system -g netsentinel -d $BASE -s /usr/sbin/nologin netsentinel
  sudo usermod -aG netsentinel "$(id -un)"

  log "目录"
  for d in $BASE $PROD $KNET $BASE/backups $BASE/review-logs $BASE/logs $BASE/shared $BASE/shared/dev-env $BASE/shared/dev-data $BASE/.cache; do
    sudo install -d -o netsentinel -g netsentinel -m 2775 "$d"
  done

  log "工具链装到系统路径（不再依赖 soar009 的 home）"
  sudo install -m 755 /home/soar009/.local/bin/uv /usr/local/bin/uv
  if [ -x /home/soar009/.local/bin/uvx ]; then sudo install -m 755 /home/soar009/.local/bin/uvx /usr/local/bin/uvx; fi
  sudo rsync -a "$NODE_SRC/" "$NODE_DST/"
  for b in node npm npx pnpm corepack; do
    if [ -e "$NODE_DST/bin/$b" ]; then sudo ln -sfn "$NODE_DST/bin/$b" "/usr/local/bin/$b"; fi
  done
  /usr/local/bin/uv --version; /usr/local/bin/node -v; /usr/local/bin/pnpm -v

  log "git 允许组成员操作 netsentinel 拥有的仓库"
  for r in $PROD $KNET; do
    sudo git config --system --get-all safe.directory 2>/dev/null | grep -qx "$r" || sudo git config --system --add safe.directory "$r"
  done

  log "预复制代码 + 建 venv（线上不受影响）"
  copy_tree "$OLD" "$PROD"
  sudo git -C $PROD config core.sharedRepository group
  as_ns uv sync --frozen --project $PROD --python /usr/bin/python3.12
  copy_tree "$OLD_KNET" "$KNET"
  if [ -f "$KNET/uv.lock" ]; then as_ns uv sync --frozen --project $KNET --python /usr/bin/python3.12; fi

  log "检查 sudoers 语法"
  sudo visudo -cf "$REPO/deploy/sudoers.netsentinel"

  log "prep 完成。重新登录让 netsentinel 组生效，再运行: scripts/migrate-to-srv.sh cutover（停服约 1 分钟）"
}

cutover() {
  [ -x $PROD/.venv/bin/uvicorn ] || die "先运行 prep"

  log "停旧的用户级服务"
  systemctl --user stop cloudflared-knettf netsentinel
  systemctl --user disable cloudflared-knettf netsentinel

  log "最终同步（含 sqlite 数据）"
  copy_tree "$OLD" "$PROD"
  copy_tree "$OLD_KNET" "$KNET"
  sudo git -C $PROD remote set-url origin git@github.com:knet-lab/NetSentinel.git

  log "安装 cloudflared 配置、systemd、cron、sudoers"
  sudo install -d -o netsentinel -g netsentinel -m 750 $CF_DIR
  sudo install -o netsentinel -g netsentinel -m 400 "$TUNNEL_JSON" $CF_DIR/
  sudo install -o root -g netsentinel -m 640 "$REPO/deploy/cloudflared-knettf.yml" $CF_DIR/config.yml
  sudo install -m 644 "$REPO/deploy/systemd/netsentinel.service" /etc/systemd/system/
  sudo install -m 644 "$REPO/deploy/systemd/cloudflared-knettf.service" /etc/systemd/system/
  sudo install -m 644 "$REPO/deploy/cron.netsentinel" /etc/cron.d/netsentinel
  sudo install -m 440 "$REPO/deploy/sudoers.netsentinel" /etc/sudoers.d/netsentinel
  { crontab -l 2>/dev/null | grep -v 'netsentinel-prod/.*rotate_partitions' || true; } | crontab -

  log "启动新系统服务"
  sudo systemctl daemon-reload
  sudo systemctl enable --now netsentinel cloudflared-knettf
  code=
  for _ in $(seq 1 20); do
    code=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8080/ || true)
    [ "$code" = 200 ] && break
    sleep 1
  done
  if [ "$code" != 200 ]; then
    sudo journalctl -u netsentinel -n 30 --no-pager || true
    die "8080 没有返回 200（${code:-无}）。运行 scripts/migrate-to-srv.sh rollback 切回旧服务"
  fi
  echo "✓ netsentinel HTTP 200"

  log "旧目录改名留作回滚，knetsentinel 原路径改为软链接"
  mv "$OLD" "$OLD.migrated-$STAMP"
  mv "$OLD_KNET" "$OLD_KNET.migrated-$STAMP"
  ln -s $KNET "$OLD_KNET"
  systemctl is-active netsentinel cloudflared-knettf
  log "cutover 完成。确认 https://knettf.com 正常一周后，可删除 $OLD.migrated-* 和 $OLD_KNET.migrated-*"
}

rollback() {
  log "停新系统服务"
  sudo systemctl disable --now cloudflared-knettf netsentinel || true
  sudo rm -f /etc/cron.d/netsentinel

  log "恢复旧目录"
  local old_dir knet_dir
  old_dir=$(ls -d "$OLD".migrated-* 2>/dev/null | tail -1 || true)
  if [ -n "$old_dir" ] && [ ! -e "$OLD" ]; then mv "$old_dir" "$OLD"; fi
  knet_dir=$(ls -d "$OLD_KNET".migrated-* 2>/dev/null | tail -1 || true)
  if [ -n "$knet_dir" ]; then
    if [ -L "$OLD_KNET" ]; then rm "$OLD_KNET"; fi
    mv "$knet_dir" "$OLD_KNET"
  fi
  [ -d "$OLD" ] || die "找不到 $OLD"

  log "启动旧的用户级服务"
  systemctl --user enable --now netsentinel cloudflared-knettf
  crontab -l | grep -q 'netsentinel-prod/.*rotate_partitions' || \
    (crontab -l; echo "0 0 * * * $OLD/.venv/bin/python $OLD/backend/manage.py rotate_partitions --database vigil >> /tmp/rotate_partitions.log 2>&1") | crontab -
  echo "注意：cutover 之后新服务写入的数据在 $PROD，需要的话手动拷回 $OLD/backend/*.sqlite3"
  systemctl --user is-active netsentinel cloudflared-knettf
}

case "${1:-}" in
  prep) prep ;;
  cutover) cutover ;;
  rollback) rollback ;;
  *) sed -n '2,6p' "$0" | sed 's/^# \{0,1\}//'; exit 1 ;;
esac
