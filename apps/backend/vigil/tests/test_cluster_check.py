from typing import Any

from django.test import SimpleTestCase

from vigil.detection.base import DetectionResult
from vigil.management.commands.cluster_check import (
    EXPECTED_FEATURES, FEATURES, validate_flow, validate_result,
)


def _flow(**over):
    d: dict[str, Any] = {k: 0 for k in FEATURES}
    d.update(src_ip="10.0.0.1", dst_ip="10.0.0.2", protocol="TCP",
             total_packets=3, fwd_packets=2, bwd_packets=1,
             flow_duration=2_000_000.0, iat_min=500_000.0, iat_mean=1_000_000.0, iat_max=1_500_000.0,
             is_tcp=1, fwd_ratio=0.667)
    d.update(over)
    return d


class ValidateFlowTests(SimpleTestCase):
    def test_feature_count(self):
        self.assertEqual(len(FEATURES), EXPECTED_FEATURES)

    def test_valid_flow(self):
        self.assertEqual(validate_flow(_flow()), [])

    def test_missing_feature(self):
        d = _flow(); del d["iat_std"]
        self.assertTrue(validate_flow(d))

    def test_duration_in_wrong_unit(self):
        # 纳秒而不是微秒：远超活跃超时
        self.assertTrue(validate_flow(_flow(flow_duration=2e12, iat_max=1e12)))

    def test_ratio_and_flag_range(self):
        self.assertTrue(validate_flow(_flow(syn_ratio=1.5)))
        self.assertTrue(validate_flow(_flow(is_tcp=2)))

    def test_packet_sum(self):
        self.assertTrue(validate_flow(_flow(total_packets=5)))

    def test_nan(self):
        self.assertTrue(validate_flow(_flow(iat_std=float("nan"))))


class ValidateResultTests(SimpleTestCase):
    def test_ok(self):
        self.assertEqual(validate_result(DetectionResult("m", False, 0.3, None)), [])

    def test_bad_confidence(self):
        self.assertTrue(validate_result(DetectionResult("m", True, 1.7, "x")))

    def test_wrong_type(self):
        self.assertTrue(validate_result({"is_attack": True}))
