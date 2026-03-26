import json
import os
import subprocess
import tempfile

from django.core.files.base import ContentFile
from django.utils import timezone
from rest_framework.exceptions import NotFound

from .models import ScanReport, TerraformConfig, TerraformTool


class TerraformConfigService:
    @staticmethod
    def get_config_by_id(config_id: int) -> TerraformConfig:
        try:
            return TerraformConfig.objects.get(id=config_id)
        except TerraformConfig.DoesNotExist:
            raise NotFound('Config not found')

    @staticmethod
    def get_configs_by_user(user) -> list:
        return TerraformConfig.objects.filter(owner=user)

    @staticmethod
    def create_from_file(owner, name: str, file) -> TerraformConfig:
        config = TerraformConfig(owner=owner, name=name, file=file)
        config.save()
        return config

    @staticmethod
    def create_from_text(owner, name: str, content: str) -> TerraformConfig:
        config = TerraformConfig(owner=owner, name=name)
        filename = f'{name}.tf'
        config.file.save(filename, ContentFile(content.encode()), save=True)
        return config

    @staticmethod
    def read_content(config: TerraformConfig) -> str:
        config.file.open('rb')
        content = config.file.read().decode('utf-8')
        config.file.close()
        return content

    @staticmethod
    def update_config(config: TerraformConfig, **kwargs) -> TerraformConfig:
        if 'name' in kwargs:
            config.name = kwargs['name']
        if 'file' in kwargs:
            config.file.delete(save=False)
            config.file = kwargs['file']
            config.is_scanned = False
        elif 'content' in kwargs:
            config.file.delete(save=False)
            filename = f'{config.name}.tf'
            config.file.save(filename, ContentFile(
                kwargs['content'].encode()), save=False)
            config.is_scanned = False
        elif 'name' in kwargs:
            # name-only: rename stored file to stay in sync; content unchanged, scan remains valid
            _, ext = os.path.splitext(config.file.name)
            new_filename = f'{config.name}{ext}'
            config.file.open('rb')
            file_content = config.file.read()
            config.file.close()
            config.file.delete(save=False)
            config.file.save(new_filename, ContentFile(
                file_content), save=False)
        config.save()
        return config

    @staticmethod
    def delete_config(config: TerraformConfig):
        config.file.delete(save=False)
        config.delete()


class TerraformToolService:
    @staticmethod
    def get_enabled_tools():
        return TerraformTool.objects.filter(is_enabled=True)

    @staticmethod
    def get_tools_by_ids(tool_ids: list):
        return TerraformTool.objects.filter(id__in=tool_ids, is_enabled=True)


class ScanReportService:
    @staticmethod
    def _get_report(config: TerraformConfig) -> ScanReport:
        try:
            return config.scan_report
        except ScanReport.DoesNotExist:
            raise NotFound('No scan report for this config')

    @staticmethod
    def get_report_by_config(config: TerraformConfig) -> ScanReport:
        return ScanReportService._get_report(config)

    @staticmethod
    def delete_report(config: TerraformConfig):
        ScanReportService._get_report(config).delete()
        config.is_scanned = False
        config.save(update_fields=['is_scanned'])


