"""
detector.py — Kafka consumer + OCSVM inference + Kafka producer

Consumes:  ebpf-net-logs   (Hubble flow JSON)
Produces:  detection-results (detection result JSON)
"""

import asyncio
import json
import logging
import math
import os
import time
from collections import defaultdict
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import websockets
import yaml
from confluent_kafka import Consumer, KafkaError, KafkaException

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("detector")

# ── Config from env ────────────────────────────────────────────────────────────
KAFKA_BOOTSTRAP   = os.environ.get("KAFKA_BOOTSTRAP", "192.168.100.200:9094,192.168.100.201:9094,192.168.100.202:9094,192.168.100.203:9094")
CONSUME_TOPIC     = os.environ.get("CONSUME_TOPIC",   "ebpf-net-logs")
GROUP_ID          = os.environ.get("GROUP_ID",         "vigil-detector")
FLOW_TIMEOUT_SEC  = int(os.environ.get("FLOW_TIMEOUT_SEC", "5"))
BATCH_SIZE        = int(os.environ.get("BATCH_SIZE",       "20"))
MODEL_DIR         = Path(os.environ.get("MODEL_DIR", Path(__file__).parent / "ads_ml"))
DJANGO_WS_URL     = os.environ.get("DJANGO_WS_URL",   "ws://192.168.100.1:8080/ws/detector/push/")
DJANGO_TOKEN      = os.environ.get("DJANGO_TOKEN",    "")

# ── Load models once at startup ────────────────────────────────────────────────
def _load():
    cfg_path = MODEL_DIR / "config.yaml"
    with open(cfg_path) as f:
        config = yaml.safe_load(f)
    pipeline   = joblib.load(MODEL_DIR / config["model_paths"]["ocsvm_pipeline"])
    prototypes = joblib.load(MODEL_DIR / config["model_paths"]["prototypes"])
    X_train    = pd.read_csv(
        MODEL_DIR / config["training_data_used_for_cosine_verification"]["train_data"]
    ).values
    logger.info("models loaded from %s", MODEL_DIR)
    return pipeline, prototypes, X_train

# ── Flow feature helpers (mirrors bridge.py) ──────────────────────────────────
def _mean(v): return sum(v) / len(v) if v else 0.0
def _std(v):
    if len(v) < 2: return 0.0
    m = _mean(v)
    return math.sqrt(sum((x - m) ** 2 for x in v) / len(v))
def _ratio(a, b): return round(a / b, 4) if b else 0.0

def _protocol(l4):
    for p in ("TCP", "UDP", "ICMPv4", "ICMPv6"):
        if p in l4: return p
    return "OTHER"

def _port(l4, side):
    for p in ("TCP", "UDP"):
        if p in l4 and side in l4[p]: return int(l4[p][side])
    return 0

def _tcp_flags(l4):
    flags = (l4.get("TCP") or {}).get("flags") or {}
    return flags if isinstance(flags, dict) else {}

def _flow_key(flow):
    l4 = flow.get("l4", {})
    return (
        flow.get("IP", {}).get("source", ""),
        flow.get("IP", {}).get("destination", ""),
        _port(l4, "source_port"),
        _port(l4, "destination_port"),
        _protocol(l4),
    )

def _to_packet(flow):
    l4  = flow.get("l4", {})
    src = flow.get("IP", {}).get("source", "")
    label = ""
    try:
        last = int(src.split(".")[-1])
        if 20 <= last <= 29:  label = "1"
        elif 50 <= last <= 64: label = "0"
    except Exception: pass
    return {
        "ts":        float(flow.get("time_unix_ns", 0)) / 1e9 or time.time(),
        "direction": flow.get("traffic_direction", ""),
        "verdict":   flow.get("verdict", ""),
        "flags":     _tcp_flags(l4),
        "is_reply":  bool(flow.get("is_reply", False)),
        "label":     label,
        "src_ip":    src,
        "dst_ip":    flow.get("IP", {}).get("destination", ""),
        "src_port":  _port(l4, "source_port"),
        "dst_port":  _port(l4, "destination_port"),
        "protocol":  _protocol(l4),
    }

