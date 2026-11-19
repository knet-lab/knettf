"""ingest.features：Hubble 事件 → 流特征。不依赖数据库和模型文件。"""

from django.test import SimpleTestCase

from vigil.detection import DetectionInput, flow_from_dict
from vigil.ingest.features import compute_flow, flow_key, hubble_to_packet, should_skip


def _event(ts, src="192.168.100.20", dst="192.168.100.210", sport=50000, dport=80,
           flags=None, direction="INGRESS", verdict="FORWARDED", reply=False):
    return {
        "time": ts,
        "IP": {"source": src, "destination": dst},
        "l4": {"TCP": {"source_port": sport, "destination_port": dport, "flags": flags or {}}},
        "traffic_direction": direction,
        "verdict": verdict,
        "is_reply": reply,
    }


class HubbleToPacketTests(SimpleTestCase):
    def test_fields_and_label(self):
        p = hubble_to_packet(_event("2026-01-01T00:00:00Z", flags={"SYN": True}))
        self.assertEqual((p["src_ip"], p["dst_port"], p["protocol"]), ("192.168.100.20", 80, "TCP"))
        self.assertEqual(p["label"], "")           # 采集时不打标签（源 IP 末段不代表攻击）
        self.assertEqual(p["flags"], {"SYN": True})
        self.assertEqual(hubble_to_packet(_event("2026-01-01T00:00:00Z", src="192.168.100.55"))["label"], "")

    def test_flow_key(self):
        self.assertEqual(flow_key(_event("x")), ("192.168.100.20", "192.168.100.210", 50000, 80, "TCP"))


class ShouldSkipTests(SimpleTestCase):
    def test_skip_rules(self):
        self.assertFalse(should_skip(_event("x")))
        self.assertTrue(should_skip(_event("x", src="10.0.0.1", dst="192.168.100.10")))   # Pod↔节点：管理流量
        self.assertTrue(should_skip(_event("x", src="192.168.100.1", dst="10.0.1.5")))    # 宿主机网关→Pod
        self.assertFalse(should_skip(_event("x", src="10.0.1.5", dst="10.0.2.7")))        # Pod↔Pod：东西向保留
        self.assertFalse(should_skip(_event("x", src="172.30.1.11", dst="10.0.2.7")))     # 外部→Pod：南北向保留
        pre_dnat = _event("x", src="172.30.1.11", dst="192.168.100.205")
        pre_dnat["trace_observation_point"] = "FROM_NETWORK"
        self.assertTrue(should_skip(pre_dnat))                                             # LB VIP 的 DNAT 前记录
        self.assertTrue(should_skip(_event("x", dport=9094)))                             # Kafka 自身流量
        self.assertTrue(should_skip({"IP": {"source": "", "destination": "1.1.1.1"}}))   # 缺 IP
        self.assertTrue(should_skip(_event("x", src="127.0.0.1", dst="192.168.100.12")))  # loopback
        partial = _event("x"); del partial["l4"]["TCP"]["destination_port"]
        self.assertTrue(should_skip(partial))                                              # 缺端口的残缺事件


class ComputeFlowTests(SimpleTestCase):
    def setUp(self):
        events = [
            _event("2026-01-01T00:00:00Z", flags={"SYN": True}),
            _event("2026-01-01T00:00:01Z", flags={"SYN": True, "ACK": True}, direction="EGRESS", reply=True),
            _event("2026-01-01T00:00:03Z", flags={"ACK": True}, verdict="DROPPED"),
        ]
        self.flow = compute_flow([hubble_to_packet(e) for e in events])

    def test_counts_and_ratios(self):
        f = self.flow
        self.assertEqual((f["total_packets"], f["fwd_packets"], f["bwd_packets"]), (3, 2, 1))
        self.assertEqual(f["flow_duration"], 3_000_000.0)                     # 微秒
        self.assertEqual(f["packets_per_second"], 1.0)                        # 每秒
        self.assertEqual((f["iat_min"], f["iat_max"], f["iat_mean"]), (1e6, 2e6, 1.5e6))
        self.assertEqual((f["syn_count"], f["ack_count"]), (2, 2))
        self.assertEqual(f["syn_ratio"], 0.6667)
        self.assertEqual((f["reply_count"], f["drop_count"], f["forwarded_count"]), (1, 1, 2))
        self.assertEqual((f["is_bidirectional"], f["is_tcp"], f["is_well_known_port"]), (1, 1, 1))
        self.assertEqual(f["label"], "")

    def test_matches_detection_input(self):
        """聚合结果的字段必须正好能构造 DetectionInput（新增 / 删减特征时两边要同步）。"""
        self.assertIsInstance(flow_from_dict(self.flow), DetectionInput)
        self.assertEqual(set(self.flow), set(DetectionInput.__dataclass_fields__))


class FlowFromDictTests(SimpleTestCase):
    def test_type_coercion(self):
        d = flow_from_dict({"src_ip": "a", "dst_ip": "b", "protocol": "TCP",
                            "total_packets": "5", "iat_mean": "", "model": "ads_ml"})
        self.assertEqual((d.total_packets, d.iat_mean), (5, 0.0))
