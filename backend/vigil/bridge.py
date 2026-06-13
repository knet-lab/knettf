"""
vigil/bridge.py — Kafka → in-memory flow aggregation → local detect API

Flow aggregation logic mirrors knetsentinel/dataset/aggregate_flows.py
so the feature set is identical to DetectionInput / FLOW_FIELDS.
"""

import json
import logging
import math
import threading
import time
from collections import defaultdict

import requests
from confluent_kafka import Consumer, KafkaError, KafkaException

logger = logging.getLogger("vigil.bridge")

# ── Kafka config ───────────────────────────────────────────────────────────────
KAFKA_BOOTSTRAP  = "192.168.100.200:9094,192.168.100.201:9094,192.168.100.202:9094,192.168.100.203:9094"
KAFKA_TOPIC      = "ebpf-net-logs"
KAFKA_GROUP_ID   = "vigil-bridge"

FLOW_TIMEOUT_SEC = 5
BATCH_SIZE       = 20

# 节点 IP + MetalLB VIP + Pod CIDR — 这些都是集群内部流量
_NODE_IPS = {f"192.168.100.{i}" for i in range(10, 16)}
_METALLB_IPS = {f"192.168.100.{i}" for i in range(200, 251)}
_KAFKA_PORTS = {9092, 9093, 9094}
_HOST_GW = "192.168.100.1"  # virbr-k8s 宿主机网关


def _is_infrastructure(ip: str) -> bool:
    """True if this IP belongs to cluster infrastructure (not external traffic)."""
    return (
        ip.startswith("10.")
        or ip in _NODE_IPS
        or ip in _METALLB_IPS
        or ip == _HOST_GW
    )


# ── Helpers ────────────────────────────────────────────────────────────────────
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


def _flow_key(flow: dict) -> tuple:
    l4 = flow.get("l4", {})
    return (
        flow.get("IP", {}).get("source", ""),
        flow.get("IP", {}).get("destination", ""),
        _port(l4, "source_port"),
        _port(l4, "destination_port"),
        _protocol(l4),
    )


def _hubble_to_packet(flow: dict) -> dict:
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


# ── HTTP push ──────────────────────────────────────────────────────────────────
def _push(flows: list[dict], base_url: str, token: str | None):
    url     = f"{base_url.rstrip('/')}/api/vigil/detect/batch/"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        r = requests.post(url, json={"flows": flows}, headers=headers, timeout=10)
        if r.status_code == 200:
            results   = (r.json().get("data") or {}).get("results") or []
            n_attacks = sum(1 for x in results if x.get("is_attack"))
            logger.info("pushed %d flows → %d attack(s)", len(flows), n_attacks)
        else:
            logger.warning("push HTTP %s: %s", r.status_code, r.text[:200])
    except requests.RequestException as e:
        logger.warning("push failed: %s", e)


# ── Wait for server ────────────────────────────────────────────────────────────
def _wait_for_server(base_url: str, timeout: int = 60):
    url      = f"{base_url.rstrip('/')}/api/vigil/stats/"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=2)
            if r.status_code in (200, 401, 403):
                logger.info("server ready at %s", base_url)
                return True
        except requests.RequestException:
            pass
        time.sleep(1)
    logger.warning("server not ready after %ds, starting anyway", timeout)
    return False


# ── Main loop ──────────────────────────────────────────────────────────────────
def run_bridge(base_url: str = "http://localhost:8080", token: str | None = None):
    _wait_for_server(base_url)

    consumer = Consumer({
        "bootstrap.servers":         KAFKA_BOOTSTRAP,
        "group.id":                  KAFKA_GROUP_ID,
        "auto.offset.reset":         "latest",
        "enable.auto.commit":        False,
        "fetch.min.bytes":           1024 * 64,
        "fetch.wait.max.ms":         500,
        "max.partition.fetch.bytes": 1024 * 1024 * 4,
        "session.timeout.ms":        30000,
        "heartbeat.interval.ms":     10000,
        "broker.address.family":     "v4",
    })
    consumer.subscribe([KAFKA_TOPIC])
    logger.info("bridge starting → bootstrap=%s topic=%s group=%s → %s",
                KAFKA_BOOTSTRAP, KAFKA_TOPIC, KAFKA_GROUP_ID, base_url)

    open_flows: dict[tuple, list] = defaultdict(list)
    pending:    list[dict]        = []
    last_flush  = time.time()

    try:
        while True:
            msg = consumer.poll(timeout=1.0)

            if msg is None:
                pass
            elif msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    pass
                else:
                    raise KafkaException(msg.error())
            else:
                try:
                    event = json.loads(msg.value().decode("utf-8"))
                    flow  = event.get("flow", {})
                    if flow:
                        src = flow.get("IP", {}).get("source", "")
                        dst = flow.get("IP", {}).get("destination", "")
                        # 过滤纯集群内部流量（包括 Kafka 自身 TCP 连接）
                        if _is_infrastructure(src) and _is_infrastructure(dst):
                            continue
                        l4_tmp = flow.get("l4", {})
                        sp = _port(l4_tmp, "source_port")
                        dp = _port(l4_tmp, "destination_port")
                        if sp in _KAFKA_PORTS or dp in _KAFKA_PORTS:
                            continue
                        key = _flow_key(flow)
                        pkt = _hubble_to_packet(flow)

                        if key in open_flows and open_flows[key]:
                            last_ts = open_flows[key][-1]["ts"]
                            if pkt["ts"] - last_ts > FLOW_TIMEOUT_SEC:
                                pending.append(compute_flow(open_flows[key]))
                                open_flows[key] = [pkt]
                            else:
                                open_flows[key].append(pkt)
                        else:
                            open_flows[key] = [pkt]
                except (json.JSONDecodeError, Exception) as e:
                    logger.debug("skip malformed message: %s", e)

            now = time.time()
            if now - last_flush >= 1.0:
                expired = [k for k, pkts in open_flows.items()
                           if pkts and now - pkts[-1]["ts"] >= FLOW_TIMEOUT_SEC]
                for k in expired:
                    pending.append(compute_flow(open_flows.pop(k)))

                if len(pending) >= BATCH_SIZE:
                    _push(pending, base_url, token)
                    consumer.commit(asynchronous=True)
                    pending.clear()

                last_flush = now

    except Exception as e:
        logger.error("bridge error: %s", e)
    finally:
        if pending:
            _push(pending, base_url, token)
        consumer.commit(asynchronous=False)
        consumer.close()
        logger.info("bridge shut down cleanly")


# ── Thread launcher ────────────────────────────────────────────────────────────
_started = False
_lock    = threading.Lock()


def start(base_url: str = "http://localhost:8080", token: str | None = None):
    """Start bridge daemon thread. Idempotent."""
    global _started
    with _lock:
        if _started:
            return
        _started = True
    t = threading.Thread(target=run_bridge, args=(base_url, token), daemon=True, name="vigil-bridge")
    t.start()
    logger.info("vigil bridge thread started")
