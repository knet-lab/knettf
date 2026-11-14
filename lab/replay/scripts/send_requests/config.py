from pathlib import Path

# ── 网络接口 ──────────────────────────────────────────────────────────────────
IFACE = "virbr-k8s"

# ── 文件路径（相对于本脚本位置） ──────────────────────────────────────────────
_HERE        = Path(__file__).parent
DATA_DIR     = _HERE.parent.parent          # zhouyang_request/

CSV_FILE     = DATA_DIR / "test set_20000(1).csv"
MAPPING_FILE = DATA_DIR / "ip_mapping.json"
RECORD_FILE  = DATA_DIR / "record_send_uuid.txt"
DONE_FILE    = DATA_DIR / "send.done"       # 发送完成后写入，read_kafka 用于终止

# ── 发包参数 ──────────────────────────────────────────────────────────────────
# None = 不限制，完整还原 CSV 中的 total_packets
MAX_PACKETS_PER_FLOW: int | None = None

# ── 跳过的特殊地址（DHCP 广播等，无法重放） ───────────────────────────────────
SKIP_SRC = {"0.0.0.0"}
SKIP_DST = {"255.255.255.255", "0.0.0.32"}
