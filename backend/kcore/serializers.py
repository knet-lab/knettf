from rest_framework import serializers
from .models import User, KubeCluster


# 输出
class UserResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'is_staff']


class KubeClusterResponseSerializer(serializers.ModelSerializer):
    owner = UserResponseSerializer(read_only=True)

    class Meta:
        model = KubeCluster
        fields = ['id', 'name', 'owner', 'kubeconfig',
                  'is_active', 'last_synced_at', 'created_at']


# 输入
class UserCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['username', 'email', 'password']
        extra_kwargs = {'password': {'write_only': True}}

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError('Username already exists')
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('Email already exists')
        return value


class UserUpdateSerializer(serializers.Serializer):
    username = serializers.CharField(required=False)
    email = serializers.EmailField(required=False)


class KubeClusterCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = KubeCluster
        fields = ['name', 'kubeconfig']

    def validate_name(self, value):
        owner = self.context['owner']
        if KubeCluster.objects.filter(owner=owner, name=value).exists():
            raise serializers.ValidationError('Cluster name already exists')
        return value


class KubeClusterUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = KubeCluster
        fields = ['name', 'kubeconfig']
        extra_kwargs = {
            'name': {'required': False},
            'kubeconfig': {'required': False},
        }

    def validate_name(self, value):
        owner = self.context['owner']
        instance = self.context['instance']
        if KubeCluster.objects.filter(owner=owner, name=value).exclude(pk=instance.pk).exists():
            raise serializers.ValidationError('Cluster name already exists')
        return value
