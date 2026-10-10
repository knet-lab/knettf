from unittest.mock import MagicMock, patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from kcore.models import User


# Minimal valid flow payload (all defaults accepted by FlowInputSerializer).
FLOW = {
    'src_ip': '10.0.0.1',
    'dst_ip': '10.0.0.2',
    'src_port': 12345,
    'dst_port': 80,
    'protocol': 'TCP',
}

DETECT_RESULT = [{
    'model_name': 'ads_ml',
    'is_attack': False,
    'confidence': 0.9,
    'attack_type': None,
    'explanation': '',
    'recommended_action': 'allow',
    'record_id': 1,
    'src_ip': '10.0.0.1',
    'dst_ip': '10.0.0.2',
    'src_port': 12345,
    'dst_port': 80,
    'protocol': 'TCP',
    'created_at': '2026-01-01T00:00:00+00:00',
    'aggregation_ms': None,
    'inference_ms': 1.5,
}]


class BaseVigilTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='alice', email='alice@test.com', password='pass')
        self.client.force_authenticate(user=self.user)


# ── DetectView ─────────────────────────────────────────────────────────────────

class DetectViewTests(BaseVigilTest):
    def setUp(self):
        super().setUp()
        self.url = reverse('vigil-detect')

    @patch('vigil.views.services.detect_flow', return_value=DETECT_RESULT)
    def test_detect_valid_flow(self, _):
        resp = self.client.post(self.url, FLOW, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('results', resp.data['data'])
        self.assertEqual(resp.data['data']['count'], 1)

    @patch('vigil.views.services.detect_flow', return_value=DETECT_RESULT)
    def test_detect_with_model_field(self, mock_detect):
        resp = self.client.post(self.url, {**FLOW, 'model': 'ads_ml'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_detect_missing_required_fields_returns_400(self):
        resp = self.client.post(self.url, {'src_ip': '10.0.0.1'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('vigil.views.services.detect_flow', side_effect=KeyError('unknown_model'))
    def test_detect_unknown_model_returns_400(self, _):
        resp = self.client.post(self.url, {**FLOW, 'model': 'bad'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_detect_unauthenticated(self):
        self.client.force_authenticate(user=None)
        resp = self.client.post(self.url, FLOW, format='json')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


# ── DetectBatchView ────────────────────────────────────────────────────────────

class DetectBatchViewTests(BaseVigilTest):
    def setUp(self):
        super().setUp()
        self.url = reverse('vigil-detect-batch')

    @patch('vigil.views.services.detect_batch', return_value=DETECT_RESULT * 2)
    def test_batch_detect(self, _):
        resp = self.client.post(self.url, {'flows': [FLOW, FLOW]}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['data']['count'], 2)

    @patch('vigil.views.services.detect_batch', return_value=DETECT_RESULT)
    def test_batch_with_model(self, mock_batch):
        resp = self.client.post(self.url, {
            'flows': [FLOW], 'model': 'ads_ml'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        _, kwargs = mock_batch.call_args
        self.assertEqual(kwargs.get('model_name') or mock_batch.call_args[0][1], 'ads_ml')

    def test_batch_missing_flows_returns_400(self):
        resp = self.client.post(self.url, {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_batch_unauthenticated(self):
        self.client.force_authenticate(user=None)
        resp = self.client.post(self.url, {'flows': [FLOW]}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


# ── RecordsView ────────────────────────────────────────────────────────────────

class RecordsViewTests(BaseVigilTest):
    def setUp(self):
        super().setUp()
        self.url = reverse('vigil-records')

    def _mock_qs(self, records=None):
        records = records or []
        qs = MagicMock()
        qs.count.return_value = len(records)
        qs.filter.return_value = qs
        qs.__getitem__ = lambda self, s: records
        return qs

    @patch('vigil.views.DetectionRecord.objects')
    def test_list_records_default(self, mock_objs):
        mock_objs.all.return_value = self._mock_qs()
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.data['data']
        self.assertIn('records', data)
        self.assertIn('total', data)
        self.assertIn('offset', data)
        self.assertIn('limit', data)

    @patch('vigil.views.DetectionRecord.objects')
    def test_list_records_only_attacks(self, mock_objs):
        qs = self._mock_qs()
        mock_objs.all.return_value = qs
        resp = self.client.get(self.url, {'only_attacks': 'true'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        qs.filter.assert_called_with(is_attack=True)

    @patch('vigil.views.DetectionRecord.objects')
    def test_list_records_only_normal(self, mock_objs):
        qs = self._mock_qs()
        mock_objs.all.return_value = qs
        resp = self.client.get(self.url, {'only_normal': 'true'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        qs.filter.assert_called_with(is_attack=False)

    @patch('vigil.views.DetectionRecord.objects')
    def test_list_records_with_filters(self, mock_objs):
        qs = self._mock_qs()
        mock_objs.all.return_value = qs
        resp = self.client.get(self.url, {
            'model_name': 'ads_ml',
            'attack_type': 'PortScan',
            'limit': '10',
            'offset': '5',
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['data']['limit'], 10)
        self.assertEqual(resp.data['data']['offset'], 5)

    @patch('vigil.views.DetectionRecord.objects')
    def test_list_records_limit_capped_at_500(self, mock_objs):
        mock_objs.all.return_value = self._mock_qs()
        resp = self.client.get(self.url, {'limit': '9999'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['data']['limit'], 500)

    def test_list_unauthenticated(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


# ── RecordDetailView ───────────────────────────────────────────────────────────

class RecordDetailViewTests(BaseVigilTest):
    def _url(self, pk):
        return reverse('vigil-record-detail', kwargs={'pk': pk})

    @patch('vigil.views.DetectionRecord.objects')
    def test_get_record(self, mock_objs):
        from vigil.models import DetectionRecord
        # 用真实（未保存）实例：裸 MagicMock 会被 JSON 编码器无限展开，耗尽内存
        fake = DetectionRecord(
            pk=1, src_ip='10.0.0.1', dst_ip='10.0.0.2', src_port=12345, dst_port=80,
            protocol='TCP', flow_input=FLOW, model_name='ads_ml', is_attack=False,
            confidence=0.9)
        mock_objs.get.return_value = fake
        resp = self.client.get(self._url(1))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['data']['id'], 1)

    @patch('vigil.views.DetectionRecord.objects')
    def test_get_record_not_found(self, mock_objs):
        from vigil.models import DetectionRecord
        mock_objs.get.side_effect = DetectionRecord.DoesNotExist
        resp = self.client.get(self._url(9999))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_record_unauthenticated(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get(self._url(1))
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


# ── StatsView ──────────────────────────────────────────────────────────────────

STATS = {
    'total': 100, 'attacks': 30, 'normal': 70,
    'attack_rate': 0.3,
    'by_attack_type': [{'attack_type': 'PortScan', 'count': 10}],
    'by_model': [{'model_name': 'ads_ml', 'count': 100}],
    'recent': [],
}


class StatsViewTests(BaseVigilTest):
    def setUp(self):
        super().setUp()
        self.url = reverse('vigil-stats')

    @patch('vigil.views.services.get_stats', return_value=STATS)
    def test_get_stats(self, _):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.data['data']
        self.assertEqual(data['total'], 100)
        self.assertEqual(data['attacks'], 30)
        self.assertIn('by_attack_type', data)

    def test_get_stats_unauthenticated(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


# ── ModelsView ─────────────────────────────────────────────────────────────────

class ModelsViewTests(BaseVigilTest):
    def setUp(self):
        super().setUp()
        self.url = reverse('vigil-models')

    @patch('vigil.views.services.list_models', return_value=['ads_ml'])
    def test_list_models(self, _):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('ads_ml', resp.data['data']['models'])

    @patch('vigil.views.services.list_models', return_value=[])
    def test_list_models_empty(self, _):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['data']['models'], [])

    def test_list_models_unauthenticated(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
