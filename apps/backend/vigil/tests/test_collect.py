from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from vigil import services


FLOW = {
    "src_ip": "172.30.1.11",
    "dst_ip": "192.168.100.205",
    "src_port": 45678,
    "dst_port": 80,
    "protocol": "TCP",
}


class CollectOnlyTests(SimpleTestCase):
    """No database: bulk_create and the detection path are mocked."""

    @override_settings(VIGIL_COLLECT_ONLY=True)
    def test_collect_only_writes_collect_records_and_skips_detection(self):
        with patch("vigil.services.CollectRecord.objects.bulk_create") as bulk, \
             patch("vigil.services.run_all") as run_all, \
             patch("vigil.services.DetectionRecord.objects.create") as det_create:
            result = services.detect_batch([dict(FLOW)])

        self.assertEqual(result, [])
        run_all.assert_not_called()
        det_create.assert_not_called()
        bulk.assert_called_once()
        (rows,) = bulk.call_args.args
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].src_ip, FLOW["src_ip"])
        self.assertIsNone(rows[0].label)
        self.assertIn("flow_duration", rows[0].flow_input)

    @override_settings(VIGIL_COLLECT_ONLY=True)
    def test_collect_only_skips_flow_without_ip(self):
        with patch("vigil.services.CollectRecord.objects.bulk_create") as bulk:
            services.detect_batch([{**FLOW, "src_ip": ""}])
        (rows,) = bulk.call_args.args
        self.assertEqual(rows, [])
