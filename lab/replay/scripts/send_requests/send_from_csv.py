#!/usr/bin/env python3
"""
send_from_csv.py — CSV-driven traffic sender for knetsentinel test environment.

每一行 CSV = 一个 flow，按 flow 特征（协议、端口、TCP flags、total_packets）
构造包集合并发送。每个 flow 分配 flow_uuid，每个包分配 packet_uuid，
全部以 JSONL 格式记录到 record_send_uuid.txt。

完成后写入 send.done，供 read_kafka.py 检测终止。

用法：
  uv run send_from_csv.py
  uv run send_from_csv.py --max-packets 100
  uv run send_from_csv.py --csv ../../test\\ set_20000\\(1\\).csv
"""

import argparse
import csv
import json
import subprocess
import sys
import time
import uuid
from pathlib import Path

from scapy.all import IP, TCP, UDP, ICMP, Raw, send, conf

import config

# IANA 协议号
PROTO_TCP  = "6"
PROTO_UDP  = "17"
PROTO_ICMP = "0"

# ── IP 管理 ───────────────────────────────────────────────────────────────────

def run(cmd: list[str]):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[WARN] {' '.join(cmd)}: {result.stderr.strip()}")
    return result


def add_ips(ips: set[str]):
    print(f"[+] Binding {len(ips)} src IPs to {config.IFACE}")
    for ip in sorted(ips):
        run(["ip", "addr", "add", f"{ip}/24", "dev", config.IFACE])
        print(f"    + {ip}")


def remove_ips(ips: set[str]):
    print(f"\n[+] Releasing {len(ips)} src IPs from {config.IFACE}")
    for ip in sorted(ips):
        run(["ip", "addr", "del", f"{ip}/24", "dev", config.IFACE])
        print(f"    - {ip}")

# ── IP 映射 ───────────────────────────────────────────────────────────────────

def load_mapping(path: Path) -> tuple[dict[str, str], dict[str, str]]:
    data = json.loads(path.read_text())
    src_map = {k: v["mapped_to"] for k, v in data["src"].items()}
    dst_map = {k: v["mapped_to"] for k, v in data["dst"].items()}
    return src_map, dst_map

# ── 包构造 ────────────────────────────────────────────────────────────────────

def _tcp_flags(row: dict) -> str:
    """将 CSV 的布尔 flag 字段还原为 scapy TCP flags 字符串。

    CSV 中各 flag 字段值为 0 或 1（布尔标记，非计数）。
    无任何 flag 时默认 SYN（连接发起）。
    """
    flags = ""
    if row.get("syn_count") == "1": flags += "S"
    if row.get("ack_count") == "1": flags += "A"
    if row.get("fin_count") == "1": flags += "F"
    if row.get("rst_count") == "1": flags += "R"
    if row.get("psh_count") == "1": flags += "P"
    if row.get("urg_count") == "1": flags += "U"
    return flags or "S"


def build_packet(src_ip: str, dst_ip: str, row: dict):
    """根据 CSV flow 行构造 scapy 包，返回 None 表示跳过该行。"""
    proto    = row.get("protocol", "")
    dst_port = int(row["dst_port"]) if row.get("dst_port") and row["dst_port"] != "0" else 80
    src_port = int(row["src_port"]) if row.get("src_port") and row["src_port"] != "0" else 12345

    if proto == PROTO_TCP:
        flags = _tcp_flags(row)
        pkt = IP(src=src_ip, dst=dst_ip) / TCP(sport=src_port, dport=dst_port, flags=flags)
        if "P" in flags:
            pkt = pkt / Raw(b"X" * 16)
        return pkt

    elif proto == PROTO_UDP:
        return IP(src=src_ip, dst=dst_ip) / UDP(sport=src_port, dport=dst_port)

    elif proto == PROTO_ICMP:
        return IP(src=src_ip, dst=dst_ip) / ICMP(type=8, code=0)

    return None

# ── 发送主流程 ────────────────────────────────────────────────────────────────

