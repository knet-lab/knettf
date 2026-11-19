"""ingest.flows：双向流、去重、FIN/RST 结束、超时。不依赖数据库和模型文件。"""

from typing import Any

from django.test import SimpleTestCase

from vigil.detection import DetectionInput
from vigil.ingest.flows import FlowTable


def _pkt(ts, src="192.168.100.20", dst="10.0.1.5", sport=40000, dport=80, flags=None,
         reply=False, obs="FROM_NETWORK", verdict="FORWARDED"):
    return {"ts": ts, "direction": "", "obs_point": obs, "verdict": verdict,
            "flags": flags or {}, "is_reply": reply, "label": "",
            "src_ip": src, "dst_ip": dst, "src_port": sport, "dst_port": dport, "protocol": "TCP"}


def _back(ts, **kw):
    return _pkt(ts, src="10.0.1.5", dst="192.168.100.20", sport=80, dport=40000, reply=True,
                obs="FROM_ENDPOINT", **kw)


class FlowTableTests(SimpleTestCase):
    def test_handshake_and_close_is_one_bidirectional_flow(self):
        t = FlowTable()
        out = []
        out += t.add(_pkt(0.0, flags={"SYN": True}))
        out += t.add(_back(0.1, flags={"SYN": True, "ACK": True}))
        out += t.add(_pkt(0.2, flags={"ACK": True}))
        out += t.add(_pkt(5.0, flags={"FIN": True, "ACK": True}))
        self.assertEqual(out, [])                      # 只有一方 FIN，流未结束
        out += t.add(_back(5.1, flags={"FIN": True, "ACK": True}))
        self.assertEqual(out, [])                      # 双方 FIN，等挥手最后的 ACK
        out += t.add(_pkt(5.2, flags={"ACK": True}))
        self.assertEqual(len(out), 1)
        f = out[0]
        self.assertEqual((f["src_ip"], f["dst_ip"], f["dst_port"]), ("192.168.100.20", "10.0.1.5", 80))
        self.assertEqual((f["total_packets"], f["fwd_packets"], f["bwd_packets"]), (6, 4, 2))
        self.assertEqual(f["is_bidirectional"], 1)
        self.assertEqual(f["flow_duration"], 5_200_000.0)
        self.assertEqual(set(f) - {"aggregation_ms"}, set(DetectionInput.__dataclass_fields__))
        self.assertEqual(len(t), 0)

    def test_close_without_last_ack_ends_after_grace(self):
        t = FlowTable()
        t.add(_pkt(0.0, flags={"SYN": True}))
        t.add(_pkt(1.0, flags={"FIN": True, "ACK": True}))
        t.add(_back(1.1, flags={"FIN": True, "ACK": True}))
        self.assertEqual(t.expire(2.0), [])
        out = t.expire(3.2)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["total_packets"], 3)

    def test_new_syn_after_close_starts_new_flow(self):
        t = FlowTable()
        t.add(_pkt(0.0, flags={"SYN": True}))
        t.add(_pkt(1.0, flags={"FIN": True, "ACK": True}))
        t.add(_back(1.1, flags={"FIN": True, "ACK": True}))
        out = t.add(_pkt(1.5, flags={"SYN": True}))
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["total_packets"], 3)
        self.assertEqual(len(t), 1)

    def test_rst_ends_flow(self):
        t = FlowTable()
        t.add(_pkt(0.0, flags={"SYN": True}))
        out = t.add(_back(0.1, flags={"RST": True}))
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["rst_count"], 1)

    def test_duplicate_observation_points_counted_once(self):
        t = FlowTable()
        t.add(_pkt(0.0, obs="FROM_ENDPOINT"))
        t.add(_pkt(0.0, obs="TO_OVERLAY"))
        t.add(_pkt(0.0, obs="FROM_OVERLAY"))
        t.add(_pkt(0.0, obs="TO_ENDPOINT"))
        (f,) = t.flush_all()
        self.assertEqual(f["total_packets"], 1)

    def test_cross_node_pod_packet_counted_once(self):
        # 跨节点 Pod→Pod：源节点 FROM_ENDPOINT，目的节点 FROM_NETWORK 再报一次，只能算一个包
        t = FlowTable()
        kw: dict[str, Any] = dict(src="10.0.2.14", dst="10.0.1.237", sport=34504, dport=6379)
        for obs in ("FROM_ENDPOINT", "TO_OVERLAY", "TO_NETWORK", "FROM_NETWORK", "FROM_OVERLAY", "TO_ENDPOINT"):
            t.add(_pkt(0.0, obs=obs, **kw))
        [f] = t.flush_all()
        self.assertEqual(f["total_packets"], 1)

    def test_external_packet_from_network_still_counted(self):
        t = FlowTable()
        t.add(_pkt(0.0, obs="FROM_NETWORK"))          # 外部客户端 → Pod
        [f] = t.flush_all()
        self.assertEqual(f["total_packets"], 1)

    def test_reply_seen_first_keeps_initiator(self):
        t = FlowTable()
        t.add(_back(0.0, flags={"ACK": True}))          # 中途接入，先看到回包
        t.add(_pkt(0.5, flags={"ACK": True}))
        (f,) = t.flush_all()
        self.assertEqual((f["src_ip"], f["dst_port"]), ("192.168.100.20", 80))
        self.assertEqual((f["fwd_packets"], f["bwd_packets"]), (1, 1))

    def test_idle_timeout(self):
        t = FlowTable(idle_timeout=60, active_timeout=120)
        t.add(_pkt(0.0))
        t.add(_pkt(10.0))
        self.assertEqual(t.expire(now=69.0), [])
        (f,) = t.expire(now=70.0)
        self.assertEqual(f["total_packets"], 2)

    def test_active_timeout_splits_long_flow(self):
        t = FlowTable(idle_timeout=60, active_timeout=120)
        out = []
        for s in range(0, 200, 10):
            out += t.add(_pkt(float(s)))
        self.assertEqual(len(out), 1)                  # 0..110 一段，120 起新一段
        self.assertEqual(out[0]["total_packets"], 12)
        (rest,) = t.flush_all()
        self.assertEqual(rest["total_packets"], 8)


