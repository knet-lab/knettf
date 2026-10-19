"""
vigil_bridge.py — Kafka → in-memory aggregation → NetSentinel vigil API

消费 ebpf-net-logs Kafka topic，将逐包 Hubble 事件聚合成 30 特征流记录，
通过 HTTP POST 推送到 NetSentinel /api/vigil/detect/batch/，无文件落盘。

用法：
    uv run python kafka/vigil_bridge.py [--backend http://localhost:8080] \
        [--token <jwt>] [--window 5] [--batch-size 20] [--from-beginning]
"""

import argparse
import json
import subprocess
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from typing import Optional

import requests

# ── Kafka 配置 ────────────────────────────────────────────────────────────────
KAFKA_POD        = "kafka-broker-0"
KAFKA_NAMESPACE  = "default"
KAFKA_TOPIC      = "ebpf-net-logs"
BOOTSTRAP_SERVER = "localhost:9092"

# ── 默认参数 ──────────────────────────────────────────────────────────────────
DEFAULT_BACKEND    = "http://localhost:8080"
DEFAULT_WINDOW_SEC = 5      # 流超时窗口（秒）
DEFAULT_BATCH_SIZE = 20     # 达到此数量立即推送


# ── 流聚合状态 ────────────────────────────────────────────────────────────────
@dataclass
class FlowState:
    src_ip: str = ""
    dst_ip: str = ""
    src_port: int = 0
    dst_port: int = 0
    protocol: str = "TCP"
    label: str = ""

    pkt_count: int = 0
    byte_count: int = 0
    reply_count: int = 0
    fwd_count: int = 0
    drop_count: int = 0

    # TCP flag counters
    syn_count: int = 0
    ack_count: int = 0
    fin_count: int = 0
    rst_count: int = 0
    psh_count: int = 0
    urg_count: int = 0

    # timing
    first_ts: float = 0.0
    last_ts:  float = 0.0
    inter_arrival_sum: float = 0.0
    prev_ts: float = 0.0

    # port/IP diversity
    dst_ports: set = field(default_factory=set)
    src_ips:   set = field(default_factory=set)

    # payload size tracking
    pkt_sizes: list = field(default_factory=list)


def _parse_protocol(l4: dict) -> str:
    for proto in ("TCP", "UDP", "ICMPv4", "ICMPv6"):
        if proto in l4:
            return proto
    return "OTHER"


def _get_port(l4: dict, side: str) -> int:
    for proto in ("TCP", "UDP"):
        if proto in l4 and side in l4[proto]:
            return int(l4[proto][side])
    return 0


def _tcp_flags(l4: dict) -> dict:
    flags = (l4.get("TCP") or {}).get("flags") or {}
    return flags if isinstance(flags, dict) else {}


def _est_pkt_size(flow: dict) -> int:
    # Hubble doesn't carry raw byte counts; we approximate from l7 or default 64
    l7 = flow.get("l7", {})
    if "http" in l7:
        return 200
    return 64


def _safe_ts(ts_str: str) -> float:
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return dt.timestamp()
    except Exception:
        return time.time()


def _flow_key(flow: dict) -> tuple:
    l4       = flow.get("l4", {})
    src_ip   = flow.get("IP", {}).get("source", "")
    dst_ip   = flow.get("IP", {}).get("destination", "")
    src_port = _get_port(l4, "source_port")
    dst_port = _get_port(l4, "destination_port")
    protocol = _parse_protocol(l4)
    return (src_ip, dst_ip, src_port, dst_port, protocol)


def update_state(state: FlowState, flow: dict):
    ts      = _safe_ts(flow.get("time", ""))
    verdict = flow.get("verdict", "")
    is_reply= flow.get("is_reply", False)
    l4      = flow.get("l4", {})
    flags   = _tcp_flags(l4)
    pkt_sz  = _est_pkt_size(flow)

    state.pkt_count  += 1
    state.byte_count += pkt_sz
    state.pkt_sizes.append(pkt_sz)

    if state.first_ts == 0.0:
        state.first_ts = ts
    if state.prev_ts > 0:
        state.inter_arrival_sum += ts - state.prev_ts
    state.prev_ts  = ts
    state.last_ts  = ts

    if is_reply:
        state.reply_count += 1
    if verdict == "FORWARDED":
        state.fwd_count  += 1
    elif verdict == "DROPPED":
        state.drop_count += 1

    if flags.get("SYN"):  state.syn_count += 1
    if flags.get("ACK"):  state.ack_count += 1
    if flags.get("FIN"):  state.fin_count += 1
    if flags.get("RST"):  state.rst_count += 1
    if flags.get("PSH"):  state.psh_count += 1
    if flags.get("URG"):  state.urg_count += 1

    dst_ip   = flow.get("IP", {}).get("destination", "")
    dst_port = _get_port(l4, "destination_port")
    src_ip   = flow.get("IP", {}).get("source", "")
    state.dst_ports.add(dst_port)
    state.src_ips.add(src_ip)

    # label from source IP range (192.168.100.20-29 = attack, .50-64 = normal)
    if not state.label:
        try:
            last = int(src_ip.split(".")[-1])
            if 20 <= last <= 29:
                state.label = "attack"
            elif 50 <= last <= 64:
                state.label = "normal"
        except Exception:
            pass


