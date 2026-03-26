from django.db import models

# Create your models here.
class AnomalyEvent(models.Model):
    id = models.AutoField(primary_key=True)
    cluster = models.ForeignKey('kcore.KubeCluster', on_delete=models.CASCADE, related_name='anomaly_events')
    event_type = models.CharField(max_length=255)  # e.g., "pod_crash", "high_cpu_usage"
    src_ip = models.GenericIPAddressField(null=True, blank=True)
    dst_ip = models.GenericIPAddressField(null=True, blank=True)
    severity = models.CharField(max_length=50)  # e.g., "low", "medium", "high"
    description = models.TextField()
    detected_at = models.DateTimeField(auto_now_add=True)
    detected_model = models.CharField(max_length=255)  # e.g., "AI-based", "rule-based"

    # a score from AI
    score = models.FloatField()  # Anomaly score calculated by the detection algorithm, higher means more severe

class CiliumPolicy(models.Model):
    id = models.AutoField(primary_key=True)
    description = models.TextField()  # A brief description of the policy, this can be used to provide more context about the policy, such as its purpose or any specific rules it contains
    action = models.CharField(max_length=50)  # e.g., "allow", "deny", "log"
    tartget_ip = models.GenericIPAddressField(null=True, blank=True)  # The target IP address that the policy applies to, this can help to identify which policies are affecting which parts of the network
    event = models.ForeignKey(AnomalyEvent, on_delete=models.CASCADE, related_name='cilium_policies')  # Link to the AnomalyEvent that triggered this policy, this can help to understand the context of the anomaly and how the policies are responding to it
    status = models.CharField(max_length=50)  # e.g., "active", "inactive", "pending"
    applied_at = models.DateTimeField(auto_now_add=True)  # The time when the policy was applied, this can help to track the timeline of events and how quickly policies are responding to anomalies
    