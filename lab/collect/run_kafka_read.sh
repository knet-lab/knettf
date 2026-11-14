#!/usr/bin/env bash
# Run kafka_read.py and capture all output to kafka_read_result.log

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG="$SCRIPT_DIR/kafka_read_result.log"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting kafka_read.py" | tee -a "$LOG"

python3 "$SCRIPT_DIR/kafka_read.py" 2>&1 | tee -a "$LOG"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] kafka_read.py finished" | tee -a "$LOG"
