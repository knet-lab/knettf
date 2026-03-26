import shutil
import tempfile
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from kcore.models import User
from .models import ScanReport, TerraformConfig, TerraformTool
from .services import TerraformConfigService


TF_CONTENT = 'resource "aws_instance" "example" {\n  ami = "ami-0c55b159cbfafe1f0"\n}'


def make_tf_file(name='main.tf'):
    return SimpleUploadedFile(name, TF_CONTENT.encode(), content_type='text/plain')


def _mock_execute(config, tools):
    """Replaces ScanService._execute without running real scan tools."""
    report, _ = ScanReport.objects.update_or_create(
        config=config,
        defaults={
            'status': ScanReport.DONE,
            'result': {'summary': {'high': 0, 'medium': 0, 'low': 0}, 'tools': {}},
            'scanned_at': timezone.now(),
        },
    )
    report.tools.set(tools)
    config.is_scanned = True
    config.save(update_fields=['is_scanned'])


class BaseAutotfTest(APITestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self._media_override = override_settings(MEDIA_ROOT=self.tmp_dir)
        self._media_override.enable()

        self.user = User.objects.create_user(
            username='alice', email='alice@test.com', password='pass')
        self.other = User.objects.create_user(
            username='bob', email='bob@test.com', password='pass')
        self.tool = TerraformTool.objects.create(
            name='tfsec', version='1.0.0', is_enabled=True)
        self.tool_disabled = TerraformTool.objects.create(
            name='checkov', version='3.0.0', is_enabled=False)
        self.client.force_authenticate(user=self.user)

    def tearDown(self):
        self._media_override.disable()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)
        super().tearDown()

    def create_config(self, name='my-config'):
        return TerraformConfigService.create_from_text(
            owner=self.user, name=name, content=TF_CONTENT)

    def create_report(self, config):
        report = ScanReport.objects.create(
            config=config,
            status=ScanReport.DONE,
            result={'summary': {'high': 1, 'medium': 0, 'low': 0}, 'tools': {}},
            scanned_at=timezone.now(),
        )
        report.tools.set([self.tool])
        return report


# ── Config List & File Create ──────────────────────────────────────────────────

class ConfigListTests(BaseAutotfTest):
    def setUp(self):
        super().setUp()
        self.url = reverse('tf-config-list', kwargs={'user_pk': self.user.pk})

    def test_list_own_configs(self):
        self.create_config('cfg-1')
        self.create_config('cfg-2')
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data['data']), 2)

    def test_list_excludes_other_user_configs(self):
        TerraformConfigService.create_from_text(self.other, 'other-cfg', TF_CONTENT)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data['data']), 0)

    def test_list_forbidden_for_other_user(self):
        self.client.force_authenticate(user=self.other)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_unauthenticated(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_from_file(self):
        resp = self.client.post(
            self.url, {'name': 'new-cfg', 'file': make_tf_file()}, format='multipart')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['data']['name'], 'new-cfg')
        self.assertFalse(resp.data['data']['is_scanned'])
        self.assertTrue(TerraformConfig.objects.filter(
            owner=self.user, name='new-cfg').exists())

    def test_create_duplicate_name_rejected(self):
        self.create_config('dup')
        resp = self.client.post(
            self.url, {'name': 'dup', 'file': make_tf_file()}, format='multipart')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_missing_file_rejected(self):
        resp = self.client.post(self.url, {'name': 'no-file'}, format='multipart')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_forbidden_for_other_user(self):
        self.client.force_authenticate(user=self.other)
        resp = self.client.post(
            self.url, {'name': 'x', 'file': make_tf_file()}, format='multipart')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


# ── Config Text Create ─────────────────────────────────────────────────────────

