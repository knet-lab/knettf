"""ingest.flows：双向流、去重、FIN/RST 结束、超时。不依赖数据库和模型文件。"""

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
        self.assertEqual(len(out), 1)
        f = out[0]
        self.assertEqual((f["src_ip"], f["dst_ip"], f["dst_port"]), ("192.168.100.20", "10.0.1.5", 80))
        self.assertEqual((f["total_packets"], f["fwd_packets"], f["bwd_packets"]), (5, 3, 2))
        self.assertEqual(f["is_bidirectional"], 1)
        self.assertEqual(f["flow_duration"], 5_100_000.0)
        self.assertEqual(set(f) - {"aggregation_ms"}, set(DetectionInput.__dataclass_fields__))
        self.assertEqual(len(t), 0)

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
