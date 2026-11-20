from rest_framework import serializers
from .models import DetectionRecord


class DetectionRecordSerializer(serializers.ModelSerializer):
    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]  DRF 存根已声明 Meta，子类重定义属正常用法
        model = DetectionRecord
        fields = "__all__"


class FlowInputSerializer(serializers.Serializer):
    """
    Validates the 35-feature eBPF flow payload for ads_ml OCSVM detection.
    Field types follow ebpf_35_features / encode_columns / numeric_columns in the pipeline.
    """

    # ── categorical (OrdinalEncoder inside pipeline) ──────────────────────────
    src_ip   = serializers.CharField(max_length=64)
    dst_ip   = serializers.CharField(max_length=64)
    protocol = serializers.CharField(max_length=16)

    # ── ports ─────────────────────────────────────────────────────────────────
    src_port = serializers.IntegerField(min_value=0, max_value=65535, default=0)
    dst_port = serializers.IntegerField(min_value=0, max_value=65535, default=0)

    # ── timing / volume ───────────────────────────────────────────────────────
    flow_duration      = serializers.FloatField(default=0.0)
    total_packets      = serializers.IntegerField(default=0)
    fwd_packets        = serializers.IntegerField(default=0)
    bwd_packets        = serializers.IntegerField(default=0)
    fwd_ratio          = serializers.FloatField(default=0.0)
    packets_per_second = serializers.FloatField(default=0.0)

    # ── inter-arrival time ────────────────────────────────────────────────────
    iat_mean = serializers.FloatField(default=0.0)
    iat_std  = serializers.FloatField(default=0.0)
    iat_min  = serializers.FloatField(default=0.0)
    iat_max  = serializers.FloatField(default=0.0)

    # ── TCP flags ─────────────────────────────────────────────────────────────
    syn_count = serializers.IntegerField(default=0)
    ack_count = serializers.IntegerField(default=0)
    fin_count = serializers.IntegerField(default=0)
    rst_count = serializers.IntegerField(default=0)
    psh_count = serializers.IntegerField(default=0)
    urg_count = serializers.IntegerField(default=0)

    syn_ratio = serializers.FloatField(default=0.0)
    ack_ratio = serializers.FloatField(default=0.0)
    fin_ratio = serializers.FloatField(default=0.0)
    rst_ratio = serializers.FloatField(default=0.0)

    # ── reply / verdict ───────────────────────────────────────────────────────
    reply_count     = serializers.IntegerField(default=0)
    reply_ratio     = serializers.FloatField(default=0.0)
    forwarded_count = serializers.IntegerField(default=0)
    drop_count      = serializers.IntegerField(default=0)
    drop_ratio      = serializers.FloatField(default=0.0)

    # ── boolean flags (0/1 int, matches aggregate_flows.py int(...) output) ───
    is_bidirectional   = serializers.IntegerField(default=0)
    is_tcp             = serializers.IntegerField(default=0)
    is_udp             = serializers.IntegerField(default=0)
    is_icmp            = serializers.IntegerField(default=0)
    is_well_known_port = serializers.IntegerField(default=0)

    # ── metadata ──────────────────────────────────────────────────────────────
    label = serializers.CharField(required=False, allow_blank=True, allow_null=True, default="")  # pyright: ignore[reportAssignmentType]  字段名与 Field.label 同名，运行时由元类取走，不冲突
    model = serializers.CharField(required=False, allow_null=True, default=None)


class BatchFlowInputSerializer(serializers.Serializer):
    flows = FlowInputSerializer(many=True)
    model = serializers.CharField(required=False, allow_null=True, default=None)
