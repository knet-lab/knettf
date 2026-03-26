from .models import User, KubeCluster
from rest_framework.exceptions import NotFound
from common.kclient import KubeClient

class UserService:
    @staticmethod
    def get_user_by_id(user_id: int) -> User:
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise NotFound('User not found')

    @staticmethod
    def get_users_list() -> list:
        return User.objects.all()

    @staticmethod
    def create_user(username: str, email: str, password: str) -> User:
        user = User(username=username, email=email)
        user.set_password(password)
        user.save()
        return user

    @staticmethod
    def update_user(user: User, **kwargs) -> User:
        for key, value in kwargs.items():
            setattr(user, key, value)
        user.save()
        return user


class KubeClusterService:
    @staticmethod
    def get_cluster_by_id(cluster_id: int) -> KubeCluster:
        try:
            return KubeCluster.objects.get(id=cluster_id)
        except KubeCluster.DoesNotExist:
            raise NotFound('Cluster not found')

    @staticmethod
    def get_clusters_by_user(user: User) -> list:
        return KubeCluster.objects.filter(owner=user)
            

    @staticmethod
    def create_cluster(owner: User, name: str, kubeconfig: str) -> KubeCluster:
        cluster = KubeCluster(owner=owner, name=name, kubeconfig=kubeconfig)
        cluster.save()
        return cluster


    @staticmethod
    def update_cluster(cluster: KubeCluster, **kwargs) -> KubeCluster:
        for key, value in kwargs.items():
            setattr(cluster, key, value)
        cluster.save()
        return cluster
    

class KubeResourceService:
    def __init__(self, cluster: KubeCluster):
        self._client = KubeClient(cluster.kubeconfig)

    # Namespace
    def get_namespaces(self):
        return self._client.get_namespaces()

    def create_namespace(self, name: str):
        return self._client.create_namespace(name)

    def delete_namespace(self, name: str):
        return self._client.delete_namespace(name)

    # Pod
    def get_pods(self, namespace: str):
        return self._client.get_pods(namespace)

    def get_pod(self, namespace: str, name: str):
        return self._client.get_pod(namespace, name)

    def delete_pod(self, namespace: str, name: str):
        return self._client.delete_pod(namespace, name)

    # Deployment
    def get_deployments(self, namespace: str):
        return self._client.get_deployments(namespace)

    def get_deployment(self, namespace: str, name: str):
        return self._client.get_deployment(namespace, name)

    def create_deployment(self, namespace: str, body: dict):
        return self._client.create_deployment(namespace, body)

    def update_deployment(self, namespace: str, name: str, body: dict):
        return self._client.update_deployment(namespace, name, body)

    def delete_deployment(self, namespace: str, name: str):
        return self._client.delete_deployment(namespace, name)

    # Service
    def get_services(self, namespace: str):
        return self._client.get_services(namespace)

    def get_service(self, namespace: str, name: str):
        return self._client.get_service(namespace, name)

    def create_service(self, namespace: str, body: dict):
        return self._client.create_service(namespace, body)

    def update_service(self, namespace: str, name: str, body: dict):
        return self._client.update_service(namespace, name, body)

    def delete_service(self, namespace: str, name: str):
        return self._client.delete_service(namespace, name)

    # ConfigMap
    def get_configmaps(self, namespace: str):
        return self._client.get_configmaps(namespace)

    def get_configmap(self, namespace: str, name: str):
        return self._client.get_configmap(namespace, name)

    def create_configmap(self, namespace: str, name: str, data: dict):
        return self._client.create_configmap(namespace, name, data)

    def update_configmap(self, namespace: str, name: str, data: dict):
        return self._client.update_configmap(namespace, name, data)

    def delete_configmap(self, namespace: str, name: str):
        return self._client.delete_configmap(namespace, name)
    
    # DaemonSet
    def get_daemonsets(self, namespace: str):
        return self._client.get_daemonsets(namespace)
    
    def get_daemonset(self, namespace: str, name: str):
        return self._client.get_daemonset(namespace, name)
    
    def create_daemonset(self, namespace: str, body: dict):
        return self._client.create_daemonset(namespace, body)
    
    def update_daemonset(self, namespace: str, name: str, body: dict):
        return self._client.update_daemonset(namespace, name, body)
    
    def delete_daemonset(self, namespace: str, name: str):
        return self._client.delete_daemonset(namespace, name)