#!/usr/bin/env bash
# start_read.sh — 等待发包启动后开始监听，关闭终端后继续运行
# 用法: bash start_read.sh [--drain-wait N] [--max-rows N]

set -euo pipefail

UV="$(command -v uv 2>/dev/null || echo /home/soar009/.local/bin/uv)"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="$SCRIPT_DIR/.."
LOG_FILE="$DATA_DIR/read.log"
PID_FILE="$DATA_DIR/send.pid"

echo "[read] waiting for send_from_csv.py to start..."
until [[ -f "$PID_FILE" ]]; do
    sleep 0.5
done
echo "[read] send started (PID=$(cat "$PID_FILE")) — launching read_kafka.py"

nohup "$UV" run "$SCRIPT_DIR/read_kafka/read_kafka.py" "$@" \
    > "$LOG_FILE" 2>&1 &

READ_PID=$!
disown "$READ_PID"

echo "[read] started  PID=$READ_PID"
echo "[read] log  →  $LOG_FILE"
echo "[read] will auto-exit after send.done + drain"
