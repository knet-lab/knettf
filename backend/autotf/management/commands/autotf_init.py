import json
import subprocess

from django.conf import settings
from django.core.management.base import BaseCommand

from autotf.models import TerraformTool


def _get_tool_version(cmd: list) -> str:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return proc.stdout.strip().splitlines()[0] if proc.stdout.strip() else 'unknown'
    except Exception:
        return 'unknown'


def _get_tf_version() -> str:
    try:
        proc = subprocess.run(
            [settings.TF_BIN, 'version', '-json'],
            capture_output=True, text=True, timeout=10,
        )
        data = json.loads(proc.stdout)
        return data.get('terraform_version', 'unknown')
    except Exception:
        return 'unknown'


def _build_tools() -> list:
    tf = settings.TF_BIN
    return [
        {
            'name': 'terraform_validate',
            'version_fn': _get_tf_version,
            'cmd': f'{tf} validate -json',
            'init_cmd': f'{tf} init -backend=false -input=false',
            'output_format': TerraformTool.OUTPUT_JSON,
            'items_path': 'diagnostics',
            'severity_field': 'severity',
            'severity_map': {'error': 'HIGH', 'warning': 'MEDIUM'},
            'rule_id_field': 'address',
            'description_field': 'summary',
            'location_file_field': 'range.filename',
            'location_line_field': 'range.start.line',
        },
        {
            'name': 'tflint',
            'version_fn': lambda: _get_tool_version(['tflint', '--version']),
            'cmd': 'tflint --format json {target_dir}',
            'init_cmd': '',
            'output_format': TerraformTool.OUTPUT_JSON,
            'items_path': 'issues',
            'severity_field': 'rule.severity',
            'severity_map': {'error': 'HIGH', 'warning': 'MEDIUM', 'notice': 'LOW'},
            'rule_id_field': 'rule.name',
            'description_field': 'message',
            'location_file_field': 'range.filename',
            'location_line_field': 'range.start.line',
        },
        {
            'name': 'checkov',
            'version_fn': lambda: _get_tool_version([f'{settings.AUTOTF_TOOLS_BIN}/checkov', '--version']),
            'cmd': f'{settings.AUTOTF_TOOLS_BIN}/checkov' + ' -d {target_dir} -o sarif --quiet',
            'init_cmd': '',
            'output_format': TerraformTool.OUTPUT_SARIF,
            'items_path': '', 'severity_field': '', 'severity_map': {},
            'rule_id_field': '', 'description_field': '',
            'location_file_field': '', 'location_line_field': '',
        },
        {
            'name': 'tfsec',
            'version_fn': lambda: _get_tool_version(['tfsec', '--version']),
            'cmd': 'tfsec {target_dir} --format sarif --no-color',
            'init_cmd': '',
            'output_format': TerraformTool.OUTPUT_SARIF,
            'items_path': '', 'severity_field': '', 'severity_map': {},
            'rule_id_field': '', 'description_field': '',
            'location_file_field': '', 'location_line_field': '',
        },
        {
            'name': 'trivy',
            'version_fn': lambda: _get_tool_version(['trivy', '--version']),
            'cmd': 'trivy config {target_dir} --format sarif',
            'init_cmd': '',
            'output_format': TerraformTool.OUTPUT_SARIF,
            'items_path': '', 'severity_field': '', 'severity_map': {},
            'rule_id_field': '', 'description_field': '',
            'location_file_field': '', 'location_line_field': '',
        },
    ]


class Command(BaseCommand):
    help = 'Initialize autotf: create terraform/ directory and seed TerraformTool records'

    def handle(self, *args, **options):
        terraform_dir = settings.BASE_DIR / 'terraform'
        terraform_dir.mkdir(exist_ok=True)
        self.stdout.write(f'Directory ready: {terraform_dir}')

        for tool_def in _build_tools():
            version_fn = tool_def.pop('version_fn')
            version = version_fn()
            tool, created = TerraformTool.objects.update_or_create(
                name=tool_def['name'],
                defaults={**{k: v for k, v in tool_def.items() if k != 'name'}, 'version': version},
            )
            action = 'Created' if created else 'Updated'
            self.stdout.write(self.style.SUCCESS(
                f'{action} tool: {tool.name} v{version}'
            ))