def state_to_flow_dict(state: FlowState) -> dict:
    duration  = max(state.last_ts - state.first_ts, 1e-6)
    pps       = state.pkt_count / duration
    bps       = state.byte_count / duration
    mean_size = state.byte_count / max(state.pkt_count, 1)
    inter_arr = state.inter_arrival_sum / max(state.pkt_count - 1, 1)
    syn_ratio = state.syn_count / max(state.pkt_count, 1)
    reply_ratio = state.reply_count / max(state.pkt_count, 1)
    drop_ratio  = state.drop_count / max(state.pkt_count, 1)

    import statistics
    std_size = statistics.stdev(state.pkt_sizes) if len(state.pkt_sizes) > 1 else 0.0

    return {
        "src_ip":            state.src_ip,
        "dst_ip":            state.dst_ip,
        "src_port":          state.src_port,
        "dst_port":          state.dst_port,
        "protocol":          state.protocol,
        "label":             state.label,
        "pkt_count":         state.pkt_count,
        "byte_count":        state.byte_count,
        "duration":          round(duration, 6),
        "pps":               round(pps, 4),
        "bps":               round(bps, 4),
        "mean_pkt_size":     round(mean_size, 2),
        "std_pkt_size":      round(std_size, 2),
        "inter_arrival_mean": round(inter_arr, 6),
        "syn_count":         state.syn_count,
        "ack_count":         state.ack_count,
        "fin_count":         state.fin_count,
        "rst_count":         state.rst_count,
        "psh_count":         state.psh_count,
        "urg_count":         state.urg_count,
        "syn_ratio":         round(syn_ratio, 4),
        "reply_ratio":       round(reply_ratio, 4),
        "fwd_count":         state.fwd_count,
        "drop_count":        state.drop_count,
        "drop_ratio":        round(drop_ratio, 4),
        "unique_dst_ports":  len(state.dst_ports),
        "unique_src_ips":    len(state.src_ips),
        "is_reply":          state.reply_count > 0,
        "has_syn":           state.syn_count > 0,
    }


# ── HTTP 推送 ─────────────────────────────────────────────────────────────────
def push_batch(flows: list[dict], backend: str, token: Optional[str]):
    url     = f"{backend.rstrip('/')}/api/vigil/detect/batch/"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    payload = {"flows": flows}
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            attacks = sum(1 for r in (data.get("data", {}).get("results") or []) if r.get("is_attack"))
            print(f"[push] {len(flows)} flows → {attacks} attack(s) detected", flush=True)
        else:
            print(f"[push] HTTP {resp.status_code}: {resp.text[:200]}", file=sys.stderr, flush=True)
    except requests.RequestException as e:
        print(f"[push] error: {e}", file=sys.stderr, flush=True)


# ── 主循环 ────────────────────────────────────────────────────────────────────
def run(args: argparse.Namespace):
    states: dict[tuple, FlowState] = {}
    pending: list[dict]             = []

    cmd = [
        "kubectl", "exec", "-n", KAFKA_NAMESPACE, KAFKA_POD, "--",
        "/opt/kafka/bin/kafka-console-consumer.sh",
        "--bootstrap-server", BOOTSTRAP_SERVER,
        "--topic", KAFKA_TOPIC,
    ]
    if args.from_beginning:
        cmd.append("--from-beginning")

    print(f"[bridge] connecting to {KAFKA_NAMESPACE}/{KAFKA_POD} topic={KAFKA_TOPIC}", flush=True)
    print(f"[bridge] backend={args.backend}  window={args.window}s  batch={args.batch_size}", flush=True)

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    last_flush = time.time()

    def flush_expired():
        now = time.time()
        expired_keys = [k for k, s in states.items() if now - s.last_ts >= args.window]
        for k in expired_keys:
            pending.append(state_to_flow_dict(states.pop(k)))
        if len(pending) >= args.batch_size:
            push_batch(pending, args.backend, args.token)
            pending.clear()

    try:
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
                if key not in states:
                    l4 = flow.get("l4", {})
                    states[key] = FlowState(
                        src_ip   = flow.get("IP", {}).get("source", ""),
                        dst_ip   = flow.get("IP", {}).get("destination", ""),
                        src_port = _get_port(l4, "source_port"),
                        dst_port = _get_port(l4, "destination_port"),
                        protocol = _parse_protocol(l4),
                    )
                update_state(states[key], flow)

            except json.JSONDecodeError:
                continue

            # periodic flush
            now = time.time()
            if now - last_flush >= 1.0:
                flush_expired()
                last_flush = now

    except KeyboardInterrupt:
        pass
    finally:
        proc.terminate()
        proc.wait()
        # flush remaining
        for s in states.values():
            pending.append(state_to_flow_dict(s))
        if pending:
            push_batch(pending, args.backend, args.token)
        print(f"\n[bridge] stopped.", flush=True)


def main():
    p = argparse.ArgumentParser(description="Kafka → Vigil bridge (no file I/O)")
    p.add_argument("--backend",      default=DEFAULT_BACKEND,    help="NetSentinel backend URL")
    p.add_argument("--token",        default=None,               help="JWT Bearer token")
    p.add_argument("--window",       type=float, default=DEFAULT_WINDOW_SEC, help="流超时窗口（秒）")
    p.add_argument("--batch-size",   type=int,   default=DEFAULT_BATCH_SIZE, dest="batch_size")
    p.add_argument("--from-beginning", dest="from_beginning", action="store_true")
    run(p.parse_args())


if __name__ == "__main__":
    main()
