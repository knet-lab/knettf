#!/usr/bin/env python3
"""
Normal traffic generator — multi-protocol mix (TCP/UDP/ICMP).
Sends from 192.168.100.50-64 to K8s nodes via virbr-k8s so Hubble sees original source IPs.
"""

import subprocess
import sys
import random
import time
from scapy.all import IP, TCP, UDP, ICMP, DNS, DNSQR, Raw, send, conf

IFACE = "virbr-k8s"

NORMAL_IPS = [f"192.168.100.{i}" for i in range(50, 65)]  # 15 IPs

NODE_IPS = [
    "192.168.100.10",  # k8s-master
    "192.168.100.11",  # k8s-node1
    "192.168.100.12",  # k8s-node2
    "192.168.100.13",  # k8s-node3
    "192.168.100.14",  # k8s-node4
]

PACKETS_PER_ROUND = 100


def run(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[WARN] {' '.join(cmd)}: {result.stderr.strip()}")
    return result


def add_ips():
    print(f"[+] Adding {len(NORMAL_IPS)} normal IPs to {IFACE}")
    for ip in NORMAL_IPS:
        run(["ip", "addr", "add", f"{ip}/24", "dev", IFACE])
        print(f"    added {ip}")


def remove_ips():
    print(f"\n[+] Removing {len(NORMAL_IPS)} normal IPs from {IFACE}")
    for ip in NORMAL_IPS:
        run(["ip", "addr", "del", f"{ip}/24", "dev", IFACE])
        print(f"    removed {ip}")


def make_packet(src, dst):
    """Return a random-protocol packet simulating realistic normal traffic."""
    sport = random.randint(1024, 65535)
    choice = random.random()

    if choice < 0.30:
        # TCP HTTP
        return IP(src=src, dst=dst) / TCP(sport=sport, dport=80, flags="S")
    elif choice < 0.45:
        # TCP HTTPS
        return IP(src=src, dst=dst) / TCP(sport=sport, dport=443, flags="S")
    elif choice < 0.55:
        # TCP SSH
        return IP(src=src, dst=dst) / TCP(sport=sport, dport=22, flags="S")
    elif choice < 0.62:
        # TCP kube-apiserver
        return IP(src=src, dst=dst) / TCP(sport=sport, dport=6443, flags="S")
    elif choice < 0.72:
        # UDP DNS query
        return IP(src=src, dst=dst) / UDP(sport=sport, dport=53) / DNS(rd=1, qd=DNSQR(qname="kubernetes.default.svc"))
    elif choice < 0.80:
        # UDP NTP
        return IP(src=src, dst=dst) / UDP(sport=sport, dport=123) / Raw(b"\x1b" + b"\x00" * 47)
    elif choice < 0.88:
        # UDP syslog
        return IP(src=src, dst=dst) / UDP(sport=sport, dport=514) / Raw(b"<14>normal heartbeat")
    elif choice < 0.95:
        # ICMP echo
        return IP(src=src, dst=dst) / ICMP(type=8, code=0)
    else:
        # TCP ACK (established session simulation)
        return IP(src=src, dst=dst) / TCP(sport=sport, dport=random.choice([80, 443, 22]), flags="A")


def run_normal():
    conf.iface = IFACE
    total = 0
    pairs = [(src, dst) for src in NORMAL_IPS for dst in NODE_IPS]

    for rnd in range(PACKETS_PER_ROUND):
        random.shuffle(pairs)
        for src, dst in pairs:
            pkt = make_packet(src, dst)
            send(pkt, verbose=False)
            total += 1
        if (rnd + 1) % 10 == 0:
            print(f"  round {rnd+1}/{PACKETS_PER_ROUND}  sent={total}", flush=True)

    print(f"\n[+] Total packets sent: {total}")


def main():
    import argparse
    global PACKETS_PER_ROUND
    p = argparse.ArgumentParser()
    p.add_argument("--packets", type=int, default=PACKETS_PER_ROUND,
                   help=f"轮次数，每轮对所有 src×dst 组合各发一个随机协议包（默认 {PACKETS_PER_ROUND}）")
    args = p.parse_args()
    PACKETS_PER_ROUND = args.packets

    if subprocess.run(["id", "-u"], capture_output=True, text=True).stdout.strip() != "0":
        print("[ERROR] Must run as root.")
        sys.exit(1)

    add_ips()
    time.sleep(0.5)

    try:
        print(f"\n[+] Sending mixed normal traffic — {PACKETS_PER_ROUND} rounds × {len(NORMAL_IPS)} IPs × {len(NODE_IPS)} nodes\n")
        print(f"    Protocols: TCP(HTTP/HTTPS/SSH/kube-api), UDP(DNS/NTP/syslog), ICMP\n")
        run_normal()
    finally:
        remove_ips()
        print("\n[+] Cleanup complete.")


if __name__ == "__main__":
    main()
