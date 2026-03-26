import subprocess

from django.conf import settings
from django.core.management.base import BaseCommand

from autotf.models import TerraformTool


def _get_tf_version() -> str:
    try:
        from django.conf import settings
        proc = subprocess.run(
            [settings.TF_BIN, 'version', '-json'],
            capture_output=True, text=True, timeout=10,
        )
        import json
        data = json.loads(proc.stdout)
        return data.get('terraform_version', 'unknown')
    except Exception:
        return 'unknown'


class Command(BaseCommand):
    help = 'Initialize autotf: create terraform/ directory and seed TerraformTool'

    def handle(self, *args, **options):
        terraform_dir = settings.BASE_DIR / 'terraform'
        terraform_dir.mkdir(exist_ok=True)
        self.stdout.write(f'Directory ready: {terraform_dir}')

        version = _get_tf_version()
        tool, created = TerraformTool.objects.update_or_create(
            name='terraform_validate',
            defaults={'version': version, 'is_enabled': True},
        )
        action = 'Created' if created else 'Updated'
        self.stdout.write(self.style.SUCCESS(
            f'{action} tool: terraform_validate v{version}'
        ))
