"""
集群只读检查：用当前代码处理集群里最近的真实流量，确认采集链路和检测链路都正常。

  python manage.py cluster_check [--messages 3000] [--max-age 300]

做的事（全部只读）：
  1. kubectl（如果有）：节点 Ready、flow-shipper DaemonSet 就绪、Kafka Pod Running
  2. Kafka：topic 存在、每个分区有 leader、最近 --max-age 秒内有新消息
  3. 取每个分区最近的消息（assign 指定偏移量，不加入消费组、不提交偏移量），
     用当前分支的 ingest 代码拼流，检查 35 个特征是否齐全、取值合理
  4. 把这些流送进 settings.VIGIL_MODELS 里的模型，检查输出是否合法

不写数据库、不调用 Cilium 策略、不发包。
退出码：0 通过；1 检查失败；2 集群不可达（推送前钩子据此只提示、不拦截）。
"""
import dataclasses
import json
import math
import shutil
import subprocess
import time

from django.conf import settings
from django.core.management.base import BaseCommand

from vigil.detection.base import DetectionInput, DetectionResult, flow_from_dict
from vigil.ingest.features import hubble_to_packet, should_skip
from vigil.ingest.flows import ACTIVE_TIMEOUT, FlowTable

UNREACHABLE = 2

# 送给模型的特征（DetectionInput 中除 label 外的字段），名称和数量不能变
FEATURES = [f.name for f in dataclasses.fields(DetectionInput) if f.name != "label"]
EXPECTED_FEATURES = 35
RATIOS = ["fwd_ratio", "syn_ratio", "ack_ratio", "fin_ratio", "rst_ratio", "reply_ratio", "drop_ratio"]
FLAGS = ["is_bidirectional", "is_tcp", "is_udp", "is_icmp", "is_well_known_port"]


def validate_flow(d: dict) -> list[str]:
    """检查一条拼好的流（flows.py 输出的 dict），返回问题列表；空列表表示正常。"""
    problems = []
    missing = [k for k in FEATURES if k not in d]
    if missing:
        problems.append(f"缺少特征 {missing}")
        return problems
    for k in FEATURES:
        v = d[k]
        if k in ("src_ip", "dst_ip", "protocol"):
            if not isinstance(v, str):
                problems.append(f"{k} 不是字符串: {v!r}")
            continue
        if not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v):
            problems.append(f"{k} 不是有限数值: {v!r}")
        elif v < 0:
            problems.append(f"{k} 为负: {v}")
    if problems:
        return problems
    for k in RATIOS:
        if d[k] > 1:
            problems.append(f"{k} 超过 1: {d[k]}")
    for k in FLAGS:
        if d[k] not in (0, 1):
            problems.append(f"{k} 不是 0/1: {d[k]}")
    if d["fwd_packets"] + d["bwd_packets"] != d["total_packets"]:
        problems.append("fwd_packets + bwd_packets != total_packets")
    # 单位是微秒：一条流不会超过活跃超时（留 10% 余量）
    limit_us = ACTIVE_TIMEOUT * 1e6 * 1.1
    if d["flow_duration"] > limit_us:
        problems.append(f"flow_duration {d['flow_duration']} 超过活跃超时，单位可能不是微秒")
    if d["iat_max"] > d["flow_duration"] + 1:
        problems.append(f"iat_max {d['iat_max']} 大于 flow_duration {d['flow_duration']}")
    if not (d["iat_min"] <= d["iat_mean"] <= d["iat_max"] + 1e-6):
        problems.append("iat_min <= iat_mean <= iat_max 不成立")
    return problems


def validate_result(r) -> list[str]:
    if not isinstance(r, DetectionResult):
        return [f"模型返回的不是 DetectionResult: {type(r).__name__}"]
    problems = []
    if not isinstance(r.is_attack, bool):
        problems.append(f"{r.model_name}: is_attack 不是 bool")
    if not (isinstance(r.confidence, (int, float)) and 0.0 <= r.confidence <= 1.0):
        problems.append(f"{r.model_name}: confidence 不在 0~1: {r.confidence!r}")
    return problems


