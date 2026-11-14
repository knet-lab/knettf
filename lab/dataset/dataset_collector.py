#!/usr/bin/env python3
"""
dataset_collector.py — 从 Kafka ebpf-net-logs 采集流量并输出带标签 CSV

标签规则（严格按源 IP 过滤，其余流量全部丢弃）：
  label=1 (attack)  : src_ip 在 192.168.100.20-29  （spoof_attack.py FAKE_IPS）
  label=0 (normal)  : src_ip 在 192.168.100.50-64  （send_request.py SOURCE_IPS）
  其他来源           : 直接跳过，不写入 CSV

输出字段（11个特征 + label）：
  timestamp, verdict, direction, summary,
  src_ip, dst_ip, protocol, src_port, dst_port,
  tcp_flags, is_reply, label
"""

import subprocess
import json
import sys
import csv
import argparse
import re
from datetime import datetime, timezone
from pathlib import Path

# ── Kafka 连接配置 ────────────────────────────────────────────────────────────
KAFKA_POD        = "kafka-broker-0"
KAFKA_NAMESPACE  = "default"
KAFKA_TOPIC      = "ebpf-net-logs"
BOOTSTRAP_SERVER = "localhost:9092"

# 攻击源 IP：192.168.100.20-29
ATTACK_IPS = {f"192.168.100.{i}" for i in range(20, 30)}

# 正常流量源 IP：192.168.100.50-64
NORMAL_IPS = {f"192.168.100.{i}" for i in range(50, 65)}


def classify(src_ip: str):
    """返回 1（attack）、0（normal）或 None（不在白名单，跳过）。"""
    if src_ip in ATTACK_IPS:
        return 1
    if src_ip in NORMAL_IPS:
        return 0
    return None


def get_protocol(l4: dict) -> str:
    for p in ("TCP", "UDP", "ICMPv4", "ICMPv6"):
        if p in l4:
            return p
    return "OTHER"


def get_port(l4: dict, side: str):
    for proto in ("TCP", "UDP"):
        if proto in l4 and side in l4[proto]:
            return l4[proto][side]
    return None


def fmt_ts(ts_str: str) -> str:
    try:
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    except Exception:
        return ts_str


def extract_row(flow: dict) -> dict:
    l4       = flow.get("l4", {})
    protocol = get_protocol(l4)
    tcp_flags = (l4.get("TCP") or {}).get("flags")

    return {
        "timestamp": fmt_ts(flow.get("time", "")),
        "verdict":   flow.get("verdict", ""),
        "direction": flow.get("traffic_direction", ""),
        "summary":   flow.get("Summary", ""),
        "src_ip":    flow.get("IP", {}).get("source", ""),
        "dst_ip":    flow.get("IP", {}).get("destination", ""),
        "protocol":  protocol,
        "src_port":  get_port(l4, "source_port"),
        "dst_port":  get_port(l4, "destination_port"),
        "tcp_flags": str(tcp_flags) if tcp_flags else "",
        "is_reply":  flow.get("is_reply"),
    }


FIELDNAMES = [
    "timestamp", "verdict", "direction", "summary",
    "src_ip", "dst_ip", "protocol", "src_port", "dst_port",
    "tcp_flags", "is_reply", "label",
]


def collect(args: argparse.Namespace):
    output_path = Path(args.output)
    cmd = [
        "kubectl", "exec", "-n", KAFKA_NAMESPACE, KAFKA_POD, "--",
        "/opt/kafka/bin/kafka-console-consumer.sh",
        "--bootstrap-server", BOOTSTRAP_SERVER,
        "--topic", KAFKA_TOPIC,
    ]
    if args.from_beginning:
        cmd.append("--from-beginning")
    if args.n:
        cmd += ["--max-messages", str(args.n)]

    counts   = {"attack": 0, "normal": 0, "skipped": 0}
    max_attack = args.max_attack
    max_normal = args.max_normal

    with output_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        f.flush()

        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        try:
            for line in proc.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    flow  = event.get("flow", {})
                    if not flow:
                        counts["skipped"] += 1
                        continue

                    row   = extract_row(flow)
                    label = classify(row["src_ip"])

                    if label is None:
                        counts["skipped"] += 1
                        continue

                    if label == 1:
                        if max_attack and counts["attack"] >= max_attack:
                            continue
                        counts["attack"] += 1
                    else:
                        if max_normal and counts["normal"] >= max_normal:
                            continue
                        counts["normal"] += 1

                    row["label"] = label
                    writer.writerow(row)
                    f.flush()

                    total = counts["attack"] + counts["normal"]
                    if total % 1000 == 0:
                        atk_pct = f"({counts['attack']/max_attack*100:.0f}%)" if max_attack else ""
                        nrm_pct = f"({counts['normal']/max_normal*100:.0f}%)" if max_normal else ""
                        print(
                            f"\r  total={total:,}  "
                            f"attack={counts['attack']:,}{atk_pct}  "
                            f"normal={counts['normal']:,}{nrm_pct}   ",
                            end="", flush=True,
                        )

                    attack_done = (max_attack is None) or (counts["attack"] >= max_attack)
                    normal_done = (max_normal is None) or (counts["normal"] >= max_normal)
                    if attack_done and normal_done:
                        print("\n[targets reached — stopping]")
                        break

                except json.JSONDecodeError as e:
                    print(f"\n[parse error] {e} | {line[:80]}", file=sys.stderr)
                    counts["skipped"] += 1

        except KeyboardInterrupt:
            print("\n[interrupted]")
        finally:
            proc.terminate()
            proc.wait()

    total = counts["attack"] + counts["normal"]
    print(f"\n\n{'─'*50}")
    print(f"  Output     : {output_path}")
    print(f"  Total rows : {total:,}")
    print(f"  Attack (1) : {counts['attack']:,}")
    print(f"  Normal (0) : {counts['normal']:,}")
    print(f"  Skipped    : {counts['skipped']:,}  (IP 不在白名单)")
    print(f"{'─'*50}")
    print(f"\n  Attack IPs : 192.168.100.20-29")
    print(f"  Normal IPs : 192.168.100.50-64")


def main():
    p = argparse.ArgumentParser(
        description="Collect labeled traffic dataset from Kafka (ebpf-net-logs)"
    )
    p.add_argument("-o", "--output", default="dataset.csv",
                   help="输出 CSV 文件路径（默认: dataset.csv）")
    p.add_argument("--from-beginning", dest="from_beginning", action="store_true",
                   help="从头读取历史消息")
    p.add_argument("-n", type=int,
                   help="最多从 Kafka 读取 N 条原始消息后退出")
    p.add_argument("--max-attack", dest="max_attack", type=int, default=None,
                   help="攻击样本上限，达到后跳过（默认不限）")
    p.add_argument("--max-normal", dest="max_normal", type=int, default=None,
                   help="正常样本上限，达到后跳过（默认不限）")
    args = p.parse_args()

    print(f"Topic      : {KAFKA_TOPIC}  |  Pod: {KAFKA_NAMESPACE}/{KAFKA_POD}")
    print(f"Output     : {args.output}")
    print(f"Mode       : {'from-beginning' if args.from_beginning else 'live (new messages only)'}")
    print(f"Max attack : {args.max_attack if args.max_attack else 'unlimited'}")
    print(f"Max normal : {args.max_normal if args.max_normal else 'unlimited'}")
    print(f"Filter     : src_ip in {{192.168.100.20-29}} OR {{192.168.100.50-64}}\n")
    collect(args)


if __name__ == "__main__":
    main()