class InitiatorTests(SimpleTestCase):
    def test_direction_kept_across_active_timeout(self):
        """长连接被活跃超时切开后，下一段即使先看到回包（且没有 is_reply），方向也不反。"""
        t = FlowTable(idle_timeout=60, active_timeout=120)
        t.add(_pkt(0.0, flags={"SYN": True}))
        t.add(_back(0.1, flags={"SYN": True, "ACK": True}))
        (first,) = t.expire(now=120.0)
        resp = _back(125.0, flags={"ACK": True}); resp["is_reply"] = False
        t.add(resp)
        t.add(_pkt(126.0, flags={"ACK": True}))
        (second,) = t.flush_all()
        self.assertEqual((first["src_ip"], first["dst_port"]), ("192.168.100.20", 80))
        self.assertEqual((second["src_ip"], second["dst_port"]), ("192.168.100.20", 80))
        self.assertEqual((second["fwd_packets"], second["bwd_packets"]), (1, 1))

    def test_synack_seen_first(self):
        t = FlowTable()
        sa = _back(0.0, flags={"SYN": True, "ACK": True}); sa["is_reply"] = False
        t.add(sa)
        (f,) = t.flush_all()
        self.assertEqual((f["src_ip"], f["dst_port"]), ("192.168.100.20", 80))

    def test_port_heuristic(self):
        t = FlowTable()
        p = _back(0.0, flags={"ACK": True}); p["is_reply"] = False     # 中途接入、无任何提示
        t.add(p)
        (f,) = t.flush_all()
        self.assertEqual((f["src_ip"], f["dst_port"]), ("192.168.100.20", 80))

    def test_learned_server_beats_port_heuristic(self):
        """gRPC 服务端口 50051 大于客户端临时端口时，靠握手学到的服务端判断方向。"""
        t = FlowTable()
        cli: dict[str, Any] = dict(src="10.0.2.14", dst="10.0.1.237", sport=34504, dport=50051, obs="FROM_ENDPOINT")
        t.add(_pkt(0.0, flags={"SYN": True}, **cli))
        t.flush_all()
        # 另一个客户端的长连接，中途接入，先看到服务端发来的包
        p = _pkt(5.0, src="10.0.1.237", dst="10.0.3.230", sport=50051, dport=34322,
                 flags={"ACK": True}, obs="FROM_ENDPOINT")
        t.add(p)
        (f,) = t.flush_all()
        self.assertEqual((f["src_ip"], f["dst_port"]), ("10.0.3.230", 50051))
