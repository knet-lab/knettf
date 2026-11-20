"""
后台检测线程（随 Django 进程启动，见 vigil/apps.py）：

  bridge 线程：Kafka(ebpf-net-logs) → 流表（双向流 + FIN/RST + 超时，见 flows.py）→ flow_queue
  drainer 线程：flow_queue → services.detect_batch（检测 + 存库）

Kafka 地址、topic、消费组都在 settings（.env）里：VIGIL_KAFKA_BOOTSTRAP / VIGIL_KAFKA_TOPIC / VIGIL_KAFKA_GROUP_ID。
开发环境必须把 VIGIL_KAFKA_GROUP_ID 设成 vigil-bridge-dev，避免和线上抢分区。
"""

import json
import logging
import queue
import threading
import time

from confluent_kafka import Consumer, KafkaError, KafkaException
from django.conf import settings

from .features import hubble_to_packet, should_skip
from .flows import FlowTable

logger = logging.getLogger("vigil.bridge")

CONSUME_BATCH  = 10000  # 每次从 Kafka 取的消息数
SWEEP_INTERVAL = 1.0    # 秒：多久检查一次超时流并把已结束的流送去检测


# ── In-process queue (bridge thread → async consumer) ─────────────────────────
flow_queue: queue.Queue = queue.Queue(maxsize=2000)


# ── Main loop ──────────────────────────────────────────────────────────────────
def run_bridge():
    consumer = Consumer({
        "bootstrap.servers":         settings.VIGIL_KAFKA_BOOTSTRAP,
        "group.id":                  settings.VIGIL_KAFKA_GROUP_ID,
        "auto.offset.reset":         "latest",
        "enable.auto.commit":        False,
        "fetch.min.bytes":           1024 * 64,
        "fetch.wait.max.ms":         500,
        "max.partition.fetch.bytes": 1024 * 1024 * 4,
        "session.timeout.ms":        6000,
        "heartbeat.interval.ms":     2000,
        "broker.address.family":     "v4",
    })
    consumer.subscribe([settings.VIGIL_KAFKA_TOPIC])
    logger.info("bridge starting → bootstrap=%s topic=%s group=%s",
                settings.VIGIL_KAFKA_BOOTSTRAP, settings.VIGIL_KAFKA_TOPIC, settings.VIGIL_KAFKA_GROUP_ID)

    table   = FlowTable()
    pending: list[dict] = []
    last_sweep = time.time()
    uncommitted = False

    def _send():
        if not pending:
            return
        batch = pending[:]
        pending.clear()
        try:
            flow_queue.put_nowait(batch)
        except queue.Full:
            logger.warning("flow_queue full, dropping batch of %d flows", len(batch))

    try:
        while True:
            msgs = consumer.consume(num_messages=CONSUME_BATCH, timeout=0.1)
            uncommitted = uncommitted or bool(msgs)

            for msg in msgs:
                err = msg.error()
                if err:
                    if err.code() != KafkaError._PARTITION_EOF:
                        raise KafkaException(err)
                    continue
                try:
                    event = json.loads((msg.value() or b"").decode("utf-8"))
                    flow  = event.get("flow", {})
                    if flow and not should_skip(flow):
                        pending.extend(table.add(hubble_to_packet(flow)))
                except (json.JSONDecodeError, Exception) as e:
                    logger.debug("skip malformed message: %s", e)

            now = time.time()
            if now - last_sweep >= SWEEP_INTERVAL:
                last_sweep = now
                pending.extend(table.expire(now))
                _send()
                # 提交的是"已读到"的位置；还在流表里没输出的流在进程重启时会丢失（最多一个超时周期）
                if uncommitted:
                    consumer.commit(asynchronous=True)
                    uncommitted = False

    except Exception as e:
        logger.error("bridge error: %s", e)
    finally:
        pending.extend(table.flush_all())
        _send()
        consumer.commit(asynchronous=False)
        consumer.close()
        logger.info("bridge shut down cleanly")


# ── Drainer loop (flow_queue → detect → DB) ───────────────────────────────────
def run_drainer():
    """Consume flow_queue and persist detections. Runs in its own thread,
    independent of any WebSocket client or the ASGI event loop."""
    from django.db import close_old_connections
    from vigil import services

    logger.info("drainer starting")
    while True:
        batch = flow_queue.get()
        close_old_connections()
        try:
            results = services.detect_batch(batch)
            n_attacks = sum(1 for r in results if r.get("is_attack"))
            logger.info("queue: %d flows → %d attack(s)", len(batch), n_attacks)
        except Exception:
            logger.exception("drainer failed on batch of %d flows", len(batch))
        finally:
            close_old_connections()


# ── Thread launcher ────────────────────────────────────────────────────────────
_started = False
_lock    = threading.Lock()


def start(base_url: str = "http://localhost:8080", token: str | None = None):
    """Start bridge + drainer daemon threads. Idempotent."""
    global _started
    with _lock:
        if _started:
            return
        _started = True
    threading.Thread(target=run_drainer, daemon=True, name="vigil-drainer").start()
    threading.Thread(target=run_bridge, daemon=True, name="vigil-bridge").start()
    logger.info("vigil bridge + drainer threads started")
