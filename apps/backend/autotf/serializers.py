from rest_framework import serializers
from .models import TerraformConfig, TerraformTool, ScanReport


# ── TerraformTool ──────────────────────────────────────────────────────────────

class TerraformToolSerializer(serializers.ModelSerializer):
    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]  DRF 存根已声明 Meta，子类重定义属正常用法
        model = TerraformTool
        fields = [
            'id', 'name', 'version', 'is_enabled',
            'cmd', 'init_cmd', 'output_format',
            'items_path', 'severity_field', 'severity_map',
            'rule_id_field', 'description_field',
            'location_file_field', 'location_line_field',
        ]


class TerraformToolWriteSerializer(serializers.ModelSerializer):
    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]  DRF 存根已声明 Meta，子类重定义属正常用法
        model = TerraformTool
        fields = [
            'name', 'version', 'is_enabled',
            'cmd', 'init_cmd', 'output_format',
            'items_path', 'severity_field', 'severity_map',
            'rule_id_field', 'description_field',
            'location_file_field', 'location_line_field',
        ]


# ── ScanReport ─────────────────────────────────────────────────────────────────

class ScanReportSummarySerializer(serializers.ModelSerializer):
    """Embedded in config list / detail — lightweight, no full result."""
    tools = TerraformToolSerializer(many=True, read_only=True)

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]  DRF 存根已声明 Meta，子类重定义属正常用法
        model = ScanReport
        fields = ['id', 'status', 'tools', 'scanned_at']


class ScanReportDetailSerializer(serializers.ModelSerializer):
    """Full report including result JSON."""
    tools = TerraformToolSerializer(many=True, read_only=True)

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]  DRF 存根已声明 Meta，子类重定义属正常用法
        model = ScanReport
        fields = ['id', 'status', 'tools', 'result', 'scanned_at']


# ── TerraformConfig ────────────────────────────────────────────────────────────

class TerraformConfigListSerializer(serializers.ModelSerializer):
    """Config list — lightweight, embeds report summary if exists."""
    report = serializers.SerializerMethodField()

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]  DRF 存根已声明 Meta，子类重定义属正常用法
        model = TerraformConfig
        fields = [
            'id', 'name', 'is_scanned', 'created_at', 'updated_at', 'report',
            'last_apply_at', 'last_apply_status', 'last_apply_output',
        ]

    def get_report(self, obj):
        try:
            return ScanReportSummarySerializer(obj.scan_report).data
        except ScanReport.DoesNotExist:
            return None


class TerraformConfigDetailSerializer(serializers.ModelSerializer):
    """Config detail — full info + report summary (no full findings)."""
    report = serializers.SerializerMethodField()

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]  DRF 存根已声明 Meta，子类重定义属正常用法
        model = TerraformConfig
        fields = [
            'id', 'name', 'file', 'is_scanned', 'created_at', 'updated_at', 'report',
            'last_apply_at', 'last_apply_status', 'last_apply_output',
        ]

    def get_report(self, obj):
        try:
            return ScanReportSummarySerializer(obj.scan_report).data
        except ScanReport.DoesNotExist:
            return None


class TerraformConfigCreateSerializer(serializers.ModelSerializer):
    """File upload path."""
    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]  DRF 存根已声明 Meta，子类重定义属正常用法
        model = TerraformConfig
        fields = ['name', 'file']

    def validate_name(self, value):
        owner_id = self.context['owner_id']
        if TerraformConfig.objects.filter(owner_id=owner_id, name=value).exists():
            raise serializers.ValidationError('Config name already exists')
        return value


class TerraformConfigTextCreateSerializer(serializers.Serializer):
    """Online editor path — accepts raw text, service writes it to a file."""
    name = serializers.CharField(max_length=255)
    content = serializers.CharField()

    def validate_name(self, value):
        owner_id = self.context['owner_id']
        if TerraformConfig.objects.filter(owner_id=owner_id, name=value).exists():
            raise serializers.ValidationError('Config name already exists')
        return value


class TerraformConfigUpdateSerializer(serializers.Serializer):
    """Update — either a new file or new text content, both optional."""
    name = serializers.CharField(max_length=255, required=False)
    file = serializers.FileField(required=False)
    content = serializers.CharField(required=False)

    def validate_name(self, value):
        owner_id = self.context['owner_id']
        instance = self.context['instance']
        if TerraformConfig.objects.filter(owner_id=owner_id, name=value).exclude(pk=instance.pk).exists():
            raise serializers.ValidationError('Config name already exists')
        return value

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError('At least one field must be provided')
        if 'file' in attrs and 'content' in attrs:
            raise serializers.ValidationError('Provide either file or content, not both')
        return attrs


# ── Scan trigger ───────────────────────────────────────────────────────────────

class ScanTriggerSerializer(serializers.Serializer):
    """Manual scan — user picks a subset of enabled tool IDs."""
    tool_ids = serializers.ListField(
        child=serializers.IntegerField(), allow_empty=False
    )

    def validate_tool_ids(self, value):
        enabled_ids = set(
            TerraformTool.objects.filter(is_enabled=True).values_list('id', flat=True)
        )
        invalid = set(value) - enabled_ids
        if invalid:
            raise serializers.ValidationError(
                f'Tool IDs not available: {sorted(invalid)}'
            )
        return value