def _compute_flow(packets):
    packets   = sorted(packets, key=lambda p: p["ts"])
    ts        = [p["ts"] for p in packets]
    duration  = max(ts[-1] - ts[0], 1e-6)
    iats      = [ts[i+1] - ts[i] for i in range(len(ts) - 1)]
    total     = len(packets)
    fwd       = sum(1 for p in packets if p["direction"] == "INGRESS")
    bwd       = total - fwd
    flags_tot: dict[str, int] = defaultdict(int)
    for p in packets:
        for flag, val in p["flags"].items():
            if val: flags_tot[flag] += 1
    replies   = sum(1 for p in packets if p["is_reply"])
    forwarded = sum(1 for p in packets if p["verdict"] == "FORWARDED")
    proto     = packets[0]["protocol"]
    dst_port  = packets[0]["dst_port"]
    labels    = [p["label"] for p in packets if p["label"] != ""]
    label     = max(set(labels), key=labels.count) if labels else ""

    return {
        "src_ip": packets[0]["src_ip"], "dst_ip": packets[0]["dst_ip"],
        "src_port": packets[0]["src_port"], "dst_port": dst_port,
        "protocol": proto, "label": label,
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
        "syn_count": flags_tot["SYN"], "ack_count": flags_tot["ACK"],
        "fin_count": flags_tot["FIN"], "rst_count": flags_tot["RST"],
        "psh_count": flags_tot["PSH"], "urg_count": flags_tot["URG"],
        "syn_ratio": _ratio(flags_tot["SYN"], total),
        "ack_ratio": _ratio(flags_tot["ACK"], total),
        "fin_ratio": _ratio(flags_tot["FIN"], total),
        "rst_ratio": _ratio(flags_tot["RST"], total),
        "reply_count":     replies,
        "reply_ratio":     _ratio(replies, total),
        "forwarded_count": forwarded,
        "drop_count":      total - forwarded,
        "drop_ratio":      _ratio(total - forwarded, total),
        "is_bidirectional":   int(len({p["direction"] for p in packets}) > 1),
        "is_tcp":  int(proto == "TCP"),
        "is_udp":  int(proto == "UDP"),
        "is_icmp": int(proto in ("ICMPv4", "ICMPv6")),
        "is_well_known_port": int(isinstance(dst_port, int) and dst_port < 1024),
    }

# ── Inference ──────────────────────────────────────────────────────────────────
FEATURE_COLS = [
    "flow_duration", "total_packets", "fwd_packets", "bwd_packets", "fwd_ratio",
    "packets_per_second", "iat_mean", "iat_std", "iat_min", "iat_max",
    "syn_count", "ack_count", "fin_count", "rst_count", "psh_count", "urg_count",
    "syn_ratio", "ack_ratio", "fin_ratio", "rst_ratio",
    "reply_count", "reply_ratio", "forwarded_count", "drop_count", "drop_ratio",
    "is_bidirectional", "is_tcp", "is_udp", "is_icmp", "is_well_known_port",
]

COSINE_NORMAL_THRESH  = 0.95
COSINE_ANOMALY_THRESH = 0.90
SEEN_SIM_THRESHOLD    = 0.50
REVIEW_THRESHOLD      = 0.10
TOP_K                 = 5

def _infer(flow: dict, pipeline, prototypes, X_train) -> dict:
    from sklearn.metrics.pairwise import cosine_similarity

    X = np.array([[flow[c] for c in FEATURE_COLS]])
    X_pca = pipeline["preprocessor"].transform(X)

    raw_score = pipeline["detector"].decision_function(X_pca)[0]
    score_min, score_max = X_train.min(), X_train.max()
    norm = (raw_score - score_min) / (score_max - score_min + 1e-10)
    is_anomaly = norm < REVIEW_THRESHOLD

    # zero-shot classification
    sims = cosine_similarity(X_pca, list(prototypes.values()))[0]
    top_idx  = np.argsort(sims)[::-1][:TOP_K]
    classes  = list(prototypes.keys())
    top_sims = [float(sims[i]) for i in top_idx]
    top_lbls = [classes[i] for i in top_idx]

    best_sim  = top_sims[0]
    best_lbl  = top_lbls[0]
    seen      = best_sim >= SEEN_SIM_THRESHOLD

    is_attack   = bool(is_anomaly)
    attack_type = best_lbl if is_attack else None

    return {
        "src_ip":      flow["src_ip"],
        "dst_ip":      flow["dst_ip"],
        "src_port":    flow["src_port"],
        "dst_port":    flow["dst_port"],
        "protocol":    flow["protocol"],
        "label":       flow.get("label", ""),
        "is_attack":   is_attack,
        "confidence":  round(float(best_sim), 4),
        "attack_type": attack_type,
        "zsl_seen":    seen,
        "zsl_top":     dict(zip(top_lbls, top_sims)),
        "ts":          time.time(),
    }

