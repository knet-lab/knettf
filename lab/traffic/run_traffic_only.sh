#!/usr/bin/env bash
# run_traffic_only.sh — 只发流量（需 root），配合手动启动的 dataset_collector.py 使用
# 用法: sudo bash run_traffic_only.sh [--normal-repeat N] [--attack-packets N]
#   --normal-repeat N   正常流量轮次（默认 1000，每轮 15 IP 各发一次请求）
#   --attack-packets N  每个攻击目标的包数（默认 25000，共 5 个目标）

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$SCRIPT_DIR/../.venv/bin/python3"

if [[ "$(id -u)" -ne 0 ]]; then
    echo "[ERROR] Must run as root."
    exit 1
fi

NORMAL_REPEAT=1000
ATTACK_PACKETS=25000

while [[ $# -gt 0 ]]; do
    case "$1" in
        --normal-repeat)  NORMAL_REPEAT="$2";  shift 2 ;;
        --attack-packets) ATTACK_PACKETS="$2"; shift 2 ;;
        *) echo "[ERROR] Unknown argument: $1"; exit 1 ;;
    esac
done

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

log "Sending normal traffic (--packets ${NORMAL_REPEAT}, 15 IPs × 5 targets)..."
"$PYTHON" "$SCRIPT_DIR/send_normal_scapy.py" --packets "$NORMAL_REPEAT"

log "Normal traffic done."
sleep 3

log "Sending attack traffic (--packets ${ATTACK_PACKETS}, 5 targets)..."
"$PYTHON" "$SCRIPT_DIR/spoof_attack.py" --packets "$ATTACK_PACKETS"

log "Attack traffic done."
log "All traffic sent. You can stop the collector now (Ctrl+C)."
