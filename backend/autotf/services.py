import json
import os
import subprocess
import tempfile

from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

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
    def get_all_tools():
        return TerraformTool.objects.all()

    @staticmethod
    def get_enabled_tools():
        return TerraformTool.objects.filter(is_enabled=True)

    @staticmethod
    def get_tools_by_ids(tool_ids: list):
        return TerraformTool.objects.filter(id__in=tool_ids, is_enabled=True)

    @staticmethod
    def get_tool_by_id(tool_id: int) -> TerraformTool:
        try:
            return TerraformTool.objects.get(id=tool_id)
        except TerraformTool.DoesNotExist:
            raise NotFound('Tool not found')

    @staticmethod
    def create_tool(**kwargs) -> TerraformTool:
        tool = TerraformTool(**kwargs)
        tool.save()
        return tool

    @staticmethod
    def update_tool(tool: TerraformTool, **kwargs) -> TerraformTool:
        for key, value in kwargs.items():
            setattr(tool, key, value)
        tool.save()
        return tool

    @staticmethod
    def delete_tool(tool: TerraformTool):
        tool.delete()


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


class ApplyService:
    @staticmethod
    def apply(config: TerraformConfig):
        # ── Prerequisite checks ──────────────────────────────────────────
        try:
            report = config.scan_report
        except ScanReport.DoesNotExist:
            raise ValidationError('No scan report found. Run a scan first.')

        if report.status != ScanReport.DONE:
            raise ValidationError('Scan is not complete.')

        if report.result.get('summary', {}).get('high', 0) > 0:
            raise ValidationError('Cannot apply: HIGH severity issues found in scan report.')

        # ── Run terraform init + apply in a temp dir ─────────────────────
        tf_bin = settings.TF_BIN
        apply_status = TerraformConfig.APPLY_FAILED
        output = ''

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                tf_path = os.path.join(tmpdir, 'main.tf')
                config.file.open('rb')
                with open(tf_path, 'wb') as f:
                    f.write(config.file.read())
                config.file.close()

                # terraform init
                init_proc = subprocess.run(
                    [tf_bin, 'init', '-input=false'],
                    capture_output=True, text=True, cwd=tmpdir, timeout=120,
                )
                output += init_proc.stdout + init_proc.stderr

                if init_proc.returncode != 0:
                    apply_status = TerraformConfig.APPLY_FAILED
                else:
                    # terraform apply
                    apply_proc = subprocess.run(
                        [tf_bin, 'apply', '-auto-approve', '-input=false'],
                        capture_output=True, text=True, cwd=tmpdir, timeout=300,
                    )
                    output += apply_proc.stdout + apply_proc.stderr
                    apply_status = (
                        TerraformConfig.APPLY_SUCCESS
                        if apply_proc.returncode == 0
                        else TerraformConfig.APPLY_FAILED
                    )
        except subprocess.TimeoutExpired:
            output += '\n[Timeout: terraform apply exceeded time limit]'
            apply_status = TerraformConfig.APPLY_FAILED
        except Exception as e:
            output += f'\n[Internal error: {e}]'
            apply_status = TerraformConfig.APPLY_FAILED

        config.last_apply_status = apply_status
        config.last_apply_output = output
        config.last_apply_at = timezone.now()
        config.save(update_fields=['last_apply_status', 'last_apply_output', 'last_apply_at'])

        return config


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
                    tool_result = ScanService._run_tool(tool, tmpdir, tf_path)
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

        except Exception:
            import traceback; traceback.print_exc()
            report.status = ScanReport.FAILED
            report.save(update_fields=['status'])

    @staticmethod
    def _run_tool(tool: TerraformTool, target_dir: str, target_file: str) -> dict:
        """Execute tool using its stored cmd/init_cmd, then dispatch to the right parser."""
        if not tool.cmd:
            return {'items': []}

        cmd_str = tool.cmd.format(target_dir=target_dir, target_file=target_file)
        cmd = cmd_str.split()

        extra_path = settings.AUTOTF_TOOLS_BIN
        env = os.environ.copy()
        env['PATH'] = extra_path + ':' + env.get('PATH', '')

        # Run optional init command first (e.g. terraform init)
        if tool.init_cmd:
            init_str = tool.init_cmd.format(target_dir=target_dir, target_file=target_file)
            init_proc = subprocess.Popen(
                init_str.split(),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, cwd=target_dir, env=env,
            )
            init_proc.communicate()

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, cwd=target_dir, env=env,
            )
        except FileNotFoundError:
            return {'items': [], 'error': f'tool not found: {cmd[0]}'}

        stdout, _ = proc.communicate()

        fmt = tool.output_format
        if fmt == TerraformTool.OUTPUT_SARIF:
            return ScanService._parse_sarif(stdout)
        return ScanService._parse_json(stdout, tool)

    # ── Parsers ───────────────────────────────────────────────────

    @staticmethod
    def _get_nested(obj: dict, path: str):
        """Traverse dot-separated path, e.g. 'results.failed_checks' or 'range.start.line'."""
        for key in path.split('.'):
            if isinstance(obj, list):
                try:
                    obj = obj[int(key)]
                except (ValueError, IndexError):
                    return None
            elif isinstance(obj, dict):
                obj = obj.get(key)
            else:
                return None
            if obj is None:
                return None
        return obj

    @staticmethod
    def _parse_json(stdout: str, tool: TerraformTool) -> dict:
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            return {'items': []}

        raw_items = ScanService._get_nested(data, tool.items_path) if tool.items_path else []
        if not isinstance(raw_items, list):
            return {'items': []}

        sev_map: dict = tool.severity_map or {}
        items = []
        for r in raw_items:
            raw_sev = (ScanService._get_nested(r, tool.severity_field) or 'LOW') if tool.severity_field else 'LOW'
            severity = sev_map.get(str(raw_sev).lower(), sev_map.get(str(raw_sev).upper(), str(raw_sev).upper()))

            rule_id     = str(ScanService._get_nested(r, tool.rule_id_field) or '')       if tool.rule_id_field       else ''
            description = str(ScanService._get_nested(r, tool.description_field) or '')   if tool.description_field   else ''
            loc_file    = str(ScanService._get_nested(r, tool.location_file_field) or '')  if tool.location_file_field else ''
            loc_line    = str(ScanService._get_nested(r, tool.location_line_field) or '')  if tool.location_line_field else ''
            location    = f'{loc_file}:{loc_line}' if loc_file or loc_line else ''

            items.append({
                'rule_id': rule_id,
                'severity': severity,
                'description': description,
                'location': location,
            })
        return {'items': items}

    @staticmethod
    def _parse_sarif(stdout: str) -> dict:
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            return {'items': []}

        SEV_MAP = {'error': 'HIGH', 'warning': 'MEDIUM', 'note': 'LOW', 'none': 'LOW'}
        items = []
        for run in data.get('runs', []):
            rules = {r['id']: r for r in run.get('tool', {}).get('driver', {}).get('rules', [])}
            for result in run.get('results', []):
                rule_id = result.get('ruleId', '')
                level   = result.get('level', 'warning')
                severity = SEV_MAP.get(level, 'MEDIUM')

                # description: prefer rule's shortDescription, fallback to result message
                rule_meta = rules.get(rule_id, {})
                description = (
                    rule_meta.get('shortDescription', {}).get('text')
                    or result.get('message', {}).get('text', '')
                )

                location = ''
                locs = result.get('locations', [])
                if locs:
                    pl = locs[0].get('physicalLocation', {})
                    uri  = pl.get('artifactLocation', {}).get('uri', '')
                    line = pl.get('region', {}).get('startLine', '')
                    location = f'{uri}:{line}' if uri or line else ''

                items.append({
                    'rule_id': rule_id,
                    'severity': severity,
                    'description': description,
                    'location': location,
                })
        return {'items': items}

