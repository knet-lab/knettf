import shutil

from django.conf import settings
from django.core.management.base import BaseCommand

from autotf.models import ScanReport, TerraformConfig, TerraformTool


class Command(BaseCommand):
    help = 'Clear all autotf data: ScanReport, TerraformConfig, TerraformTool, and uploaded files'

    def handle(self, *args, **options):
        report_count = ScanReport.objects.count()
        config_count = TerraformConfig.objects.count()
        tool_count = TerraformTool.objects.count()

        ScanReport.objects.all().delete()
        TerraformConfig.objects.all().delete()
        TerraformTool.objects.all().delete()

        terraform_dir = settings.BASE_DIR / 'terraform'
        if terraform_dir.exists():
            shutil.rmtree(terraform_dir)
            self.stdout.write(f'Deleted directory: {terraform_dir}')

        self.stdout.write(self.style.SUCCESS(
            f'Cleared: {report_count} reports, {config_count} configs, {tool_count} tools'
        ))
