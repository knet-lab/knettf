"""
flow-shipper：每个节点一个，替代原来的 Vector + `hubble observe`。

  本节点 Hubble（unix socket，gRPC/protobuf）→ 过滤 + 去重 → Kafka(ebpf-net-logs)

· 直接收 protobuf，不再经过 `hubble observe` 转 JSON → 管道 → Vector 解析 → 再编码 JSON。
· 过滤：采集链路自身的流量（kube-system、Kafka、本程序、hubble-relay），以及后端
  should_skip 会丢弃的事件。
· 去重（SHIPPER_DEDUP=1，默认开）：同一个包在多个观测点的重复事件只发一次，规则与后端
  vigil/ingest/flows.counts_once 完全相同（同一份代码，部署时随 ConfigMap 下发）。
  约七成事件在节点上就被丢掉。lab/dataset 等按原始逐包事件统计的旧脚本需要关掉去重。
· 写入 Kafka 的消息格式与 `hubble observe --output=json` 相同，后端无需改动。

环境变量：KAFKA_BOOTSTRAP（必填）、KAFKA_TOPIC、HUBBLE_SOCKET、SHIPPER_DEDUP、SHIPPER_STATS_SECS
"""

import json
import logging
import os
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "hubble_api"))          # 生成的 Hubble gRPC 代码（flow/ observer/ relay/）
sys.path.insert(0, os.environ.get("INGEST_PARENT", str(HERE)))  # 含 ingest/ 包的目录

import grpc                                           # noqa: E402
from confluent_kafka import Producer                  # noqa: E402
from google.protobuf.json_format import MessageToDict  # noqa: E402
from observer import observer_pb2, observer_pb2_grpc  # noqa: E402

from ingest.features import hubble_to_packet, should_skip  # noqa: E402
from ingest.flows import counts_once                        # noqa: E402

log = logging.getLogger("flow-shipper")

_INFRA_LABELS = re.compile(
    r"k8s:app=(kafka-broker|kafka-controller|flow-shipper)(,|$)|k8s:app\.kubernetes\.io/name=hubble-relay")


def is_pipeline_traffic(flow: dict) -> bool:
    """采集链路自身的流量（Hubble → 本程序 → Kafka → 又被 Hubble 记录），不转发，避免自激回路。"""
    src, dst = flow.get("source") or {}, flow.get("destination") or {}
    if "kube-system" in (src.get("namespace"), dst.get("namespace")):
        return True
    labels = ",".join(src.get("labels") or []) + "," + ",".join(dst.get("labels") or [])
    return bool(_INFRA_LABELS.search(labels))


def keep(flow: dict, dedup: bool) -> bool:
    if not flow or is_pipeline_traffic(flow) or should_skip(flow):
        return False
    return counts_once(hubble_to_packet(flow)) if dedup else True


def to_dict(resp) -> dict:
    """与 `hubble observe --output=json` 相同的字段名（proto 原名）和取值格式。"""
    return MessageToDict(resp, preserving_proto_field_name=True)


class Stats:
    def __init__(self, every: float):
        self.every, self.t0 = every, time.monotonic()
        self.seen = self.sent = self.lost = 0

    def maybe_log(self):
        dt = time.monotonic() - self.t0
        if dt >= self.every:
            log.info("%.0fs: 收到 %d 事件，转发 %d（%.0f%%），Hubble 丢失 %d",
                     dt, self.seen, self.sent, 100 * self.sent / max(self.seen, 1), self.lost)
            self.__init__(self.every)


def produce(producer: Producer, topic: str, value: bytes):
    """缓冲满时阻塞等待（反压到 Hubble，丢失体现在 Hubble 的 lost events 里，不在这里静默丢）。"""
    while True:
        try:
            producer.produce(topic, value)
            producer.poll(0)
            return
        except BufferError:
            producer.poll(0.5)


def run():
    socket = os.environ.get("HUBBLE_SOCKET", "unix:///var/run/cilium/hubble.sock")
    topic = os.environ.get("KAFKA_TOPIC", "ebpf-net-logs")
    dedup = os.environ.get("SHIPPER_DEDUP", "1") != "0"
    stats = Stats(float(os.environ.get("SHIPPER_STATS_SECS", "60")))
    producer = Producer({
        "bootstrap.servers": os.environ["KAFKA_BOOTSTRAP"],
        "linger.ms": 200,
        "batch.num.messages": 2000,
        "compression.type": "lz4",
        "queue.buffering.max.messages": 200_000,
    })
    log.info("启动：hubble=%s topic=%s dedup=%s", socket, topic, dedup)

    while True:
        try:
            with grpc.insecure_channel(socket) as ch:
                stub = observer_pb2_grpc.ObserverStub(ch)
                for resp in stub.GetFlows(observer_pb2.GetFlowsRequest(follow=True)):
                    kind = resp.WhichOneof("response_types")
                    if kind == "lost_events":
                        stats.lost += resp.lost_events.num_events_lost
                    elif kind == "flow":
                        stats.seen += 1
                        event = to_dict(resp)
                        if keep(event.get("flow", {}), dedup):
                            produce(producer, topic, json.dumps(event, separators=(",", ":")).encode())
                            stats.sent += 1
                    stats.maybe_log()
        except grpc.RpcError as e:
            log.warning("Hubble 连接断开（%s），5 秒后重连", e.code() if hasattr(e, "code") else e)
        producer.flush(5)
        time.sleep(5)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run()