# ── Filtering ──────────────────────────────────────────────────────────────────
_NODE_IPS    = {f"192.168.100.{i}" for i in range(10, 16)}
_METALLB_IPS = {f"192.168.100.{i}" for i in range(200, 251)}
_KAFKA_PORTS = {9092, 9093, 9094}

def _skip(flow: dict) -> bool:
    src = flow.get("IP", {}).get("source", "")
    dst = flow.get("IP", {}).get("destination", "")
    l4  = flow.get("l4", {})
    sp  = _port(l4, "source_port")
    dp  = _port(l4, "destination_port")
    def _infra(ip):
        return ip.startswith("10.") or ip in _NODE_IPS or ip in _METALLB_IPS or ip == "192.168.100.1"
    if _infra(src) and _infra(dst): return True
    if sp in _KAFKA_PORTS or dp in _KAFKA_PORTS: return True
    return False

# ── WebSocket push ─────────────────────────────────────────────────────────────
async def _ws_push_loop(queue: asyncio.Queue):
    """持续维护一条到 Django 的 WebSocket 连接，断线自动重连。"""
    headers = {"Authorization": f"Bearer {DJANGO_TOKEN}"}
    backoff = 2
    while True:
        try:
            async with websockets.connect(DJANGO_WS_URL, additional_headers=headers) as ws:
                logger.info("connected to Django: %s", DJANGO_WS_URL)
                backoff = 2
                while True:
                    payload = await queue.get()
                    await ws.send(payload)
                    queue.task_done()
        except Exception as e:
            logger.warning("ws disconnected: %s — retry in %ds", e, backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)


# ── Main loop ──────────────────────────────────────────────────────────────────
def run():
    pipeline, prototypes, X_train = _load()

    consumer = Consumer({
        "bootstrap.servers":         KAFKA_BOOTSTRAP,
        "group.id":                  GROUP_ID,
        "auto.offset.reset":         "latest",
        "enable.auto.commit":        False,
        "fetch.min.bytes":           1024 * 64,
        "fetch.wait.max.ms":         500,
        "broker.address.family":     "v4",
    })
    consumer.subscribe([CONSUME_TOPIC])
    logger.info("consuming %s → pushing to %s", CONSUME_TOPIC, DJANGO_WS_URL)

    # asyncio 事件循环跑 ws push，主线程跑 Kafka 消费
    loop  = asyncio.new_event_loop()
    queue: asyncio.Queue = asyncio.Queue()

    import threading
    def _start_loop():
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_ws_push_loop(queue))

    ws_thread = threading.Thread(target=_start_loop, daemon=True, name="ws-push")
    ws_thread.start()

    open_flows: dict[tuple, list] = defaultdict(list)
    pending:    list[dict]        = []
    last_flush  = time.time()

    try:
        while True:
            msg = consumer.poll(timeout=1.0)

            if msg is None:
                pass
            elif msg.error():
                if msg.error().code() != KafkaError._PARTITION_EOF:
                    raise KafkaException(msg.error())
            else:
                try:
                    event = json.loads(msg.value().decode("utf-8"))
                    flow  = event.get("flow", {})
                    if flow and not _skip(flow):
                        key = _flow_key(flow)
                        pkt = _to_packet(flow)
                        if key in open_flows and open_flows[key]:
                            if pkt["ts"] - open_flows[key][-1]["ts"] > FLOW_TIMEOUT_SEC:
                                pending.append(_compute_flow(open_flows[key]))
                                open_flows[key] = [pkt]
                            else:
                                open_flows[key].append(pkt)
                        else:
                            open_flows[key] = [pkt]
                except Exception as e:
                    logger.debug("skip malformed: %s", e)

            now = time.time()
            if now - last_flush >= 1.0:
                expired = [k for k, pkts in open_flows.items()
                           if pkts and now - pkts[-1]["ts"] >= FLOW_TIMEOUT_SEC]
                for k in expired:
                    pending.append(_compute_flow(open_flows.pop(k)))

                if len(pending) >= BATCH_SIZE:
                    results = [_infer(f, pipeline, prototypes, X_train) for f in pending]
                    payload = json.dumps({"results": results})
                    loop.call_soon_threadsafe(queue.put_nowait, payload)
                    attacks = sum(1 for r in results if r["is_attack"])
                    logger.info("batch %d flows → %d attack(s)", len(results), attacks)
                    consumer.commit(asynchronous=True)
                    pending.clear()

                last_flush = now

    finally:
        consumer.commit(asynchronous=False)
        consumer.close()
        logger.info("detector shut down")


if __name__ == "__main__":
    run()
