from django.db import models


class DetectionRecord(models.Model):
    """One flow inference result: one model run on one network flow."""

    # Flow 5-tuple
    src_ip = models.GenericIPAddressField()
    dst_ip = models.GenericIPAddressField()
    src_port = models.IntegerField()
    dst_port = models.IntegerField()
    protocol = models.CharField(max_length=10)

    # Full 30-feature flow input as JSON
    flow_input = models.JSONField()

    # Model result
    model_name = models.CharField(max_length=100)
    is_attack = models.BooleanField()
    confidence = models.FloatField()
    attack_type = models.CharField(max_length=100, null=True, blank=True)
    explanation = models.TextField(blank=True)
    raw_output = models.JSONField(default=dict)

    # Cilium feedback
    cilium_action = models.CharField(max_length=50, null=True, blank=True)
    cilium_reason = models.TextField(blank=True)

    # Ground-truth label from dataset (0=normal, 1=attack), optional
    label = models.IntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False  # DDL managed by hand-written migration SQL (partitioned table)
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["is_attack"]),
            models.Index(fields=["model_name"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        tag = "ATTACK" if self.is_attack else "normal"
        return f"[{tag}] {self.src_ip}→{self.dst_ip} ({self.model_name})"


class CollectRecord(models.Model):
    """One raw flow captured in collect-only mode (no model run, no verdict)."""

    src_ip = models.GenericIPAddressField()
    dst_ip = models.GenericIPAddressField()
    src_port = models.IntegerField()
    dst_port = models.IntegerField()
    protocol = models.CharField(max_length=10)

    # Full flow input (35 features) as JSON, same shape as DetectionRecord.flow_input
    flow_input = models.JSONField()

    # Ground-truth label if known at capture time (0=normal, 1=attack), optional
    label = models.IntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["created_at"])]

    def __str__(self):
        return f"[collect] {self.src_ip}→{self.dst_ip}"
