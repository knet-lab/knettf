#!/bin/bash
# client-zone.sh — 在宿主机上用 network namespace 仿真一组"互联网客户端"
#
#   宿主机
#   ├─ czbr0 (172.30.1.1/24) ── veth ── netns cz01 (172.30.1.11) ┐
#   │                         ── veth ── netns cz02 (172.30.1.12) ├ 每个各跑一份 locust
#   │                          ...                                ┘ 出口 tc netem：延迟/抖动/丢包
#   └─ 经宿主机路由 → virbr-k8s (192.168.100.0/24) → frontend LoadBalancer
#
# 每个客户端：独立源 IP、不同的网络条件、不同相位的日周期负载。
# locust 进程用 systemd 单元 knettf-client-NN 运行，限制在 CLIENT_CPUS 指定的核上，不和 VM 抢 CPU。
#
# 用法（需 root）：
#   sudo bash client-zone.sh up       创建 netns / 网桥 / 路由 / 防火墙放行 / netem
#   sudo bash client-zone.sh start    启动各客户端的 locust（读 lab/.env 的 BOUTIQUE_URL）
#   sudo bash client-zone.sh stop     停止 locust
#   sudo bash client-zone.sh down     停止并删除全部网络配置
#   sudo bash client-zone.sh status
#
# 可调环境变量：CLIENTS（默认 10）、CLIENT_CPUS（默认 48-55）、
#               CLIENT_MIN_USERS / CLIENT_MAX_USERS / CLIENT_PERIOD_SEC（见 boutique_locust.py）
set -euo pipefail

LAB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLIENTS="${CLIENTS:-10}"
CLIENT_CPUS="${CLIENT_CPUS:-48-55}"
BR=czbr0
NET=172.30.1
GW="${NET}.1"
CLUSTER_NET=192.168.100.0/24
ZONE_NET=172.30.0.0/16
TAG="knettf-client-zone"
RUN_USER="${SUDO_USER:-$(logname 2>/dev/null || echo root)}"
LOCUST="${LAB_DIR}/.venv/bin/locust"
LOCUSTFILE="${LAB_DIR}/traffic/boutique_locust.py"

say() { echo "[client-zone] $*"; }
die() { echo "[client-zone] ❌ $*" >&2; exit 1; }
[ "$(id -u)" -eq 0 ] || die "需要 root：sudo bash $0 $*"

name() { printf 'cz%02d' "$1"; }

# 每个客户端的网络条件（确定性，便于复现）：单向延迟 5~60ms、抖动、少量丢包
netem_args() {
  local i=$1
  local delay=$(( 5 + (i * 37) % 56 ))
  local jitter=$(( 1 + delay / 5 ))
  local loss; loss=$(awk -v i="$i" 'BEGIN{printf "%.1f", (i % 4) * 0.2}')
  echo "delay ${delay}ms ${jitter}ms distribution normal loss ${loss}%"
}

fw() {  # $1 = -I | -D
  iptables "$1" FORWARD -s "$ZONE_NET" -d "$CLUSTER_NET" -m comment --comment "$TAG" -j ACCEPT
  iptables "$1" FORWARD -s "$CLUSTER_NET" -d "$ZONE_NET" -m comment --comment "$TAG" -j ACCEPT
}

