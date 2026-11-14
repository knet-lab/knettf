#!/usr/bin/env python3
"""
aggregate.py — 将 read_result.csv 按顺序每 WINDOW_SIZE 行聚合一次，
输出每窗口一行的统计摘要 CSV。

用法：
  uv run scripts/aggregate.py
  uv run scripts/aggregate.py --captured read_result.csv \
      --output joined_result.csv --window 10000
"""

import argparse
import csv
from pathlib import Path

_HERE    = Path(__file__).parent
DATA_DIR = _HERE.parent

DEFAULT_WINDOW = 10_000


def flush_window(writer, window_idx: int, buf: list[dict]) -> None:
    if not buf:
        return

    ts_list = [r["timestamp"] for r in buf if r.get("timestamp")]
    ts_first = min(ts_list) if ts_list else ""
    ts_last  = max(ts_list) if ts_list else ""

    proto_counts: dict[str, int] = {}
    flag_counts:  dict[str, int] = {}
    verdict_counts: dict[str, int] = {}
    direction_counts: dict[str, int] = {}
    src_ips: set[str] = set()
    dst_ips: set[str] = set()
    reply_count = 0
    label_counts: dict[str, int] = {}

    for r in buf:
        proto = r.get("protocol", "")
        proto_counts[proto] = proto_counts.get(proto, 0) + 1

        flags = r.get("tcp_flags", "").strip()
        if flags and flags not in ("", "{}"):
            flag_counts[flags] = flag_counts.get(flags, 0) + 1

        verdict = r.get("verdict", "")
        if verdict:
            verdict_counts[verdict] = verdict_counts.get(verdict, 0) + 1

        direction = r.get("direction", "")
        if direction:
            direction_counts[direction] = direction_counts.get(direction, 0) + 1

        if r.get("src_ip"):
            src_ips.add(r["src_ip"])
        if r.get("dst_ip"):
            dst_ips.add(r["dst_ip"])

        if r.get("is_reply", "").lower() in ("true", "1"):
            reply_count += 1

        label = r.get("label", "")
        label_counts[label] = label_counts.get(label, 0) + 1

    def fmt_counts(d: dict) -> str:
        return "|".join(f"{k}:{v}" for k, v in sorted(d.items()))

    writer.writerow({
        "window_idx":        window_idx,
        "packet_count":      len(buf),
        "timestamp_first":   ts_first,
        "timestamp_last":    ts_last,
        "proto_counts":      fmt_counts(proto_counts),
        "tcp_flag_counts":   fmt_counts(flag_counts),
        "verdict_counts":    fmt_counts(verdict_counts),
        "direction_counts":  fmt_counts(direction_counts),
        "unique_src_ips":    len(src_ips),
        "unique_dst_ips":    len(dst_ips),
        "reply_count":       reply_count,
        "reply_ratio":       f"{reply_count / len(buf):.4f}",
        "label_counts":      fmt_counts(label_counts),
    })


def main():
    p = argparse.ArgumentParser(description="Tumbling-window aggregation of captured packets")
    p.add_argument("--captured", default=str(DATA_DIR / "read_result.csv"))
    p.add_argument("--output",   default=str(DATA_DIR / "joined_result.csv"))
    p.add_argument("--window",   type=int, default=DEFAULT_WINDOW,
                   help=f"每窗口包数，默认 {DEFAULT_WINDOW}")
    args = p.parse_args()

    print(f"Captured : {args.captured}")
    print(f"Output   : {args.output}")
    print(f"Window   : {args.window} packets/row\n")

    out_fields = [
        "window_idx", "packet_count",
        "timestamp_first", "timestamp_last",
        "proto_counts", "tcp_flag_counts",
        "verdict_counts", "direction_counts",
        "unique_src_ips", "unique_dst_ips",
        "reply_count", "reply_ratio",
        "label_counts",
    ]

    buf: list[dict] = []
    window_idx = 0
    total_packets = 0

    with open(args.captured, encoding="utf-8", newline="") as fin, \
         open(args.output,   "w", encoding="utf-8", newline="") as fout:

        reader = csv.DictReader(fin)
        writer = csv.DictWriter(fout, fieldnames=out_fields)
        writer.writeheader()

        for row in reader:
            buf.append(row)
            total_packets += 1

            if len(buf) >= args.window:
                flush_window(writer, window_idx, buf)
                window_idx += 1
                buf = []

        if buf:
            flush_window(writer, window_idx, buf)
            window_idx += 1

    print(f"{'─'*48}")
    print(f"  总包数     : {total_packets:,}")
    print(f"  窗口大小   : {args.window:,} packets")
    print(f"  输出行数   : {window_idx:,}")
    print(f"{'─'*48}")
    print(f"  输出文件   : {args.output}")


if __name__ == "__main__":
    main()
