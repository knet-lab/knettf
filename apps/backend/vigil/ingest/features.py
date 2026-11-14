"""
Hubble flow 事件 → 数据包记录 → 流特征（35 个，与 DetectionInput 字段一致）。

这里的计算必须与训练数据的生成方式一致（lab/dataset/aggregate_flows.py），
否则模型看到的特征分布会和训练时不同。改动任何特征前先对照那边。
"""

import math
import time
from collections import defaultdict

# 节点 IP + MetalLB VIP + Pod CIDR — 这些都是集群内部流量
_NODE_IPS = {f"192.168.100.{i}" for i in range(10, 16)}
_METALLB_IPS = {f"192.168.100.{i}" for i in range(200, 251)}
KAFKA_PORTS = {9092, 9093, 9094}
_HOST_GW = "192.168.100.1"  # virbr-k8s 宿主机网关


def is_infrastructure(ip: str) -> bool:
    """True if this IP belongs to cluster infrastructure (not external traffic)."""
    return (
        ip.startswith("10.")
        or ip in _NODE_IPS
        or ip in _METALLB_IPS
        or ip == _HOST_GW
    )


# ── 工具函数 ────────────────────────────────────────────────────────────────────
def _mean(values):
    return sum(values) / len(values) if values else 0.0


def _std(values):
    if len(values) < 2:
        return 0.0
    m = _mean(values)
    return math.sqrt(sum((v - m) ** 2 for v in values) / len(values))


def _ratio(count, total):
    return round(count / total, 4) if total else 0.0


def _parse_ts(ts_str: str) -> float:
    try:
        from datetime import datetime
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00")).timestamp()
    except Exception:
        return time.time()


def _protocol(l4: dict) -> str:
    for p in ("TCP", "UDP", "ICMPv4", "ICMPv6"):
        if p in l4:
            return p
    return "OTHER"


def _port(l4: dict, side: str) -> int:
    for p in ("TCP", "UDP"):
        if p in l4 and side in l4[p]:
            return int(l4[p][side])
    return 0


def _tcp_flags(l4: dict) -> dict:
    flags_raw = (l4.get("TCP") or {}).get("flags") or {}
    if not isinstance(flags_raw, dict):
        return {}
    return flags_raw


def flow_key(flow: dict) -> tuple:
    l4 = flow.get("l4", {})
    return (
        flow.get("IP", {}).get("source", ""),
        flow.get("IP", {}).get("destination", ""),
        _port(l4, "source_port"),
        _port(l4, "destination_port"),
        _protocol(l4),
    )


def hubble_to_packet(flow: dict) -> dict:
    l4 = flow.get("l4", {})
    src_ip       = flow.get("IP", {}).get("source", "")
    dst_port_val = _port(l4, "destination_port")

    label = ""
    try:
        last = int(src_ip.split(".")[-1])
        if 20 <= last <= 29:
            label = "1"
        elif 50 <= last <= 64:
            label = "0"
    except Exception:
        pass

    return {
        "ts":        _parse_ts(flow.get("time", "")),
        "direction": flow.get("traffic_direction", ""),
        "verdict":   flow.get("verdict", ""),
        "flags":     _tcp_flags(l4),
        "is_reply":  bool(flow.get("is_reply", False)),
        "label":     label,
        "src_ip":    src_ip,
        "dst_ip":    flow.get("IP", {}).get("destination", ""),
        "src_port":  _port(l4, "source_port"),
        "dst_port":  dst_port_val,
        "protocol":  _protocol(l4),
    }


def compute_flow(packets: list) -> dict:
    packets = sorted(packets, key=lambda p: p["ts"])

    timestamps = [p["ts"] for p in packets]
    duration   = max(timestamps[-1] - timestamps[0], 1e-6)
    iats       = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps) - 1)]

    total = len(packets)
    fwd   = sum(1 for p in packets if p["direction"] == "INGRESS")
    bwd   = total - fwd

    flags_total: dict[str, int] = defaultdict(int)
    for p in packets:
        for flag, val in p["flags"].items():
            if val:
                flags_total[flag] += 1

    replies   = sum(1 for p in packets if p["is_reply"])
    forwarded = sum(1 for p in packets if p["verdict"] == "FORWARDED")
    dropped   = total - forwarded

    proto      = packets[0]["protocol"]
    directions = {p["direction"] for p in packets}

    labels = [p["label"] for p in packets if p["label"] != ""]
    label  = max(set(labels), key=labels.count) if labels else ""

    dst_port = packets[0]["dst_port"]

    return {
        "src_ip":    packets[0]["src_ip"],
        "dst_ip":    packets[0]["dst_ip"],
        "src_port":  packets[0]["src_port"],
        "dst_port":  dst_port,
        "protocol":  proto,
        "flow_duration":      round(duration, 4),
        "total_packets":      total,
        "fwd_packets":        fwd,
        "bwd_packets":        bwd,
        "fwd_ratio":          _ratio(fwd, total),
        "packets_per_second": round(total / duration, 4),
        "iat_mean": round(_mean(iats), 6) if iats else 0.0,
        "iat_std":  round(_std(iats),  6) if iats else 0.0,
        "iat_min":  round(min(iats),   6) if iats else 0.0,
        "iat_max":  round(max(iats),   6) if iats else 0.0,
        "syn_count": flags_total["SYN"],
        "ack_count": flags_total["ACK"],
        "fin_count": flags_total["FIN"],
        "rst_count": flags_total["RST"],
        "psh_count": flags_total["PSH"],
        "urg_count": flags_total["URG"],
        "syn_ratio": _ratio(flags_total["SYN"], total),
        "ack_ratio": _ratio(flags_total["ACK"], total),
        "fin_ratio": _ratio(flags_total["FIN"], total),
        "rst_ratio": _ratio(flags_total["RST"], total),
        "reply_count":     replies,
        "reply_ratio":     _ratio(replies, total),
        "forwarded_count": forwarded,
        "drop_count":      dropped,
        "drop_ratio":      _ratio(dropped, total),
        "is_bidirectional":   int(len(directions) > 1),
        "is_tcp":  int(proto == "TCP"),
        "is_udp":  int(proto == "UDP"),
        "is_icmp": int(proto in ("ICMPv4", "ICMPv6")),
        "is_well_known_port": int(isinstance(dst_port, int) and dst_port < 1024),
        "label": label,
    }




def should_skip(flow: dict) -> bool:
    """集群内部流量（两端都是基础设施）、Kafka 自身的流量、缺 IP 的事件不参与检测。"""
    src = flow.get("IP", {}).get("source", "")
    dst = flow.get("IP", {}).get("destination", "")
    if not src or not dst:
        return True
    if is_infrastructure(src) and is_infrastructure(dst):
        return True
    l4 = flow.get("l4", {})
    return _port(l4, "source_port") in KAFKA_PORTS or _port(l4, "destination_port") in KAFKA_PORTS
