import subprocess
import time
import argparse

# 192.168.100.50-64 绑定到 virbr-k8s，与 K8s VMs 同 L2，Hubble 能看到原始源 IP
SOURCE_IPS = [f"192.168.100.{n}" for n in range(50, 65)]
DESTINATION_IP   = "192.168.100.204"   # MetalLB nginx
DESTINATION_PORT = 80
IFACE            = "virbr-k8s"


def add_ips():
    print(f"[+] Adding {len(SOURCE_IPS)} normal-traffic IPs to {IFACE}")
    for ip in SOURCE_IPS:
        r = subprocess.run(
            ["ip", "addr", "add", f"{ip}/24", "dev", IFACE],
            capture_output=True, text=True,
        )
        if r.returncode != 0 and "File exists" not in r.stderr:
            print(f"    [warn] {ip}: {r.stderr.strip()}")
        else:
            print(f"    added {ip}")


def remove_ips():
    print(f"\n[+] Removing {len(SOURCE_IPS)} normal-traffic IPs from {IFACE}")
    for ip in SOURCE_IPS:
        r = subprocess.run(
            ["ip", "addr", "del", f"{ip}/24", "dev", IFACE],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            print(f"    [warn] {ip}: {r.stderr.strip()}")


def send_request(src_ip, dst_ip, dst_port):
    r = subprocess.run(
        ["curl", "-s", "--max-time", "5",
         "--interface", src_ip,
         f"http://{dst_ip}:{dst_port}"],
        capture_output=True, text=True,
    )
    return r.returncode == 0 and "Welcome to nginx!" in r.stdout


def main():
    p = argparse.ArgumentParser(description="Send normal HTTP traffic from virbr-k8s IPs")
    p.add_argument("--repeat", type=int, default=1,
                   help="轮次（每轮对所有 SOURCE_IPS 各发一次请求，默认 1）")
    p.add_argument("--delay", type=float, default=0.05,
                   help="每条请求间隔秒数（默认 0.05）")
    args = p.parse_args()

    add_ips()
    time.sleep(0.5)

    total = ok = 0
    try:
        for rnd in range(1, args.repeat + 1):
            for src_ip in SOURCE_IPS:
                success = send_request(src_ip, DESTINATION_IP, DESTINATION_PORT)
                total += 1
                if success:
                    ok += 1
                if args.delay:
                    time.sleep(args.delay)
            if rnd % 10 == 0:
                print(f"  round {rnd}/{args.repeat}  sent={total}  ok={ok}")
    finally:
        remove_ips()

    print(f"\nDone: {total} requests, {ok} succeeded, {total - ok} failed")


if __name__ == "__main__":
    main()
