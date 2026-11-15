"""
Hubble flow 事件 → 数据包记录 → 流特征（35 个，与 DetectionInput 字段一致）。

流的切分在 flows.py（双向流 + FIN/RST + 超时，业界通用做法）。这里只负责：
  · 单个 Hubble 事件 → 包记录（hubble_to_packet）
  · 一条完整流的包 → 特征（compute_flow）

单位与 CICFlowMeter / 训练数据一致：flow_duration、iat_* 为微秒；packets_per_second 为每秒。
正向（fwd）= 连接发起方发出的包，反向（bwd）= 响应方发出的包。
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


def is_node_level(ip: str) -> bool:
    """节点 IP 或宿主机网关（不含 Pod、不含 LoadBalancer VIP）。"""
    return ip in _NODE_IPS or ip == _HOST_GW


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


US = 1_000_000  # 秒 → 微秒


def flow_key(flow: dict) -> tuple:
    """单向五元组（事件里的 src→dst）。双向流的规范化见 flows.biflow_key。"""
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
        "obs_point": flow.get("trace_observation_point", ""),
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
    """一条流的全部包 → 35 个特征。

    包里有 "fwd"（bool，flows.FlowTable 填）时按发起方判断正反向；
    没有时退回旧规则（direction == INGRESS 为正向）。src/dst 取发起方/响应方。
    """
    packets = sorted(packets, key=lambda p: p["ts"])

    timestamps = [p["ts"] for p in packets]
    duration   = max(timestamps[-1] - timestamps[0], 1e-6)          # 秒，下面换算
    iats       = [(timestamps[i+1] - timestamps[i]) * US for i in range(len(timestamps) - 1)]

    total = len(packets)
    is_fwd = [p["fwd"] if "fwd" in p else p["direction"] == "INGRESS" for p in packets]
    fwd   = sum(is_fwd)
    bwd   = total - fwd

    flags_total: dict[str, int] = defaultdict(int)
    for p in packets:
        for flag, val in p["flags"].items():
            if val:
                flags_total[flag] += 1

    replies   = sum(1 for p in packets if p["is_reply"])
    forwarded = sum(1 for p in packets if p["verdict"] == "FORWARDED")
    dropped   = total - forwarded

    # 发起方视角的端点：第一个正向包；全是反向包时把第一个包的两端对调
    first_fwd = next((p for p, f in zip(packets, is_fwd) if f), None)
    if first_fwd is not None:
        src_ip, dst_ip = first_fwd["src_ip"], first_fwd["dst_ip"]
        src_port, dst_port = first_fwd["src_port"], first_fwd["dst_port"]
    else:
        p0 = packets[0]
        src_ip, dst_ip, src_port, dst_port = p0["dst_ip"], p0["src_ip"], p0["dst_port"], p0["src_port"]
    proto = packets[0]["protocol"]

    labels = [p["label"] for p, f in zip(packets, is_fwd) if f and p["label"] != ""] \
          or [p["label"] for p in packets if p["label"] != ""]
    label  = max(set(labels), key=labels.count) if labels else ""

    return {
        "src_ip":    src_ip,
        "dst_ip":    dst_ip,
        "src_port":  src_port,
        "dst_port":  dst_port,
        "protocol":  proto,
        "flow_duration":      round(duration * US, 1),
        "total_packets":      total,
        "fwd_packets":        fwd,
        "bwd_packets":        bwd,
        "fwd_ratio":          _ratio(fwd, total),
        "packets_per_second": round(total / duration, 4),
        "iat_mean": round(_mean(iats), 1) if iats else 0.0,
        "iat_std":  round(_std(iats),  1) if iats else 0.0,
        "iat_min":  round(min(iats),   1) if iats else 0.0,
        "iat_max":  round(max(iats),   1) if iats else 0.0,
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
        "is_bidirectional":   int(fwd > 0 and bwd > 0),
        "is_tcp":  int(proto == "TCP"),
        "is_udp":  int(proto == "UDP"),
        "is_icmp": int(proto in ("ICMPv4", "ICMPv6")),
        "is_well_known_port": int(isinstance(dst_port, int) and dst_port < 1024),
        "label": label,
    }


def should_skip(flow: dict) -> bool:
    """节点层面的管理流量、Kafka 自身的流量、loopback、缺 IP 或缺端口的残缺事件不参与检测。"""
    src = flow.get("IP", {}).get("source", "")
    dst = flow.get("IP", {}).get("destination", "")
    if not src or not dst:
        return True
    # 节点层面的管理流量（kubelet 探针、apiserver、节点间通信）：一端是节点/宿主机网关，
    # 另一端也在集群内。Pod↔Pod（东西向）与外部↔集群（南北向）都保留检测。
    if (is_node_level(src) and is_infrastructure(dst)) or (is_node_level(dst) and is_infrastructure(src)):
        return True
    # 发往 LoadBalancer VIP 的包在 FROM_NETWORK 处记录的是 DNAT 前的地址，随后会以 Pod 地址
    # 在 FROM_HOST 再记录一次；只保留后者，请求和回包才能落在同一条"客户端↔Pod"双向流里
    if flow.get("trace_observation_point") == "FROM_NETWORK" and dst in _METALLB_IPS:
        return True
    # loopback：节点本地 socket 层的记录，不是网络上的包
    if src.startswith("127.") or dst.startswith("127.") or src == "::1" or dst == "::1":
        return True
    l4 = flow.get("l4", {})
    # TCP/UDP 缺任一端口 = 残缺事件（无观测点、无方向），缺的端口不能当 0 用
    for proto in ("TCP", "UDP"):
        if proto in l4 and not ("source_port" in l4[proto] and "destination_port" in l4[proto]):
            return True
    return _port(l4, "source_port") in KAFKA_PORTS or _port(l4, "destination_port") in KAFKA_PORTS
