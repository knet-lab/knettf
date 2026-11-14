#!/usr/bin/env bash
# run_dataset_collection.sh
#
# 编排流程：
#   1. 后台启动 dataset_collector.py（普通用户身份，只收 .20-.29 和 .50-.64 的流量）
#   2. 正常流量：send_request.py --repeat 1000（192.168.100.50-64 → nginx，需 root）
#   3. 攻击流量：spoof_attack.py（192.168.100.20-29 SYN flood，需 root）
#   4. 等待 Kafka 消费追上，停止采集

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$SCRIPT_DIR/../.venv/bin/python3"

OUTPUT="${1:-$SCRIPT_DIR/dataset.csv}"
TARGET_ATTACK=160000
TARGET_NORMAL=50000
DRAIN_WAIT=20

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

# ── 校验 root（send_request.py 和 spoof_attack.py 需要 ip addr + raw socket） ──
if [[ "$(id -u)" -ne 0 ]]; then
    echo "[ERROR] Must run as root (ip addr add + raw socket required)."
    exit 1
fi

# 采集器以普通用户运行（kubectl 需要用户的 kubeconfig，不需要 root）
REAL_USER="${SUDO_USER:-soar009}"

# ── 1. 启动采集（后台，普通用户身份） ─────────────────────────────────────────
log "Starting dataset_collector as $REAL_USER → $OUTPUT"
log "  Targets: attack=$TARGET_ATTACK  normal=$TARGET_NORMAL"
log "  Filter : src_ip in {192.168.100.20-29} OR {192.168.100.50-64}"
sudo -H -u "$REAL_USER" "$PYTHON" "$SCRIPT_DIR/dataset_collector.py" \
    --output "$OUTPUT" \
    --max-attack "$TARGET_ATTACK" \
    --max-normal "$TARGET_NORMAL" \
    &
COLLECTOR_PID=$!
log "Collector PID=$COLLECTOR_PID"

# 等 header 出现（说明 kafka-console-consumer 已连上 Kafka）
log "Waiting for consumer to connect to Kafka..."
for i in $(seq 1 30); do
    sleep 1
    if [[ -f "$OUTPUT" ]] && [[ $(wc -l < "$OUTPUT") -ge 1 ]]; then
        log "Consumer ready after ${i}s"
        break
    fi
done
sleep 2  # 再等 2s 让 consumer 稳定

# ── 2. 正常流量（192.168.100.50-64 → 192.168.100.204:80） ────────────────────
log "Sending normal traffic (send_request.py --repeat 1000, 15 IPs)..."
"$PYTHON" "$SCRIPT_DIR/../traffic/send_request.py" --repeat 1000 --delay 0.02 || true
log "Normal traffic done."

sleep 3

# ── 3. 攻击流量（192.168.100.20-29 SYN flood） ───────────────────────────────
log "Sending attack traffic (spoof_attack.py, PACKETS_PER_TARGET=25000)..."
"$PYTHON" "$SCRIPT_DIR/../traffic/spoof_attack.py" || true
log "Attack traffic done."

# ── 4. 等待 Kafka 消费追上 ────────────────────────────────────────────────────
log "Waiting ${DRAIN_WAIT}s for Kafka consumer to drain..."
sleep "$DRAIN_WAIT"

# ── 5. 停止采集 ───────────────────────────────────────────────────────────────
if kill -0 "$COLLECTOR_PID" 2>/dev/null; then
    log "Stopping collector (PID=$COLLECTOR_PID)..."
    kill "$COLLECTOR_PID" 2>/dev/null || true
    wait "$COLLECTOR_PID" 2>/dev/null || true
else
    log "Collector already finished (targets reached)."
fi

log "Done. Dataset: $OUTPUT"
wc -l "$OUTPUT" | awk '{print "  Rows (incl. header): "$1}'