class Command(BaseCommand):
    help = "集群只读检查：用当前代码处理集群最近的真实流量（不写库、不提交 Kafka 偏移量）"

    def add_arguments(self, parser):
        parser.add_argument("--messages", type=int, default=3000, help="最多读取的消息总数")
        parser.add_argument("--max-age", type=int, default=300, help="最新消息允许的最大时延（秒）")
        parser.add_argument("--timeout", type=float, default=10.0, help="连接 Kafka 的超时（秒）")

    def handle(self, *args, **opts):
        self.failed = []
        self._kubectl()
        msgs = self._kafka(opts)
        if msgs is not None:
            self._pipeline(msgs)
        if self.failed:
            self.stdout.write(self.style.ERROR(f"✗ 集群检查失败: {len(self.failed)} 项"))
            raise SystemExit(1)
        self.stdout.write(self.style.SUCCESS("✓ 集群检查通过"))

    # ── 输出 ────────────────────────────────────────────────────────────────
    def ok(self, msg):
        self.stdout.write(f"  ✓ {msg}")

    def fail(self, msg):
        self.stdout.write(f"  ✗ {msg}")
        self.failed.append(msg)

    def unreachable(self, msg):
        self.stdout.write(self.style.WARNING(f"  ! 集群不可达，跳过：{msg}"))
        raise SystemExit(UNREACHABLE)

    # ── 1. kubectl ──────────────────────────────────────────────────────────
    def _kubectl(self):
        self.stdout.write("==> Kubernetes")
        if not shutil.which("kubectl"):
            self.stdout.write("  - 没有 kubectl，跳过")
            return

        def get(*a):
            out = subprocess.run(["kubectl", *a, "-o", "json", "--request-timeout=10s"],
                                 capture_output=True, text=True)
            if out.returncode != 0:
                return None
            return json.loads(out.stdout)

        nodes = get("get", "nodes")
        if nodes is None:
            self.unreachable("kubectl 连不上 API server")
        not_ready = [n["metadata"]["name"] for n in nodes["items"]
                     if not any(c["type"] == "Ready" and c["status"] == "True"
                                for c in n["status"].get("conditions", []))]
        if not_ready:
            self.fail(f"节点未就绪: {not_ready}")
        else:
            self.ok(f"{len(nodes['items'])} 个节点 Ready")

        ds = get("get", "daemonset", "-A", "--field-selector", "metadata.name=flow-shipper")
        if not ds or not ds["items"]:
            self.fail("找不到 flow-shipper DaemonSet")
        else:
            s = ds["items"][0]["status"]
            want, ready = s.get("desiredNumberScheduled", 0), s.get("numberReady", 0)
            (self.ok if want and want == ready else self.fail)(f"flow-shipper {ready}/{want} 就绪")

        pods = get("get", "pods", "-A")
        kafka = [p for p in (pods or {}).get("items", []) if p["metadata"]["name"].startswith("kafka-")]
        bad = [p["metadata"]["name"] for p in kafka if p["status"].get("phase") != "Running"]
        if not kafka:
            self.fail("找不到 Kafka Pod")
        elif bad:
            self.fail(f"Kafka Pod 未运行: {bad}")
        else:
            self.ok(f"{len(kafka)} 个 Kafka Pod Running")

    # ── 2. Kafka ────────────────────────────────────────────────────────────
    def _kafka(self, opts):
        from confluent_kafka import Consumer, KafkaError, TopicPartition

        self.stdout.write("==> Kafka")
        topic = settings.VIGIL_KAFKA_TOPIC
        consumer = Consumer({
            "bootstrap.servers":    settings.VIGIL_KAFKA_BOOTSTRAP,
            # 只用 assign() 读指定偏移量，不 subscribe、不提交，不影响线上消费组
            "group.id":             "vigil-cluster-check",
            "enable.auto.commit":   False,
            "enable.partition.eof": True,
            "broker.address.family": "v4",
        })
        try:
            try:
                md = consumer.list_topics(topic, timeout=opts["timeout"])
            except Exception as e:
                self.unreachable(f"连不上 Kafka: {e}")
            tmd = md.topics.get(topic)
            if tmd is None or tmd.error is not None or not tmd.partitions:
                self.fail(f"topic {topic} 不存在或不可用")
                return None
            no_leader = [p for p, pm in tmd.partitions.items() if pm.leader < 0]
            if no_leader:
                self.fail(f"分区没有 leader: {no_leader}")
            else:
                self.ok(f"topic {topic}：{len(tmd.partitions)} 个分区都有 leader")

            parts = sorted(tmd.partitions)
            per_part = max(opts["messages"] // len(parts), 1)
            assign, end = [], {}
            for p in parts:
                low, high = consumer.get_watermark_offsets(TopicPartition(topic, p), timeout=opts["timeout"])
                if high > low:
                    assign.append(TopicPartition(topic, p, max(low, high - per_part)))
                    end[p] = high  # 只读到开始时的末尾，之后新来的消息不读
            if not assign:
                self.fail(f"topic {topic} 没有任何消息")
                return None
            consumer.assign(assign)

            msgs, done, deadline = [], set(), time.time() + 30
            while len(done) < len(assign) and time.time() < deadline:
                for m in consumer.consume(num_messages=500, timeout=1.0):
                    p = m.partition()
                    if m.error():
                        if m.error().code() == KafkaError._PARTITION_EOF:
                            done.add(p)
                        continue
                    if m.offset() < end[p]:
                        msgs.append(m)
                    if m.offset() >= end[p] - 1:
                        done.add(p)

            newest = max((m.timestamp()[1] for m in msgs), default=0) / 1000
            age = time.time() - newest
            if age > opts["max_age"]:
                self.fail(f"最新消息是 {age:.0f} 秒前，超过 {opts['max_age']} 秒：采集链路可能中断")
            else:
                self.ok(f"读到 {len(msgs)} 条消息，最新的在 {age:.0f} 秒前")
            return msgs
        finally:
            consumer.close()

    # ── 3/4. 拼流 + 模型 ────────────────────────────────────────────────────
    def _pipeline(self, msgs):
        from vigil.detection.registry import run_all

        self.stdout.write("==> 拼流与检测（当前代码）")
        if len(FEATURES) != EXPECTED_FEATURES:
            self.fail(f"DetectionInput 特征数是 {len(FEATURES)}，应为 {EXPECTED_FEATURES}")

        table, flows, malformed = FlowTable(), [], 0
        for m in sorted(msgs, key=lambda m: m.timestamp()[1]):
            try:
                flow = json.loads(m.value().decode("utf-8")).get("flow", {})
            except (ValueError, UnicodeDecodeError):
                malformed += 1
                continue
            if flow and not should_skip(flow):
                flows.extend(table.add(hubble_to_packet(flow)))
        flows.extend(table.flush_all())

        if malformed > len(msgs) * 0.01:
            self.fail(f"{malformed}/{len(msgs)} 条消息不是合法 JSON")
        if not flows:
            self.fail("没有拼出任何流")
            return
        self.ok(f"拼出 {len(flows)} 条流")

        bad = {}
        for d in flows:
            for p in validate_flow(d):
                bad.setdefault(p.split(":")[0], p)
        if bad:
            for p in bad.values():
                self.fail(f"特征异常（示例）：{p}")
        else:
            self.ok(f"{EXPECTED_FEATURES} 个特征齐全，取值合理")

        inputs = []
        for d in flows:
            d = {k: v for k, v in d.items() if k != "aggregation_ms"}
            try:
                inputs.append(flow_from_dict(d))
            except Exception as e:
                self.fail(f"flow_from_dict 失败: {e}")
                return

        t0, n, problems, attacks = time.time(), 0, {}, 0
        for x in inputs:
            try:
                results = run_all(x)
            except Exception as e:
                self.fail(f"模型调用异常: {type(e).__name__}: {e}")
                return
            if not results:
                self.fail(f"没有模型输出结果，检查 VIGIL_MODELS: {settings.VIGIL_MODELS}")
                return
            for r in results:
                n += 1
                attacks += bool(getattr(r, "is_attack", False))
                for p in validate_result(r):
                    problems.setdefault(p, None)
        for p in problems:
            self.fail(p)
        if not problems:
            ms = (time.time() - t0) * 1000 / max(len(inputs), 1)
            self.ok(f"模型输出 {n} 条结果（判为攻击 {attacks} 条），平均 {ms:.2f} ms/流")