up() {
  ip link show "$BR" >/dev/null 2>&1 || {
    ip link add "$BR" type bridge
    ip addr add "${GW}/24" dev "$BR"
    ip link set "$BR" up
  }
  for i in $(seq 1 "$CLIENTS"); do
    local ns; ns=$(name "$i")
    local ip="${NET}.$((10 + i))"
    ip netns list | grep -qw "$ns" && continue
    ip netns add "$ns"
    ip link add "${ns}-h" type veth peer name eth0 netns "$ns"
    ip link set "${ns}-h" master "$BR" up
    ip -n "$ns" addr add "${ip}/24" dev eth0
    ip -n "$ns" link set lo up
    ip -n "$ns" link set eth0 up
    ip -n "$ns" route add default via "$GW"
    # 上行（客户端→集群）在 netns 的 eth0 出口加 netem；下行在宿主机侧 veth 出口加同样的条件
    # shellcheck disable=SC2046
    ip netns exec "$ns" tc qdisc replace dev eth0 root netem $(netem_args "$i")
    # shellcheck disable=SC2046
    tc qdisc replace dev "${ns}-h" root netem $(netem_args "$i")
    say "$ns  ${ip}  $(netem_args "$i")"
  done
  iptables -C FORWARD -s "$ZONE_NET" -d "$CLUSTER_NET" -m comment --comment "$TAG" -j ACCEPT 2>/dev/null || fw -I
  [ "$(cat /proc/sys/net/ipv4/ip_forward)" = 1 ] || die "ip_forward 未开启"
  say "up 完成：${CLIENTS} 个客户端，网段 ${NET}.0/24"
}

start() {
  [ -x "$LOCUST" ] || die "找不到 $LOCUST（在 lab/ 下运行 uv sync）"
  URL=$(grep -oP '^BOUTIQUE_URL=\K.*' "${LAB_DIR}/.env" 2>/dev/null || true)
  if [ -z "$URL" ]; then
    # root 没有 kubeconfig，以调用 sudo 的用户身份查询前端 LB 地址
    local ip
    ip=$(runuser -u "$RUN_USER" -- kubectl -n boutique get svc frontend-external \
           -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || true)
    [ -n "$ip" ] && URL="http://${ip}"
  fi
  [ -n "$URL" ] || die "找不到 Online Boutique 地址，先运行 cluster/04-deploy-baseline.sh"
  say "目标：$URL"
  for i in $(seq 1 "$CLIENTS"); do
    local ns; ns=$(name "$i")
    ip netns list | grep -qw "$ns" || die "$ns 不存在，先运行 up"
    local unit="knettf-client-$(printf '%02d' "$i")"
    systemctl is-active --quiet "$unit" && continue
    local phase; phase=$(awk -v i="$i" -v n="$CLIENTS" 'BEGIN{printf "%.3f", (i-1)/n}')
    systemd-run --quiet --unit "$unit" --collect \
      -p AllowedCPUs="$CLIENT_CPUS" -p MemoryMax=512M \
      --setenv=CLIENT_PHASE="$phase" \
      --setenv=CLIENT_MIN_USERS="${CLIENT_MIN_USERS:-1}" \
      --setenv=CLIENT_MAX_USERS="${CLIENT_MAX_USERS:-6}" \
      --setenv=CLIENT_PERIOD_SEC="${CLIENT_PERIOD_SEC:-3600}" \
      ip netns exec "$ns" runuser -u "$RUN_USER" -- \
        "$LOCUST" -f "$LOCUSTFILE" --headless --host "$URL" --only-summary --loglevel WARNING
    say "$unit 已启动（$ns，相位 $phase）"
  done
}

stop() {
  for i in $(seq 1 "$CLIENTS"); do
    systemctl stop "knettf-client-$(printf '%02d' "$i")" 2>/dev/null || true
  done
  say "已停止"
}

down() {
  stop
  for i in $(seq 1 "$CLIENTS"); do
    local ns; ns=$(name "$i")
    ip link del "${ns}-h" 2>/dev/null || true
    ip netns del "$ns" 2>/dev/null || true
  done
  ip link del "$BR" 2>/dev/null || true
  while iptables -C FORWARD -s "$ZONE_NET" -d "$CLUSTER_NET" -m comment --comment "$TAG" -j ACCEPT 2>/dev/null; do fw -D; done
  say "已删除"
}

status() {
  ip -br addr show "$BR" 2>/dev/null || echo "网桥 $BR 不存在"
  ip netns list | grep -E '^cz[0-9]+' || echo "没有客户端 netns"
  systemctl list-units --no-legend 'knettf-client-*' 2>/dev/null || true
}

case "${1:-}" in
  up) up ;; start) start ;; stop) stop ;; down) down ;; status) status ;;
  *) echo "用法：sudo bash $0 {up|start|stop|down|status}"; exit 1 ;;
esac