def send_flows(args: argparse.Namespace):
    src_map, dst_map = load_mapping(args.mapping)

    with open(args.csv, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    # 收集需要绑定到接口的本地 src IP
    needed_src_ips: set[str] = set()
    for row in rows:
        if row["src_ip"] in config.SKIP_SRC or row["dst_ip"] in config.SKIP_DST:
            continue
        mapped = src_map.get(row["src_ip"])
        if mapped:
            needed_src_ips.add(mapped)

    conf.iface = config.IFACE
    add_ips(needed_src_ips)
    time.sleep(0.5)

    total_flows  = 0
    total_pkts   = 0
    skipped_rows = 0

    # 清理上次残留的 done 标记
    args.done.unlink(missing_ok=True)

    try:
        with open(args.record, "w", encoding="utf-8") as rec:
            for i, row in enumerate(rows):
                if row["src_ip"] in config.SKIP_SRC or row["dst_ip"] in config.SKIP_DST:
                    skipped_rows += 1
                    continue

                src_ip = src_map.get(row["src_ip"])
                dst_ip = dst_map.get(row["dst_ip"])
                if not src_ip or not dst_ip:
                    skipped_rows += 1
                    continue

                pkt = build_packet(src_ip, dst_ip, row)
                if pkt is None:
                    skipped_rows += 1
                    continue

                n_pkts = int(row["total_packets"])
                if args.max_packets:
                    n_pkts = min(n_pkts, args.max_packets)

                flow_uid = str(uuid.uuid4())
                pkt_uids = [str(uuid.uuid4()) for _ in range(n_pkts)]

                send(pkt, count=n_pkts, verbose=False, inter=0)

                record = {
                    "flow_uuid":          flow_uid,
                    "csv_row_index":      i,
                    "original_src":       row["src_ip"],
                    "original_dst":       row["dst_ip"],
                    "mapped_src":         src_ip,
                    "mapped_dst":         dst_ip,
                    "protocol":           row["protocol"],
                    "src_port":           row["src_port"],
                    "dst_port":           row["dst_port"],
                    "total_packets_csv":  int(row["total_packets"]),
                    "total_packets_sent": n_pkts,
                    "tcp_flags": _tcp_flags(row) if row["protocol"] == PROTO_TCP else None,
                    "packet_uuids":       pkt_uids,
                }
                rec.write(json.dumps(record, ensure_ascii=False) + "\n")
                rec.flush()

                total_flows += 1
                total_pkts  += n_pkts

                if total_flows % 200 == 0:
                    print(
                        f"  flows={total_flows:,}  pkts={total_pkts:,}  "
                        f"skipped={skipped_rows}",
                        flush=True,
                    )

    except KeyboardInterrupt:
        print("\n[interrupted]")
    finally:
        remove_ips(needed_src_ips)

    # 写入完成标记，read_kafka.py 检测到后进入排水等待并退出
    args.done.write_text(
        json.dumps({"flows_sent": total_flows, "pkts_sent": total_pkts}) + "\n"
    )
    print(f"[+] Written sentinel: {args.done}")

    print(f"\n{'─'*52}")
    print(f"  CSV           : {args.csv}")
    print(f"  Flows sent    : {total_flows:,}")
    print(f"  Packets sent  : {total_pkts:,}")
    print(f"  Rows skipped  : {skipped_rows}")
    print(f"  Record file   : {args.record}")
    print(f"{'─'*52}")

# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(description="CSV-driven traffic sender (knetsentinel)")
    p.add_argument("--csv",        default=str(config.CSV_FILE),     help="输入 CSV 文件")
    p.add_argument("--mapping",    default=config.MAPPING_FILE, type=Path, help="IP 映射 JSON")
    p.add_argument("--record",     default=str(config.RECORD_FILE),  help="UUID 记录输出（JSONL）")
    p.add_argument("--done",       default=config.DONE_FILE,    type=Path, help="完成标记文件路径")
    p.add_argument("--max-packets", dest="max_packets", type=int,
                   default=config.MAX_PACKETS_PER_FLOW,
                   help="每个 flow 最多发包数（默认不限）")
    args = p.parse_args()

    if subprocess.run(["id", "-u"], capture_output=True, text=True).stdout.strip() != "0":
        print("[ERROR] Must run as root (raw socket + ip addr required).")
        sys.exit(1)

    print(f"CSV           : {args.csv}")
    print(f"Mapping       : {args.mapping}")
    print(f"Record        : {args.record}")
    print(f"Done sentinel : {args.done}")
    print(f"Max pkts/flow : {args.max_packets or 'unlimited'}\n")

    send_flows(args)


if __name__ == "__main__":
    main()
