from typing import Any

from rest_framework.views import APIView
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAdminUser
from common.response import ResponseMixin
from common.permissions import check_owner
import common
from .serializers import (
    KubeClusterUpdateSerializer, UserResponseSerializer, UserCreateSerializer, UserUpdateSerializer,
    KubeClusterResponseSerializer, KubeClusterCreateSerializer,
)
from .services import UserService, KubeClusterService, KubeResourceService


class UserMe(APIView, ResponseMixin):
    def get(self, request: common.Request):
        return self.success_response(UserResponseSerializer(request.user).data)


class UserList(APIView, ResponseMixin):
    def get_permissions(self):
        if self.request.method == 'POST':
            return [AllowAny()]
        if self.request.method == 'GET':
            return [IsAdminUser()]
        return super().get_permissions()

    def get(self, request: common.Request):
        users = UserService.get_users_list()
        return self.success_response(UserResponseSerializer(users, many=True).data)

    def post(self, request: common.Request):
        serializer = UserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = UserService.create_user(**serializer.validated_data)
        return self.success_response(UserResponseSerializer(user).data, status=status.HTTP_201_CREATED)


class UserDetail(APIView, ResponseMixin):
    def get(self, request: common.Request, pk: int):
        user = UserService.get_user_by_id(pk)
        check_owner(request, user.pk)
        return self.success_response(UserResponseSerializer(user).data)

    def put(self, request: common.Request, pk: int):
        user = UserService.get_user_by_id(pk)
        check_owner(request, user.pk)
        serializer = UserUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = UserService.update_user(user, **serializer.validated_data)
        return self.success_response(UserResponseSerializer(user).data)

    def delete(self, request: common.Request, pk: int):
        user = UserService.get_user_by_id(pk)
        check_owner(request, user.pk)
        user.delete()
        return self.success_response({'message': 'User deleted'})


class KubeClusterList(APIView, ResponseMixin):
    def get(self, request: common.Request, pk: int):
        user = UserService.get_user_by_id(pk)
        check_owner(request, user.pk)
        clusters = KubeClusterService.get_clusters_by_user(user)
        return self.success_response(KubeClusterResponseSerializer(clusters, many=True).data)

    def post(self, request: common.Request, pk: int):
        user = UserService.get_user_by_id(pk)
        check_owner(request, user.pk)
        serializer = KubeClusterCreateSerializer(
            data=request.data, context={'owner': user})
        serializer.is_valid(raise_exception=True)
        cluster = KubeClusterService.create_cluster(
            owner=user, **serializer.validated_data)
        return self.success_response(KubeClusterResponseSerializer(cluster).data, status=status.HTTP_201_CREATED)


class KubeClusterDetail(APIView, ResponseMixin):
    def get(self, request: common.Request, pk: int):
        cluster = KubeClusterService.get_cluster_by_id(pk)
        check_owner(request, cluster.owner.pk)
        return self.success_response(KubeClusterResponseSerializer(cluster).data)

    def delete(self, request: common.Request, pk: int):
        cluster = KubeClusterService.get_cluster_by_id(pk)
        check_owner(request, cluster.owner.pk)
        cluster.delete()
        return self.success_response({'message': 'Cluster deleted'})

    def put(self, request: common.Request, pk: int):
        cluster = KubeClusterService.get_cluster_by_id(pk)
        check_owner(request, cluster.owner.pk)
        serializer = KubeClusterUpdateSerializer(
            data=request.data, context={'owner': cluster.owner, 'instance': cluster})
        serializer.is_valid(raise_exception=True)
        cluster = KubeClusterService.update_cluster(
            cluster, **serializer.validated_data)
        return self.success_response(KubeClusterResponseSerializer(cluster).data)


