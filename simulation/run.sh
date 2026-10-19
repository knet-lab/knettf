#!/usr/bin/env bash
# 用法：sudo bash simulation/run.sh [1|2|3]

set -e
cd "$(dirname "$0")"

PYTHON=/srv/netsentinel/knetsentinel/.venv/bin/python3

MODE=${1:-}
if [[ -z "$MODE" ]]; then
    echo "  1 → 正常流量"
    echo "  2 → 混合流量"
    echo "  3 → 全攻击流量"
    read -rp "模式 [1/2/3]: " MODE
fi

case "$MODE" in
    1|2|3) ;;
    *) echo "无效模式: $MODE"; exit 1 ;;
esac

LOG="monitor/send.log"
> "$LOG"

# 先启 monitor（WS 先连上，不漏结果）
echo "[run] 启动 monitor..."
$PYTHON monitor/monitor.py --mode "$MODE" &
MON_PID=$!

# 等 monitor WS 连上
sleep 2

# 再启 simulate
echo "[run] 启动 simulate_${MODE}.py..."
$PYTHON "simulate_${MODE}.py" > "$LOG" 2>&1

# simulate 结束后等 monitor 生成报告
wait "$MON_PID"
echo "[run] 完成"
