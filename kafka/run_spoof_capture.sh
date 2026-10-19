#!/usr/bin/env bash
# Capture spoofed-IP traffic (192.168.100.20~29) from Kafka and save to log

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG="$SCRIPT_DIR/spoof_attack_captured.log"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting spoof traffic capture" | tee -a "$LOG"

# --src 192.168.100.2 pre-filters to .2xx range; awk then keeps only blocks with exact .20~.29
python3 "$SCRIPT_DIR/kafka_read.py" \
    --src 192.168.100.2 \
    --protocol TCP \
    --from-beginning \
    2>&1 | awk '
/^\[/ {
    if (buf ~ /192\.168\.100\.2[0-9]:/) printf "%s", buf
    buf = $0 "\n"
    next
}
{ buf = buf $0 "\n" }
END { if (buf ~ /192\.168\.100\.2[0-9]:/) printf "%s", buf }
' | tee -a "$LOG"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Capture finished" | tee -a "$LOG"
