"""
aggregate_flows.py — 将 kafka_read_csv.py 输出的逐条记录 CSV 聚合为流级别特征 CSV

流定义：相同五元组（src_ip, dst_ip, src_port, dst_port, protocol）中，
相邻两包时间差超过 --timeout 秒则切割为新流。

用法：
  python3 aggregate_flows.py --input dataset.csv --output flows.csv
  python3 aggregate_flows.py --input dataset.csv --output flows.csv --timeout 5
"""

import csv
import argparse
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path


TIMESTAMP_FMTS = [
    "%Y-%m-%d %H:%M:%S %Z",
    "%Y-%m-%d %H:%M:%S",
]


def parse_ts(s: str) -> float:
    for fmt in TIMESTAMP_FMTS:
        try:
            return datetime.strptime(s.strip(), fmt).timestamp()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse timestamp: {s!r}")


def parse_flags(flags_str: str) -> dict:
    if not flags_str:
        return {}
    flags = {}
    for name in ("SYN", "ACK", "FIN", "RST", "PSH", "URG"):
        flags[name] = f"'{name}': True" in flags_str
    return flags


def mean(values):
    return sum(values) / len(values) if values else 0.0


def std(values):
    if len(values) < 2:
        return 0.0
    m = mean(values)
    return math.sqrt(sum((v - m) ** 2 for v in values) / len(values))


FLOW_FIELDS = [
    "src_ip", "dst_ip", "src_port", "dst_port", "protocol",
    "flow_duration",
    "total_packets", "fwd_packets", "bwd_packets", "fwd_ratio",
    "packets_per_second",
    "iat_mean", "iat_std", "iat_min", "iat_max",
    "syn_count", "ack_count", "fin_count", "rst_count", "psh_count", "urg_count",
    "syn_ratio", "ack_ratio", "fin_ratio", "rst_ratio",
    "reply_count", "reply_ratio",
    "forwarded_count", "drop_count", "drop_ratio",
    "is_bidirectional",
    "is_tcp", "is_udp", "is_icmp",
    "is_well_known_port",
    "label",
]


def compute_flow(packets: list) -> dict:
    packets.sort(key=lambda p: p["ts"])

    timestamps = [p["ts"] for p in packets]
    t_start, t_end = timestamps[0], timestamps[-1]
    duration = max(t_end - t_start, 1e-6)

    iats = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps)-1)]

    fwd = sum(1 for p in packets if p["direction"] == "INGRESS")
    bwd = len(packets) - fwd
    total = len(packets)

    flags_total = defaultdict(int)
    for p in packets:
        for flag, val in p["flags"].items():
            if val:
                flags_total[flag] += 1

    replies = sum(1 for p in packets if p["is_reply"])
    forwarded = sum(1 for p in packets if p["verdict"] == "FORWARDED")
    dropped = total - forwarded

    proto = packets[0]["protocol"]
    directions = {p["direction"] for p in packets}

    labels = [p["label"] for p in packets if p["label"] != ""]
    label = max(set(labels), key=labels.count) if labels else ""

    def ratio(count, total):
        return round(count / total, 4) if total else 0.0

    return {
        "src_ip":    packets[0]["src_ip"],
        "dst_ip":    packets[0]["dst_ip"],
        "src_port":  packets[0]["src_port"],
        "dst_port":  packets[0]["dst_port"],
        "protocol":  proto,
        "flow_duration":      round(duration, 4),
        "total_packets":      total,
        "fwd_packets":        fwd,
        "bwd_packets":        bwd,
        "fwd_ratio":          ratio(fwd, total),
        "packets_per_second": round(total / duration, 4),
        "iat_mean": round(mean(iats), 6) if iats else 0.0,
        "iat_std":  round(std(iats),  6) if iats else 0.0,
        "iat_min":  round(min(iats),  6) if iats else 0.0,
        "iat_max":  round(max(iats),  6) if iats else 0.0,
        "syn_count": flags_total["SYN"],
        "ack_count": flags_total["ACK"],
        "fin_count": flags_total["FIN"],
        "rst_count": flags_total["RST"],
        "psh_count": flags_total["PSH"],
        "urg_count": flags_total["URG"],
        "syn_ratio": ratio(flags_total["SYN"], total),
        "ack_ratio": ratio(flags_total["ACK"], total),
        "fin_ratio": ratio(flags_total["FIN"], total),
        "rst_ratio": ratio(flags_total["RST"], total),
        "reply_count":   replies,
        "reply_ratio":   ratio(replies, total),
        "forwarded_count": forwarded,
        "drop_count":      dropped,
        "drop_ratio":      ratio(dropped, total),
        "is_bidirectional":   int(len(directions) > 1),
        "is_tcp":  int(proto == "TCP"),
        "is_udp":  int(proto == "UDP"),
        "is_icmp": int(proto in ("ICMPv4", "ICMPv6")),
        "is_well_known_port": int(str(packets[0]["dst_port"]).isdigit() and int(packets[0]["dst_port"] or 0) < 1024),
        "label": label,
    }


