"""
vigil/bridge.py — Kafka → in-memory flow aggregation → local detect API

Flow aggregation logic mirrors knetsentinel/dataset/aggregate_flows.py
so the feature set is identical to DetectionInput / FLOW_FIELDS.
"""

import json
import logging
import math
import subprocess
import threading
import time
from collections import defaultdict

import requests

logger = logging.getLogger("vigil.bridge")

# ── Kafka config ───────────────────────────────────────────────────────────────
KAFKA_POD        = "kafka-broker-0"
KAFKA_NAMESPACE  = "default"
KAFKA_TOPIC      = "ebpf-net-logs"
BOOTSTRAP_SERVER = "localhost:9092"

FLOW_TIMEOUT_SEC = 5   # idle gap that closes a flow (mirrors aggregate_flows.py default)
BATCH_SIZE       = 20  # POST when this many completed flows are queued


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
    """Convert a Hubble flow event to the packet dict format used by compute_flow()."""
    l4 = flow.get("l4", {})
    src_ip  = flow.get("IP", {}).get("source", "")
    dst_port_val = _port(l4, "destination_port")

    # label from IP range: 192.168.100.20-29 = attack (1), .50-64 = normal (0)
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
    """
    Identical logic to knetsentinel/dataset/aggregate_flows.py:compute_flow().
    Produces all fields matching DetectionInput / FLOW_FIELDS.
    """
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

    # open_flows: flow_key → list of packet dicts
    open_flows: dict[tuple, list] = defaultdict(list)
    pending:    list[dict]        = []

    cmd = [
        "kubectl", "exec", "-n", KAFKA_NAMESPACE, KAFKA_POD, "--",
        "/opt/kafka/bin/kafka-console-consumer.sh",
        "--bootstrap-server", BOOTSTRAP_SERVER,
        "--topic", KAFKA_TOPIC,
    ]
    logger.info("bridge starting → %s/%s topic=%s → %s", KAFKA_NAMESPACE, KAFKA_POD, KAFKA_TOPIC, base_url)

    while True:
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            last_flush = time.time()

            for line in proc.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    flow  = event.get("flow", {})
                    if not flow:
                        continue

                    key = _flow_key(flow)
                    pkt = _hubble_to_packet(flow)

                    if key in open_flows and open_flows[key]:
                        last_ts = open_flows[key][-1]["ts"]
                        if pkt["ts"] - last_ts > FLOW_TIMEOUT_SEC:
                            # timeout — close old flow, start new
                            pending.append(compute_flow(open_flows[key]))
                            open_flows[key] = [pkt]
                        else:
                            open_flows[key].append(pkt)
                    else:
                        open_flows[key] = [pkt]

                except json.JSONDecodeError:
                    continue

                now = time.time()
                if now - last_flush >= 1.0:
                    # also flush idle flows
                    expired = [k for k, pkts in open_flows.items()
                               if pkts and now - pkts[-1]["ts"] >= FLOW_TIMEOUT_SEC]
                    for k in expired:
                        pending.append(compute_flow(open_flows.pop(k)))

                    if len(pending) >= BATCH_SIZE:
                        _push(pending, base_url, token)
                        pending.clear()
                    last_flush = now

        except Exception as e:
            logger.error("bridge error: %s — restarting in 10s", e)
        finally:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:
                pass

        # flush before restart
        for pkts in open_flows.values():
            if pkts:
                pending.append(compute_flow(pkts))
        if pending:
            _push(pending, base_url, token)
            pending.clear()
        open_flows.clear()

        logger.info("bridge restarting in 10s...")
        time.sleep(10)


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