class ConfigTextCreateTests(BaseAutotfTest):
    def setUp(self):
        super().setUp()
        self.url = reverse('tf-config-text-create', kwargs={'user_pk': self.user.pk})

    def test_create_from_text(self):
        resp = self.client.post(self.url, {'name': 'text-cfg', 'content': TF_CONTENT})
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['data']['name'], 'text-cfg')

    def test_create_duplicate_name_rejected(self):
        self.create_config('dup')
        resp = self.client.post(self.url, {'name': 'dup', 'content': TF_CONTENT})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_missing_content_rejected(self):
        resp = self.client.post(self.url, {'name': 'no-content'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_forbidden_for_other_user(self):
        self.client.force_authenticate(user=self.other)
        resp = self.client.post(self.url, {'name': 'x', 'content': TF_CONTENT})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


# ── Config Detail / Update / Delete ───────────────────────────────────────────

class ConfigDetailTests(BaseAutotfTest):
    def setUp(self):
        super().setUp()
        self.config = self.create_config()
        self.url = reverse('tf-config-detail', kwargs={'config_pk': self.config.pk})

    def test_get_detail(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.data['data']
        self.assertEqual(data['name'], 'my-config')
        self.assertIn('file', data)
        self.assertIsNone(data['report'])

    def test_get_not_found(self):
        resp = self.client.get(
            reverse('tf-config-detail', kwargs={'config_pk': 9999}))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_forbidden_for_other_user(self):
        self.client.force_authenticate(user=self.other)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_update_name_only(self):
        resp = self.client.put(self.url, {'name': 'renamed'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['data']['name'], 'renamed')

    def test_update_name_only_preserves_is_scanned(self):
        self.config.is_scanned = True
        self.config.save()
        resp = self.client.put(self.url, {'name': 'renamed'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data['data']['is_scanned'])

    def test_update_content_resets_is_scanned(self):
        self.config.is_scanned = True
        self.config.save()
        resp = self.client.put(self.url, {'content': 'resource "aws_s3_bucket" "b" {}'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data['data']['is_scanned'])

    def test_update_file_resets_is_scanned(self):
        self.config.is_scanned = True
        self.config.save()
        resp = self.client.put(
            self.url, {'file': make_tf_file('new.tf')}, format='multipart')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data['data']['is_scanned'])

    def test_update_duplicate_name_rejected(self):
        self.create_config('other-cfg')
        resp = self.client.put(self.url, {'name': 'other-cfg'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_empty_payload_rejected(self):
        resp = self.client.put(self.url, {})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_file_and_content_together_rejected(self):
        resp = self.client.put(
            self.url,
            {'file': make_tf_file(), 'content': TF_CONTENT},
            format='multipart',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_forbidden_for_other_user(self):
        self.client.force_authenticate(user=self.other)
        resp = self.client.put(self.url, {'name': 'hacked'})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete(self):
        resp = self.client.delete(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(TerraformConfig.objects.filter(pk=self.config.pk).exists())

    def test_delete_forbidden_for_other_user(self):
        self.client.force_authenticate(user=self.other)
        resp = self.client.delete(self.url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(TerraformConfig.objects.filter(pk=self.config.pk).exists())


# ── Config Content ─────────────────────────────────────────────────────────────

class ConfigContentTests(BaseAutotfTest):
    def setUp(self):
        super().setUp()
        self.config = self.create_config()
        self.url = reverse('tf-config-content', kwargs={'config_pk': self.config.pk})

    def test_get_content(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['data']['content'], TF_CONTENT)

    def test_get_content_forbidden(self):
        self.client.force_authenticate(user=self.other)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


# ── Full Scan ──────────────────────────────────────────────────────────────────

class FullScanTests(BaseAutotfTest):
    def setUp(self):
        super().setUp()
        self.config = self.create_config()
        self.url = reverse('tf-config-scan-full', kwargs={'config_pk': self.config.pk})

    @patch('autotf.services.ScanService._execute', side_effect=_mock_execute)
    def test_full_scan_returns_done_report(self, _):
        resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.data['data']
        self.assertEqual(data['status'], ScanReport.DONE)
        self.assertIsNotNone(data['scanned_at'])
        self.assertIn('result', data)

    @patch('autotf.services.ScanService._execute', side_effect=_mock_execute)
    def test_full_scan_sets_config_is_scanned(self, _):
        self.client.post(self.url)
        self.config.refresh_from_db()
        self.assertTrue(self.config.is_scanned)

    def test_full_scan_no_enabled_tools_returns_404(self):
        self.tool.is_enabled = False
        self.tool.save()
        resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_full_scan_forbidden_for_other_user(self):
        self.client.force_authenticate(user=self.other)
        resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


# ── Manual Scan ────────────────────────────────────────────────────────────────

class ManualScanTests(BaseAutotfTest):
    def setUp(self):
        super().setUp()
        self.config = self.create_config()
        self.url = reverse('tf-config-scan-manual', kwargs={'config_pk': self.config.pk})

    @patch('autotf.services.ScanService._execute', side_effect=_mock_execute)
    def test_manual_scan_returns_done_report(self, _):
        resp = self.client.post(
            self.url, {'tool_ids': [self.tool.pk]}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['data']['status'], ScanReport.DONE)

    def test_manual_scan_invalid_tool_id_rejected(self):
        resp = self.client.post(self.url, {'tool_ids': [9999]}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_manual_scan_disabled_tool_rejected(self):
        resp = self.client.post(
            self.url, {'tool_ids': [self.tool_disabled.pk]}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_manual_scan_empty_tool_ids_rejected(self):
        resp = self.client.post(self.url, {'tool_ids': []}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_manual_scan_missing_tool_ids_rejected(self):
        resp = self.client.post(self.url, {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_manual_scan_forbidden_for_other_user(self):
        self.client.force_authenticate(user=self.other)
        resp = self.client.post(
            self.url, {'tool_ids': [self.tool.pk]}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


# ── Scan Report ────────────────────────────────────────────────────────────────

class ReportTests(BaseAutotfTest):
    def setUp(self):
        super().setUp()
        self.config = self.create_config()
        self.url = reverse('tf-config-report', kwargs={'config_pk': self.config.pk})

    def test_get_report(self):
        self.create_report(self.config)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.data['data']
        self.assertEqual(data['status'], ScanReport.DONE)
        self.assertIn('result', data)
        self.assertIsNotNone(data['scanned_at'])

    def test_get_report_not_found(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_report_forbidden_for_other_user(self):
        self.create_report(self.config)
        self.client.force_authenticate(user=self.other)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_report_clears_is_scanned(self):
        self.create_report(self.config)
        self.config.is_scanned = True
        self.config.save()
        resp = self.client.delete(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(ScanReport.objects.filter(config=self.config).exists())
        self.config.refresh_from_db()
        self.assertFalse(self.config.is_scanned)

    def test_delete_report_not_found(self):
        resp = self.client.delete(self.url)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_report_forbidden_for_other_user(self):
        self.create_report(self.config)
        self.client.force_authenticate(user=self.other)
        resp = self.client.delete(self.url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


# ── Tool List ──────────────────────────────────────────────────────────────────

class ToolListTests(BaseAutotfTest):
    def setUp(self):
        super().setUp()
        self.url = reverse('tf-tool-list')

    def test_list_returns_only_enabled_tools(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        names = [t['name'] for t in resp.data['data']]
        self.assertIn('tfsec', names)
        self.assertNotIn('checkov', names)

    def test_list_unauthenticated(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