class KubeResourceList(APIView, ResponseMixin):
    def get(self, request: common.Request, cluster_id: int, resource_type: str):
        cluster = KubeClusterService.get_cluster_by_id(cluster_id)
        check_owner(request, cluster.owner.pk)
        bk_service = KubeResourceService(cluster)
        if resource_type == 'namespaces':
            resources = bk_service.get_namespaces()
            return self.success_response({'resources': [r.to_dict() for r in resources]})

        namespace = request.query_params.get('namespace')
        if not namespace:
            return self.error_response('Namespace query parameter is required', status=status.HTTP_400_BAD_REQUEST)
        if resource_type == 'pods':
            resources = bk_service.get_pods(namespace)
        elif resource_type == 'deployments':
            resources = bk_service.get_deployments(namespace)
        elif resource_type == 'services':
            resources = bk_service.get_services(namespace)
        elif resource_type == 'configmaps':
            resources = bk_service.get_configmaps(namespace)
        elif resource_type == 'daemonsets':
            resources = bk_service.get_daemonsets(namespace)
        else:
            return self.error_response('Invalid resource type', status=status.HTTP_400_BAD_REQUEST)

        return self.success_response({'resources': [r.to_dict() for r in resources]})

    def post(self, request: common.Request, cluster_id: int, resource_type: str):
        cluster = KubeClusterService.get_cluster_by_id(cluster_id)
        check_owner(request, cluster.owner.pk)
        bk_service = KubeResourceService(cluster)
        resource: Any   # kubernetes 客户端无类型标注，运行时是 V1Xxx 对象
        if resource_type == 'namespaces':
            name = request.data.get('name')
            if not name:
                return self.error_response('Name is required for namespace', status=status.HTTP_400_BAD_REQUEST)
            resource = bk_service.create_namespace(name)
            return self.success_response({'resource': resource.to_dict()}, status=status.HTTP_201_CREATED)

        namespace = request.data.get('namespace')
        if not namespace:
            return self.error_response('Namespace is required', status=status.HTTP_400_BAD_REQUEST)
        if resource_type == 'deployments':
            resource = bk_service.create_deployment(namespace, request.data)
        elif resource_type == 'services':
            resource = bk_service.create_service(namespace, request.data)
        elif resource_type == 'configmaps':
            name = request.data.get('name')
            data = request.data.get('data')
            if not name or not data:
                return self.error_response('Name and data are required for configmap', status=status.HTTP_400_BAD_REQUEST)
            resource = bk_service.create_configmap(namespace, name, data)
        elif resource_type == 'daemonsets':
            resource = bk_service.create_daemonset(namespace, request.data)
        else:
            return self.error_response('Invalid resource type', status=status.HTTP_400_BAD_REQUEST)

        return self.success_response({'resource': resource.to_dict()}, status=status.HTTP_201_CREATED)

    def delete(self, request: common.Request, cluster_id: int, resource_type: str):
        cluster = KubeClusterService.get_cluster_by_id(cluster_id)
        check_owner(request, cluster.owner.pk)
        bk_service = KubeResourceService(cluster)
        if resource_type == 'namespaces':
            name = request.data.get('name')
            if not name:
                return self.error_response('Name is required for namespace deletion', status=status.HTTP_400_BAD_REQUEST)
            bk_service.delete_namespace(name)
            return self.success_response({'message': 'Namespace deleted'})

        namespace = request.data.get('namespace')
        if not namespace:
            return self.error_response('Namespace is required for deletion', status=status.HTTP_400_BAD_REQUEST)
        name = request.data.get('name')
        if not name:
            return self.error_response('Name is required for deletion', status=status.HTTP_400_BAD_REQUEST)

        if resource_type == 'pods':
            bk_service.delete_pod(namespace, name)
        elif resource_type == 'deployments':
            bk_service.delete_deployment(namespace, name)
        elif resource_type == 'services':
            bk_service.delete_service(namespace, name)
        elif resource_type == 'configmaps':
            bk_service.delete_configmap(namespace, name)
        elif resource_type == 'daemonsets':
            bk_service.delete_daemonset(namespace, name)
        else:
            return self.error_response('Invalid resource type', status=status.HTTP_400_BAD_REQUEST)

        return self.success_response({'message': f'{resource_type[:-1].capitalize()} deleted'})

    def put(self, request: common.Request, cluster_id: int, resource_type: str):
        cluster = KubeClusterService.get_cluster_by_id(cluster_id)
        check_owner(request, cluster.owner.pk)
        bk_service = KubeResourceService(cluster)
        resource: Any   # kubernetes 客户端无类型标注，运行时是 V1Xxx 对象
        namespace = request.data.get('namespace')
        if not namespace:
            return self.error_response('Namespace is required for update', status=status.HTTP_400_BAD_REQUEST)
        name = request.data.get('name')
        if not name:
            return self.error_response('Name is required for update', status=status.HTTP_400_BAD_REQUEST)

        if resource_type == 'deployments':
            resource = bk_service.update_deployment(
                namespace, name, request.data)
        elif resource_type == 'services':
            resource = bk_service.update_service(namespace, name, request.data)
        elif resource_type == 'configmaps':
            data = request.data.get('data')
            if not data:
                return self.error_response('Data is required for configmap update', status=status.HTTP_400_BAD_REQUEST)
            resource = bk_service.update_configmap(namespace, name, data)
        elif resource_type == 'daemonsets':
            resource = bk_service.update_daemonset(
                namespace, name, request.data)
        else:
            return self.error_response('Invalid resource type', status=status.HTTP_400_BAD_REQUEST)

        return self.success_response({'resource': resource.to_dict()})


