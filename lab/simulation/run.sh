#!/usr/bin/env bash
# 用法：sudo NETSENTINEL_TOKEN=<JWT> bash simulation/run.sh [1|2|3]
#   可选 NETSENTINEL_BACKEND（默认 http://localhost:8080）

set -e
cd "$(dirname "$0")"

PYTHON="$(pwd)/../.venv/bin/python3"   # lab/.venv

MODE=${1:-}
if [[ -z "$MODE" ]]; then
    echo "  1 → 正常流量"
    echo "  2 → 混合流量"
    echo "  3 → 全攻击流量"
    read -rp "模式 [1/2/3]: " MODE
fi

if [[ -z "${NETSENTINEL_TOKEN:-}" ]]; then
    echo "需要设置 NETSENTINEL_TOKEN（NetSentinel 后端 JWT），monitor 用它轮询 /api/vigil/records/"
    exit 1
fi

case "$MODE" in
    1|2|3) ;;
    *) echo "无效模式: $MODE"; exit 1 ;;
esac

LOG="monitor/send.log"
> "$LOG"

# 先启 monitor（记录起始时间，只统计之后落库的检测结果）
echo "[run] 启动 monitor..."
$PYTHON monitor/monitor.py --mode "$MODE" \
    --token "$NETSENTINEL_TOKEN" --backend "${NETSENTINEL_BACKEND:-http://localhost:8080}" &
MON_PID=$!

# 等 monitor 启动
sleep 2

# 再启 simulate
echo "[run] 启动 simulate_${MODE}.py..."
$PYTHON "simulate_${MODE}.py" > "$LOG" 2>&1

# simulate 结束后等 monitor 生成报告
wait "$MON_PID"
echo "[run] 完成"
