from django.db import models


class TerraformConfig(models.Model):
    id = models.AutoField(primary_key=True)
    owner = models.ForeignKey(
        'kcore.User', on_delete=models.CASCADE, related_name='terraform_configs')
    name = models.CharField(max_length=255)
    file = models.FileField(upload_to='terraform/')
    is_scanned = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [['owner', 'name']]


class TerraformTool(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255, unique=True)
    version = models.CharField(max_length=50)
    is_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)


class ScanReport(models.Model):
    PENDING = 'pending'
    RUNNING = 'running'
    DONE = 'done'
    FAILED = 'failed'
    STATUS_CHOICES = [
        (PENDING, 'Pending'),
        (RUNNING, 'Running'),
        (DONE, 'Done'),
        (FAILED, 'Failed'),
    ]

    id = models.AutoField(primary_key=True)
    config = models.OneToOneField(
        TerraformConfig, on_delete=models.CASCADE, related_name='scan_report')
    tools = models.ManyToManyField(TerraformTool)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    result = models.JSONField(default=dict)
    scanned_at = models.DateTimeField(null=True, blank=True)