class KubeApply(APIView, ResponseMixin):
    """POST /clusters/{cluster_id}/apply/  — apply raw YAML (one or more docs)."""

    def post(self, request: common.Request, cluster_id: int):
        cluster = KubeClusterService.get_cluster_by_id(cluster_id)
        check_owner(request, cluster.owner.pk)
        yaml_str = request.data.get('yaml', '')
        if not yaml_str or not yaml_str.strip():
            return self.error_response('yaml field is required', status=status.HTTP_400_BAD_REQUEST)
        bk_service = KubeResourceService(cluster)
        try:
            results = bk_service.apply_yaml(yaml_str)
        except Exception as e:
            return self.error_response(str(e), status=status.HTTP_400_BAD_REQUEST)
        has_error = any(r['status'] == 'error' for r in results)
        if has_error:
            return self.error_response('One or more documents failed to apply', status=status.HTTP_400_BAD_REQUEST,
                                       data={'results': results})
        return self.success_response({'results': results})


class KubeResourceDetail(APIView, ResponseMixin):
    """
    GET  /clusters/{id}/resources/{type}/{name}/?namespace=xxx  → YAML string
    POST /clusters/{id}/resources/{type}/{name}/                → restart
         body: {namespace, force (bool, optional)}
    DELETE /clusters/{id}/resources/{type}/{name}/              → delete
         body: {namespace} (omit for cluster-scoped resources like namespaces)
    """

    def get(self, request: common.Request, cluster_id: int, resource_type: str, name: str):
        cluster = KubeClusterService.get_cluster_by_id(cluster_id)
        check_owner(request, cluster.owner.pk)
        namespace = request.query_params.get('namespace') or None
        bk_service = KubeResourceService(cluster)
        try:
            yaml_str = bk_service.get_resource_yaml(resource_type, namespace, name)
        except ValueError as e:
            return self.error_response(str(e), status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return self.error_response(str(e), status=status.HTTP_502_BAD_GATEWAY)
        return self.success_response({'yaml': yaml_str})

    def post(self, request: common.Request, cluster_id: int, resource_type: str, name: str):
        cluster = KubeClusterService.get_cluster_by_id(cluster_id)
        check_owner(request, cluster.owner.pk)
        namespace = request.data.get('namespace')
        if not namespace:
            return self.error_response('namespace is required', status=status.HTTP_400_BAD_REQUEST)
        force = bool(request.data.get('force', False))
        bk_service = KubeResourceService(cluster)
        try:
            bk_service.restart_resource(resource_type, namespace, name, force)
        except ValueError as e:
            return self.error_response(str(e), status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return self.error_response(str(e), status=status.HTTP_502_BAD_GATEWAY)
        mode = 'force' if force else 'normal'
        return self.success_response({'message': f'{name} restarted ({mode})'})

    def delete(self, request: common.Request, cluster_id: int, resource_type: str, name: str):
        cluster = KubeClusterService.get_cluster_by_id(cluster_id)
        check_owner(request, cluster.owner.pk)
        bk_service = KubeResourceService(cluster)
        namespaced_delete = {
            'pods': bk_service.delete_pod,
            'deployments': bk_service.delete_deployment,
            'services': bk_service.delete_service,
            'configmaps': bk_service.delete_configmap,
            'daemonsets': bk_service.delete_daemonset,
        }
        if resource_type != 'namespaces' and resource_type not in namespaced_delete:
            return self.error_response('Invalid resource type', status=status.HTTP_400_BAD_REQUEST)
        namespace = request.data.get('namespace') or None
        # 带命名空间的资源必须给 namespace（与创建 / 更新接口一致），否则会把 None 传给 K8s 客户端
        if resource_type != 'namespaces' and not namespace:
            return self.error_response('Namespace is required', status=status.HTTP_400_BAD_REQUEST)
        try:
            if resource_type == 'namespaces':
                bk_service.delete_namespace(name)
            elif namespace:
                namespaced_delete[resource_type](namespace, name)
        except Exception as e:
            return self.error_response(str(e), status=status.HTTP_502_BAD_GATEWAY)
        return self.success_response({'message': f'{resource_type[:-1].capitalize()} "{name}" deleted'})
