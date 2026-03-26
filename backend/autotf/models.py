from django.db import models
    

# Create your models here.
class TerrafromConfig(models.Model):
    id = models.AutoField(primary_key=True)
    owner = models.ForeignKey('kcore.User', on_delete=models.CASCADE, related_name='terraform_configs')
    name = models.CharField(max_length=255)
    content = models.TextField()     # The actual terraform configuration content
    created_at = models.DateTimeField(auto_now_add=True)


class TerraformTool(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255, unique=True)  # e.g., "tfsec", "checkov"
    version = models.CharField(max_length=50)  # e.g., "0.58.0"
    created_at = models.DateTimeField(auto_now_add=True)


class ScanReport(models.Model):
    id = models.AutoField(primary_key=True)
    owner = models.ForeignKey('kcore.User', on_delete=models.CASCADE, related_name='scan_reports')
    tools = models.ManyToManyField(TerraformTool)           # change to ManyToManyField to support multiple tools in one scan report
    status = models.CharField(max_length=50)  # e.g., "pending", "running", "completed", "failed"           if network not good can save the middle status
    config = models.ForeignKey(TerrafromConfig, on_delete=models.CASCADE, related_name='scan_reports')
    created_at = models.DateTimeField(auto_now_add=True)
    result = models.JSONField(default=dict)  # JSON outer is a dict, this is findings Field in PRD
    """
    When end all scanning, every result of tools will be process by tool result parser which is a function returning a dict with a fixed format to easily save into JSONField.
    result example:
    {
        summary: {
            "tool_name": "<tool_name>",
            "result": {
                ... # here is real result content for <tool_name>, every tool has different content, but the outer structure is same, which is a dict with "tool_name" and "result" keys
            }
        }
    }
    """