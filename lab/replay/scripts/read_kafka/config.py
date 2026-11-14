from pathlib import Path

# ── Kafka 连接 ────────────────────────────────────────────────────────────────
KAFKA_POD        = "kafka-broker-0"
KAFKA_NAMESPACE  = "default"
KAFKA_TOPIC      = "ebpf-net-logs"
BOOTSTRAP_SERVER = "localhost:9092"

# ── 文件路径（相对于本脚本位置） ──────────────────────────────────────────────
_HERE    = Path(__file__).parent
DATA_DIR = _HERE.parent.parent          # zhouyang_request/

OUTPUT_CSV = DATA_DIR / "read_result.csv"
DONE_FILE  = DATA_DIR / "send.done"    # send_from_csv.py 写入后触发排水等待

# ── 终止控制 ──────────────────────────────────────────────────────────────────
# 检测到 send.done 后，再等待 N 秒让 Kafka 排水后退出
DRAIN_WAIT_SEC = 15

# ── 捕获过滤：只记录来自映射后 normal IP 池的流量 ─────────────────────────────
CAPTURE_SRC_IPS = {f"192.168.100.{i}" for i in range(50, 65)}

# ── 输出 CSV 字段 ─────────────────────────────────────────────────────────────
FIELDNAMES = [
    "timestamp", "verdict", "direction", "summary",
    "src_ip", "dst_ip", "protocol", "src_port", "dst_port",
    "tcp_flags", "is_reply", "trace_reason", "label",
]

# 발송 트래픽은 전부 192.168.100.50-64 (normal) → label=0 고정
FIXED_LABEL = 0
