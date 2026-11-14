#!/usr/bin/env python3
"""
read_kafka.py — 从 Kafka 读取 Hubble 流量并写入 CSV。

过滤条件：src_ip 在 192.168.100.50-64（send_from_csv.py 映射后的 normal IP 池）。

终止策略（优先级从高到低）：
  1. 检测到 send.done 文件出现 → 再等待 DRAIN_WAIT_SEC 秒后退出
  2. --max-rows 达到上限
  3. Ctrl+C

用法：
  uv run read_kafka.py                        # 监听新流量
  uv run read_kafka.py --from-beginning       # 从头读取历史消息
  uv run read_kafka.py --max-rows 5000        # 最多采集 5000 条
  uv run read_kafka.py -n 10000              # 最多读取 10000 条原始 Kafka 消息
"""

import argparse
import csv
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import config

# ── 解析工具 ──────────────────────────────────────────────────────────────────

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

# ── Kafka 消费 ────────────────────────────────────────────────────────────────

def consume(args: argparse.Namespace):
    cmd = [
        "kubectl", "exec", "-n", config.KAFKA_NAMESPACE, config.KAFKA_POD, "--",
        "/opt/kafka/bin/kafka-console-consumer.sh",
        "--bootstrap-server", config.BOOTSTRAP_SERVER,
        "--topic", config.KAFKA_TOPIC,
    ]
    if args.from_beginning:
        cmd.append("--from-beginning")
    if args.n:
        cmd += ["--max-messages", str(args.n)]

    counts = {"written": 0, "skipped": 0}
    drain_start: float | None = None   # send.done 检测到的时间戳

    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=config.FIELDNAMES)
        writer.writeheader()
        f.flush()

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        print(f"[*] kafka-console-consumer started (PID={proc.pid})", flush=True)

        try:
            for line in proc.stdout:
                # ── 终止检查：send.done ──────────────────────────────────
                if drain_start is None and args.done.exists():
                    drain_start = time.monotonic()
                    print(
                        f"\n[+] send.done detected — draining for {config.DRAIN_WAIT_SEC}s ...",
                        flush=True,
                    )

                if drain_start is not None:
                    if time.monotonic() - drain_start >= config.DRAIN_WAIT_SEC:
                        print("[+] Drain complete — stopping.")
                        break

                line = line.strip()
                if not line:
                    continue

                try:
                    event = json.loads(line)
                    flow  = event.get("flow", {})
                    if not flow:
                        counts["skipped"] += 1
                        continue

                    src_ip = flow.get("IP", {}).get("source", "")
                    if src_ip not in config.CAPTURE_SRC_IPS:
                        counts["skipped"] += 1
                        continue

                    l4       = flow.get("l4", {})
                    protocol = get_protocol(l4)
                    tcp_flags = (l4.get("TCP") or {}).get("flags")

                    row = {
                        "timestamp":    fmt_ts(flow.get("time", "")),
                        "verdict":      flow.get("verdict", ""),
                        "direction":    flow.get("traffic_direction", ""),
                        "summary":      flow.get("Summary", ""),
                        "src_ip":       src_ip,
                        "dst_ip":       flow.get("IP", {}).get("destination", ""),
                        "protocol":     protocol,
                        "src_port":     get_port(l4, "source_port"),
                        "dst_port":     get_port(l4, "destination_port"),
                        "tcp_flags":    str(tcp_flags) if tcp_flags else "",
                        "is_reply":     flow.get("is_reply"),
                        "trace_reason": flow.get("trace_reason", ""),
                        "label":        config.FIXED_LABEL,
                    }
                    writer.writerow(row)
                    f.flush()
                    counts["written"] += 1

                    if args.max_rows and counts["written"] >= args.max_rows:
                        print(f"\n[+] max-rows {args.max_rows} reached — stopping.")
                        break

                    if counts["written"] % 500 == 0:
                        print(
                            f"\r  written={counts['written']:,}  skipped={counts['skipped']:,}   ",
                            end="", flush=True,
                        )

                except json.JSONDecodeError as e:
                    print(f"\n[parse error] {e} | {line[:80]}", file=sys.stderr)

        except KeyboardInterrupt:
            print("\n[interrupted]")
        finally:
            proc.terminate()
            proc.wait()

    print(f"\n{'─'*52}")
    print(f"  Output  : {args.output}")
    print(f"  Written : {counts['written']:,}")
    print(f"  Skipped : {counts['skipped']:,}")
    print(f"  Filter  : src_ip in 192.168.100.50-64")
    print(f"{'─'*52}")

# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(description="Kafka reader for zhouyang_request captures")
    p.add_argument("-o", "--output",
                   default=str(config.OUTPUT_CSV),
                   help=f"输出 CSV（默认 {config.OUTPUT_CSV.name}）")
    p.add_argument("--done",
                   default=config.DONE_FILE, type=Path,
                   help="send.done 文件路径（send_from_csv.py 写入）")
    p.add_argument("--drain-wait",
                   dest="drain_wait", type=int, default=config.DRAIN_WAIT_SEC,
                   help=f"检测到 send.done 后排水等待秒数（默认 {config.DRAIN_WAIT_SEC}）")
    p.add_argument("--max-rows",
                   dest="max_rows", type=int, default=None,
                   help="最多写入 N 行后停止")
    p.add_argument("--from-beginning",
                   dest="from_beginning", action="store_true",
                   help="从头读取历史消息")
    p.add_argument("-n", type=int,
                   help="最多读取 N 条原始 Kafka 消息")
    args = p.parse_args()

    # drain_wait 可通过 CLI 覆盖 config 值
    config.DRAIN_WAIT_SEC = args.drain_wait

    print(f"Output      : {args.output}")
    print(f"Done file   : {args.done}")
    print(f"Drain wait  : {config.DRAIN_WAIT_SEC}s after send.done")
    print(f"Max rows    : {args.max_rows or 'unlimited'}")
    print(f"Mode        : {'from-beginning' if args.from_beginning else 'live (new only)'}")
    print(f"Filter      : src_ip in 192.168.100.50-64\n")

    consume(args)


if __name__ == "__main__":
    main()
