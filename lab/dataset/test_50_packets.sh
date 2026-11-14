#!/usr/bin/env bash
# test_50_packets.sh — 小规模同步测试：发50个攻击包，验证 CSV 能否抓到数据
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$SCRIPT_DIR/../.venv/bin/python3"
OUTPUT="/tmp/test50.csv"
FAKE_IP="192.168.100.20"
IFACE="virbr-k8s"

if [[ "$(id -u)" -ne 0 ]]; then
    echo "[ERROR] Must run as root."
    exit 1
fi

REAL_USER="${SUDO_USER:-soar009}"

rm -f "$OUTPUT"
echo "[+] Output: $OUTPUT"

# 1. 添加伪造 IP
echo "[+] Adding $FAKE_IP to $IFACE..."
ip addr add "$FAKE_IP/24" dev "$IFACE" 2>/dev/null && echo "    added" || echo "    (already exists)"

# 2. 启动采集器（后台，普通用户身份）
echo "[+] Starting collector as $REAL_USER (max-attack=250)..."
sudo -H -u "$REAL_USER" "$PYTHON" "$SCRIPT_DIR/dataset_collector.py" \
    --output "$OUTPUT" \
    --max-attack 250 \
    --max-normal 1 &
CPID=$!

# 3. 等 header 出现，说明 kafka-console-consumer 已经开始读取
echo "[+] Waiting for consumer to connect to Kafka (header check)..."
for i in $(seq 1 30); do
    sleep 1
    if [[ -f "$OUTPUT" ]] && [[ $(wc -l < "$OUTPUT") -ge 1 ]]; then
        echo "[+] Consumer ready after ${i}s (header written)"
        break
    fi
    echo "    ... ${i}s elapsed"
done

# 再等 2 秒让 consumer 稳定
sleep 2

# 4. 发 50 个 SYN 包
echo "[+] Sending 50 SYN packets from $FAKE_IP → 192.168.100.10:6443..."
"$PYTHON" - <<'PYEOF'
from scapy.all import IP, TCP, send, conf
conf.iface = "virbr-k8s"
pkt = IP(src="192.168.100.20", dst="192.168.100.10") / TCP(dport=6443, flags="S", sport=12345)
send(pkt, count=50, verbose=False, inter=0)
print("[+] 50 packets sent")
PYEOF

# 5. 等待 Kafka 消费追上（Vector 批次刷新最多几秒）
echo "[+] Waiting 20s for Kafka drain..."
sleep 20

# 6. 停止采集
if kill -0 "$CPID" 2>/dev/null; then
    echo "[+] Stopping collector..."
    kill "$CPID" 2>/dev/null || true
    wait "$CPID" 2>/dev/null || true
else
    echo "[+] Collector already finished (target reached)."
fi

# 7. 清理 IP
ip addr del "$FAKE_IP/24" dev "$IFACE" 2>/dev/null || true
echo "[+] Cleaned up $FAKE_IP"

# 8. 结果
echo ""
echo "=== Result ==="
if [[ -f "$OUTPUT" ]]; then
    LINES=$(wc -l < "$OUTPUT")
    echo "Rows (incl. header): $LINES"
    echo "Data rows: $((LINES - 1))"
    echo ""
    head -5 "$OUTPUT"
else
    echo "[FAIL] Output file not found."
fi
