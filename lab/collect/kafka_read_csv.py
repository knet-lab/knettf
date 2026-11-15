"""
kafka_read_csv.py — 从 Kafka 读取 Hubble 流量，筛选后写入带标签 CSV

标签规则（严格按源 IP，其余全部跳过）：
  label=1 (attack) : src_ip 在 192.168.100.20-29
  label=0 (normal) : src_ip 在 192.168.100.50-64

输出字段：
  timestamp, verdict, direction, summary,
  src_ip, dst_ip, protocol, src_port, dst_port,
  tcp_flags, is_reply, label

用法示例：
  python3 kafka_read_csv.py --output dataset.csv --max-attack 160000 --max-normal 50000
"""

import subprocess
import json
import sys
import csv
import argparse
from datetime import datetime
from pathlib import Path


KAFKA_POD        = "kafka-broker-0"
KAFKA_NAMESPACE  = "default"
KAFKA_TOPIC      = "ebpf-net-logs"
BOOTSTRAP_SERVER = "localhost:9092"

ATTACK_IPS = {f"192.168.100.{i}" for i in range(20, 30)}
NORMAL_IPS  = {f"192.168.100.{i}" for i in range(50, 65)}

FIELDNAMES = [
    "timestamp", "verdict", "direction", "summary",
    "src_ip", "dst_ip", "protocol", "src_port", "dst_port",
    "tcp_flags", "is_reply", "trace_reason", "label",
]


def classify(src_ip: str):
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
        return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S.%f %Z")
    except Exception:
        return ts_str


def consume(args: argparse.Namespace):
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

    counts = {"attack": 0, "normal": 0, "skipped": 0}

    with output_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        f.flush()

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        print(f"[*] kafka-console-consumer started (PID={proc.pid})", flush=True)

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

                    l4       = flow.get("l4", {})
                    protocol = get_protocol(l4)
                    tcp_flags = (l4.get("TCP") or {}).get("flags")
                    src_ip   = flow.get("IP", {}).get("source", "")

                    label = classify(src_ip)
                    if label is None:
                        counts["skipped"] += 1
                        continue

                    if label == 1 and args.max_attack and counts["attack"] >= args.max_attack:
                        if args.max_normal and counts["normal"] >= args.max_normal:
                            break
                        continue
                    if label == 0 and args.max_normal and counts["normal"] >= args.max_normal:
                        if args.max_attack and counts["attack"] >= args.max_attack:
                            break
                        continue

                    row = {
                        "timestamp": fmt_ts(flow.get("time", "")),
                        "verdict":   flow.get("verdict", ""),
                        "direction": flow.get("traffic_direction", ""),
                        "summary":   flow.get("Summary", ""),
                        "src_ip":    src_ip,
                        "dst_ip":    flow.get("IP", {}).get("destination", ""),
                        "protocol":  protocol,
                        "src_port":  get_port(l4, "source_port"),
                        "dst_port":  get_port(l4, "destination_port"),
                        "tcp_flags":    str(tcp_flags) if tcp_flags else "",
                        "is_reply":     flow.get("is_reply"),
                        "trace_reason": flow.get("trace_reason", ""),
                        "label":        label,
                    }
                    writer.writerow(row)
                    f.flush()

                    if label == 1:
                        counts["attack"] += 1
                    else:
                        counts["normal"] += 1

                    total = counts["attack"] + counts["normal"]
                    if total % 500 == 0:
                        atk_pct = f" ({counts['attack']/args.max_attack*100:.0f}%)" if args.max_attack else ""
                        nrm_pct = f" ({counts['normal']/args.max_normal*100:.0f}%)" if args.max_normal else ""
                        print(
                            f"\r  total={total:,}  attack={counts['attack']:,}{atk_pct}  normal={counts['normal']:,}{nrm_pct}   ",
                            end="", flush=True,
                        )

                    attack_done = (not args.max_attack) or counts["attack"] >= args.max_attack
                    normal_done = (not args.max_normal) or counts["normal"] >= args.max_normal
                    if attack_done and normal_done:
                        print("\n[+] Targets reached — stopping.")
                        break

                except json.JSONDecodeError as e:
                    print(f"\n[parse error] {e} | {line[:80]}", file=sys.stderr)

        except KeyboardInterrupt:
            print("\n[interrupted]")
        finally:
            proc.terminate()
            proc.wait()

    total = counts["attack"] + counts["normal"]
    print(f"\n{'─'*50}")
    print(f"  Output  : {output_path}")
    print(f"  Total   : {total:,}")
    print(f"  Attack  : {counts['attack']:,}  (label=1, src 192.168.100.20-29)")
    print(f"  Normal  : {counts['normal']:,}  (label=0, src 192.168.100.50-64)")
    print(f"  Skipped : {counts['skipped']:,}")
    print(f"{'─'*50}")


def main():
    p = argparse.ArgumentParser(description="Collect labeled traffic from Kafka → CSV")
    p.add_argument("-o", "--output",     default="dataset.csv", help="输出 CSV（默认 dataset.csv）")
    p.add_argument("--max-attack",       dest="max_attack", type=int, default=None, help="攻击样本上限")
    p.add_argument("--max-normal",       dest="max_normal", type=int, default=None, help="正常样本上限")
    p.add_argument("--from-beginning",   dest="from_beginning", action="store_true", help="从头读取")
    p.add_argument("-n",                 type=int, help="最多读取 N 条原始消息")
    args = p.parse_args()

    print(f"Output      : {args.output}")
    print(f"Max attack  : {args.max_attack or 'unlimited'}")
    print(f"Max normal  : {args.max_normal or 'unlimited'}")
    print(f"Mode        : {'from-beginning' if args.from_beginning else 'live (new only)'}")
    print(f"Filter      : src_ip in {{192.168.100.20-29}} OR {{192.168.100.50-64}}\n")
    consume(args)


if __name__ == "__main__":
    main()
