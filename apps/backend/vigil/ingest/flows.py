"""
流表：Hubble 逐包事件 → 完整的双向流（业界通用切分方式，参照 CICFlowMeter / Zeek / IPFIX）。

一条流 = 同一对端点（双向五元组）之间的一次通信：
  · 双向：A→B 与 B→A 的包归入同一条流；先发包的一方是发起方（正向 fwd）
  · 结束：TCP 出现 RST，或双方都发过 FIN → 立即输出
  · 空闲超时 IDLE_TIMEOUT：这么久没有新包 → 输出
  · 活跃超时 ACTIVE_TIMEOUT：流持续超过这么久 → 先输出一段，后续包开始新的一条
  · 单条流包数上限 MAX_PACKETS：防止异常长流占满内存，达到即输出

去重：同一个包会在多个观测点各上报一次（例如源节点 FROM_ENDPOINT + TO_OVERLAY，
目的节点 FROM_OVERLAY + TO_ENDPOINT）。只统计包"第一次被看到"的观测点，
其余丢弃，避免包数被放大 2~4 倍。

时间一律用事件自带的时间戳（Hubble 记录的内核时间），超时判断用调用方给的 now。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from .features import compute_flow

IDLE_TIMEOUT   = 60.0     # 秒
ACTIVE_TIMEOUT = 120.0    # 秒（CICFlowMeter 默认 flow timeout）
MAX_PACKETS    = 10_000
MAX_FLOWS      = 200_000  # 同时打开的流上限，超出时最早不活跃的先输出

# 包第一次被 Cilium 看到的观测点。FROM_OVERLAY / TO_* 是同一个包的后续位置，不重复计数。
_FIRST_SIGHTING = {"FROM_ENDPOINT", "FROM_NETWORK", "FROM_HOST", "FROM_STACK",
                   "FROM_PROXY", "FROM_CRYPTO"}


def counts_once(packet: dict) -> bool:
    """这个包事件是否参与计数。没有观测点信息时（旧版本 Hubble）照常计数。"""
    op = packet.get("obs_point") or ""
    return op == "" or op in _FIRST_SIGHTING


def biflow_key(p: dict) -> tuple:
    """双向五元组：两个端点排序后作为键，A→B 与 B→A 得到同一个键。"""
    a = (p["src_ip"], p["src_port"])
    b = (p["dst_ip"], p["dst_port"])
    lo, hi = (a, b) if a <= b else (b, a)
    return (lo, hi, p["protocol"])


@dataclass
class _Flow:
    initiator: tuple            # (ip, port) 发起方
    first_ts: float
    last_ts: float
    packets: list = field(default_factory=list)
    fin_fwd: bool = False
    fin_bwd: bool = False


class FlowTable:
    def __init__(self, idle_timeout=IDLE_TIMEOUT, active_timeout=ACTIVE_TIMEOUT,
                 max_packets=MAX_PACKETS, max_flows=MAX_FLOWS):
        self.idle_timeout = idle_timeout
        self.active_timeout = active_timeout
        self.max_packets = max_packets
        self.max_flows = max_flows
        self._flows: dict[tuple, _Flow] = {}

    def __len__(self):
        return len(self._flows)

    def add(self, p: dict) -> list[dict]:
        """加入一个包；返回因此结束的流（0 或 1 条，已算好特征）。"""
        if not counts_once(p):
            return []
        key = biflow_key(p)
        out: list[dict] = []
        f = self._flows.get(key)

        # 活跃超时：老流先输出，这个包开始新的一条
        if f is not None and p["ts"] - f.first_ts >= self.active_timeout:
            out.append(self._emit(key))
            f = None

        if f is None:
            if len(self._flows) >= self.max_flows:
                oldest = min(self._flows, key=lambda k: self._flows[k].last_ts)
                out.append(self._emit(oldest))
            # 发起方：第一个看到的包的发送方；如果它是回包（is_reply），发起方是对端
            init = (p["dst_ip"], p["dst_port"]) if p.get("is_reply") else (p["src_ip"], p["src_port"])
            f = self._flows[key] = _Flow(initiator=init, first_ts=p["ts"], last_ts=p["ts"])

        fwd = (p["src_ip"], p["src_port"]) == f.initiator
        f.packets.append({**p, "fwd": fwd})
        f.last_ts = max(f.last_ts, p["ts"])

        flags = p.get("flags") or {}
        if flags.get("FIN"):
            if fwd:
                f.fin_fwd = True
            else:
                f.fin_bwd = True
        if flags.get("RST") or (f.fin_fwd and f.fin_bwd) or len(f.packets) >= self.max_packets:
            out.append(self._emit(key))
        return out

    def expire(self, now: float) -> list[dict]:
        """输出空闲超时或活跃超时的流。now 与事件时间戳同一时钟（epoch 秒）。"""
        keys = [k for k, f in self._flows.items()
                if now - f.last_ts >= self.idle_timeout or now - f.first_ts >= self.active_timeout]
        return [self._emit(k) for k in keys]

    def flush_all(self) -> list[dict]:
        """进程退出时输出所有未结束的流。"""
        return [self._emit(k) for k in list(self._flows)]

    def _emit(self, key: tuple) -> dict:
        f = self._flows.pop(key)
        flow = compute_flow(f.packets)
        # 首包到输出的延迟（含等待流结束/超时的时间），前端用来展示检测时效
        flow["aggregation_ms"] = round(max(time.time() - f.first_ts, 0.0) * 1000, 1)
        return flow