class ScanService:
    @staticmethod
    def run_full_scan(config: TerraformConfig):
        tools = list(TerraformTool.objects.filter(is_enabled=True))
        if not tools:
            raise NotFound('No enabled tools available')
        ScanService._execute(config, tools)

    @staticmethod
    def run_manual_scan(config: TerraformConfig, tool_ids: list):
        tools = list(TerraformTool.objects.filter(
            id__in=tool_ids, is_enabled=True))
        ScanService._execute(config, tools)

    @staticmethod
    def _execute(config: TerraformConfig, tools: list):
        report, _ = ScanReport.objects.update_or_create(
            config=config,
            defaults={'status': ScanReport.PENDING, 'result': {}, 'scanned_at': None},
        )
        report.tools.set(tools)
        report.status = ScanReport.RUNNING
        report.save(update_fields=['status'])

        config.is_scanned = False
        config.save(update_fields=['is_scanned'])

        try:
            result = {'summary': {'high': 0, 'medium': 0, 'low': 0}, 'tools': {}}

            with tempfile.TemporaryDirectory() as tmpdir:
                tf_path = os.path.join(tmpdir, 'main.tf')
                config.file.open('rb')
                with open(tf_path, 'wb') as f:
                    f.write(config.file.read())
                config.file.close()

                for tool in tools:
                    tool_result = ScanService._run_tool(tool.name, tmpdir)
                    result['tools'][tool.name] = tool_result
                    for item in tool_result['items']:
                        sev = item['severity'].lower()
                        if sev in result['summary']:
                            result['summary'][sev] += 1

            report.result = result
            report.status = ScanReport.DONE
            report.scanned_at = timezone.now()
            report.save(update_fields=['result', 'status', 'scanned_at'])

            config.is_scanned = True
            config.save(update_fields=['is_scanned'])

        except Exception as e:
            import traceback; traceback.print_exc()
            report.status = ScanReport.FAILED
            report.save(update_fields=['status'])

    @staticmethod
    def _run_tool(tool_name: str, target_dir: str) -> dict:
        runners = {
            'tfsec': ScanService._run_tfsec,
            'checkov': ScanService._run_checkov,
            'terraform_validate': ScanService._run_terraform_validate,
        }
        runner = runners.get(tool_name)
        if runner is None:
            return {'items': []}
        return runner(target_dir)

    @staticmethod
    def _run_tfsec(target_dir: str) -> dict:
        proc = subprocess.Popen(
            ['tfsec', target_dir, '--format', 'json', '--no-color'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        stdout, _ = proc.communicate()
        try:
            data = json.loads(stdout)
            items = []
            for r in data.get('results', []):
                loc = r.get('location', {})
                items.append({
                    'rule_id': r.get('rule_id', ''),
                    'severity': r.get('severity', 'LOW').upper(),
                    'description': r.get('description', ''),
                    'location': f"{loc.get('filename', '')}:{loc.get('start_line', '')}",
                })
            return {'items': items}
        except (json.JSONDecodeError, KeyError):
            return {'items': []}

    @staticmethod
    def _run_terraform_validate(target_dir: str) -> dict:
        from django.conf import settings
        tf_bin = settings.TF_BIN
        init = subprocess.Popen(
            [tf_bin, 'init', '-backend=false', '-input=false'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=target_dir,
        )
        init.communicate()
        proc = subprocess.Popen(
            [tf_bin, 'validate', '-json'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=target_dir,
        )
        stdout, _ = proc.communicate()
        try:
            data = json.loads(stdout)
            items = []
            for d in data.get('diagnostics', []):
                severity = d.get('severity', 'error').upper()
                if severity == 'ERROR':
                    severity = 'HIGH'
                elif severity == 'WARNING':
                    severity = 'MEDIUM'
                location = ''
                r = d.get('range')
                if r:
                    location = f"{r.get('filename', '')}:{r.get('start', {}).get('line', '')}"
                items.append({
                    'rule_id': d.get('address', 'TF_VALIDATE'),
                    'severity': severity,
                    'description': d.get('summary', '') + (f' — {d["detail"]}' if d.get('detail') else ''),
                    'location': location,
                })
            return {'items': items}
        except (json.JSONDecodeError, KeyError):
            return {'items': []}

    @staticmethod
    def _run_checkov(target_dir: str) -> dict:
        proc = subprocess.Popen(
            ['checkov', '-d', target_dir, '-o', 'json', '--quiet'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        stdout, _ = proc.communicate()
        try:
            data = json.loads(stdout)
            failed = data.get('results', {}).get('failed_checks', [])
            items = []
            for c in failed:
                line_range = c.get('file_line_range') or ['']
                items.append({
                    'rule_id': c.get('check_id', ''),
                    'severity': (c.get('severity') or 'MEDIUM').upper(),
                    'description': c.get('check', {}).get('name', ''),
                    'location': f"{c.get('repo_file_path', '')}:{line_range[0]}",
                })
            return {'items': items}
        except (json.JSONDecodeError, KeyError):
            return {'items': []}
