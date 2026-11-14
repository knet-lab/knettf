#!/usr/bin/env python3
"""正常流量 — curl/nc + asyncio，通过 --interface 绑定源 IP"""

import asyncio
import random
import subprocess
import time

IFACE   = "virbr-k8s"
SRC_IPS = [f"192.168.100.{n}" for n in range(50, 60)]

HTTP_DST    = "192.168.100.210"
HTTP_PORT   = 8080
TCP_TARGETS = [("192.168.100.211", 3306), ("192.168.100.212", 21)]
UDP_TARGETS = [("192.168.100.213", 9999), ("192.168.100.214", 53)]
PATHS       = ["/", "/index.html", "/api/status", "/api/users", "/healthz"]

DURATION = 90
N        = 50  # 并发 worker 数（curl 进程比 aiohttp 重，适当降低）


def _log(src, dst, port, atype):
    print(f"SEND|normal|{src}|{dst}|{port}|{atype}|{time.time():.3f}", flush=True)


def manage_ips(action):
    for ip in SRC_IPS:
        subprocess.run(["sudo", "ip", "addr", action, f"{ip}/24", "dev", IFACE],
                       capture_output=True)


def _fire(pending: set, coro):
    task = asyncio.create_task(coro)
    pending.add(task)
    task.add_done_callback(pending.discard)


async def _curl(src, url):
    proc = await asyncio.create_subprocess_exec(
        "curl", "-s", "--interface", src, "--max-time", "3", url,
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.wait()


async def _nc_tcp(src, dst, port):
    proc = await asyncio.create_subprocess_exec(
        "nc", "-w", "2", "-s", src, dst, str(port),
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.wait()


async def _nc_udp(src, dst, port):
    proc = await asyncio.create_subprocess_exec(
        "nc", "-u", "-w", "1", "-s", src, dst, str(port),
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.wait()


async def worker(stop: asyncio.Event, pending: set):
    while not stop.is_set():
        src  = random.choice(SRC_IPS)
        roll = random.random()
        if roll < 0.6:
            path = random.choice(PATHS)
            _log(src, HTTP_DST, HTTP_PORT, "HTTP")
            _fire(pending, _curl(src, f"http://{HTTP_DST}:{HTTP_PORT}{path}"))
        elif roll < 0.85:
            dst, port = random.choice(TCP_TARGETS)
            _log(src, dst, port, "TCP")
            _fire(pending, _nc_tcp(src, dst, port))
        else:
            dst, port = random.choice(UDP_TARGETS)
            _log(src, dst, port, "UDP")
            _fire(pending, _nc_udp(src, dst, port))
        await asyncio.sleep(0.05)


async def main():
    manage_ips("add")
    await asyncio.sleep(0.3)
    print(f"[simulate_1] 正常流量开始  N={N}  duration={DURATION}s", flush=True)

    stop    = asyncio.Event()
    pending: set = set()

    workers = [asyncio.create_task(worker(stop, pending)) for _ in range(N)]
    await asyncio.sleep(DURATION)
    stop.set()
    await asyncio.gather(*workers, return_exceptions=True)
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)

    manage_ips("del")
    print("[simulate_1] 完成", flush=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        manage_ips("del")
