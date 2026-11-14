#!/usr/bin/env bash
# start_send.sh — 后台启动发包，关闭终端后继续运行
# 用法: sudo bash start_send.sh [--max-packets N]

set -euo pipefail

UV="$(command -v uv 2>/dev/null || echo /home/soar009/.local/bin/uv)"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="$SCRIPT_DIR/.."
LOG_FILE="$DATA_DIR/send.log"
PID_FILE="$DATA_DIR/send.pid"
DONE_FILE="$DATA_DIR/send.done"

rm -f "$PID_FILE" "$DONE_FILE"

if [[ "$(id -u)" -ne 0 ]]; then
    echo "[send] ERROR: must run as root." >&2
    exit 1
fi

nohup "$UV" run "$SCRIPT_DIR/send_requests/send_from_csv.py" "$@" \
    > "$LOG_FILE" 2>&1 &

SEND_PID=$!
disown "$SEND_PID"
echo "$SEND_PID" > "$PID_FILE"

echo "[send] started  PID=$SEND_PID"
echo "[send] log  →  $LOG_FILE"
echo "[send] done sentinel will appear at: $DONE_FILE"
