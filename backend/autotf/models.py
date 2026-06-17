from django.db import models


class TerraformConfig(models.Model):
    APPLY_SUCCESS = 'success'
    APPLY_FAILED  = 'failed'
    APPLY_STATUS_CHOICES = [
        (APPLY_SUCCESS, 'Success'),
        (APPLY_FAILED,  'Failed'),
    ]

    id = models.AutoField(primary_key=True)
    owner = models.ForeignKey(
        'kcore.User', on_delete=models.CASCADE, related_name='terraform_configs',
        db_constraint=False)
    name = models.CharField(max_length=255)
    file = models.FileField(upload_to='terraform/')
    is_scanned = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Apply tracking
    last_apply_at     = models.DateTimeField(null=True, blank=True)
    last_apply_status = models.CharField(
        max_length=10, choices=APPLY_STATUS_CHOICES, null=True, blank=True)
    last_apply_output = models.TextField(blank=True, default='')

    class Meta:
        unique_together = [['owner', 'name']]


class TerraformTool(models.Model):
    OUTPUT_JSON  = 'json'
    OUTPUT_SARIF = 'sarif'
    OUTPUT_FORMAT_CHOICES = [
        (OUTPUT_JSON,  'JSON'),
        (OUTPUT_SARIF, 'SARIF'),
    ]

    id         = models.AutoField(primary_key=True)
    name       = models.CharField(max_length=255, unique=True)
    version    = models.CharField(max_length=50)
    is_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Execution
    cmd      = models.CharField(max_length=500, default='')
    init_cmd = models.CharField(max_length=500, blank=True, default='')

    # Output
    output_format = models.CharField(
        max_length=10, choices=OUTPUT_FORMAT_CHOICES, default=OUTPUT_JSON)

    # JSON field mapping (only used when output_format == 'json')
    items_path          = models.CharField(max_length=255, blank=True, default='')
    severity_field      = models.CharField(max_length=100, blank=True, default='')
    severity_map        = models.JSONField(default=dict, blank=True)
    rule_id_field       = models.CharField(max_length=100, blank=True, default='')
    description_field   = models.CharField(max_length=100, blank=True, default='')
    location_file_field = models.CharField(max_length=100, blank=True, default='')
    location_line_field = models.CharField(max_length=100, blank=True, default='')


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