def aggregate(input_path: Path, output_path: Path, timeout: float):
    # flow_key -> list of packets still open
    open_flows: dict[tuple, list] = defaultdict(list)

    completed: list[dict] = []
    total_in = 0
    skipped = 0

    with input_path.open(newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Sort all rows by timestamp first
    parsed = []
    for row in rows:
        try:
            ts = parse_ts(row["timestamp"])
        except ValueError:
            skipped += 1
            continue
        parsed.append((ts, row))
    parsed.sort(key=lambda x: x[0])

    for ts, row in parsed:
        total_in += 1
        key = (row["src_ip"], row["dst_ip"], row["src_port"], row["dst_port"], row["protocol"])

        pkt = {
            "ts":        ts,
            "direction": row.get("direction", ""),
            "verdict":   row.get("verdict", ""),
            "flags":     parse_flags(row.get("tcp_flags", "")),
            "is_reply":  row.get("is_reply", "").lower() == "true",
            "label":     row.get("label", ""),
            "src_ip":    row["src_ip"],
            "dst_ip":    row["dst_ip"],
            "src_port":  row["src_port"],
            "dst_port":  row["dst_port"],
            "protocol":  row["protocol"],
        }

        if key in open_flows:
            last_ts = open_flows[key][-1]["ts"]
            if ts - last_ts > timeout:
                # flush old flow, start new
                completed.append(compute_flow(open_flows[key]))
                open_flows[key] = [pkt]
            else:
                open_flows[key].append(pkt)
        else:
            open_flows[key] = [pkt]

    # flush remaining open flows
    for pkts in open_flows.values():
        if pkts:
            completed.append(compute_flow(pkts))

    with output_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FLOW_FIELDS)
        writer.writeheader()
        writer.writerows(completed)

    print(f"Input packets : {total_in:,}  (skipped {skipped})")
    print(f"Output flows  : {len(completed):,}")
    print(f"Timeout used  : {timeout}s")
    attack = sum(1 for r in completed if str(r["label"]) == "1")
    normal = sum(1 for r in completed if str(r["label"]) == "0")
    print(f"Attack flows  : {attack:,}  (label=1)")
    print(f"Normal flows  : {normal:,}  (label=0)")
    print(f"Saved to      : {output_path}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input",   "-i", default="dataset.csv", help="输入 CSV（默认 dataset.csv）")
    p.add_argument("--output",  "-o", default="flows.csv",   help="输出 CSV（默认 flows.csv）")
    p.add_argument("--timeout", "-t", type=float, default=5.0,
                   help="流超时秒数：相邻包间隔超过此值则切割为新流（默认 5.0）")
    args = p.parse_args()

    aggregate(Path(args.input), Path(args.output), args.timeout)


if __name__ == "__main__":
    main()
