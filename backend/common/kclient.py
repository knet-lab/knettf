# k8s client tools
import yaml
from kubernetes import client, config


class KubeClient:
    def __init__(self, kubeconfig: str):
        kubeconfig_dict = yaml.safe_load(kubeconfig)
        api_client = config.new_client_from_config_dict(kubeconfig_dict)
        self.core = client.CoreV1Api(api_client)
        self.apps = client.AppsV1Api(api_client)

    # Namespace
    def get_namespaces(self):
        return self.core.list_namespace().items

    def create_namespace(self, name: str):
        body = client.V1Namespace(metadata=client.V1ObjectMeta(name=name))
        return self.core.create_namespace(body)

    def delete_namespace(self, name: str):
        return self.core.delete_namespace(name)

    # Pod
    def get_pods(self, namespace: str):
        return self.core.list_namespaced_pod(namespace).items

    def get_pod(self, namespace: str, name: str):
        return self.core.read_namespaced_pod(name, namespace)

    def delete_pod(self, namespace: str, name: str):
        return self.core.delete_namespaced_pod(name, namespace)

    # Deployment
    def get_deployments(self, namespace: str):
        return self.apps.list_namespaced_deployment(namespace).items

    def get_deployment(self, namespace: str, name: str):
        return self.apps.read_namespaced_deployment(name, namespace)

    def create_deployment(self, namespace: str, body: dict):
        return self.apps.create_namespaced_deployment(namespace, body)

    def update_deployment(self, namespace: str, name: str, body: dict):
        return self.apps.patch_namespaced_deployment(name, namespace, body)

    def delete_deployment(self, namespace: str, name: str):
        return self.apps.delete_namespaced_deployment(name, namespace)

    # Service
    def get_services(self, namespace: str):
        return self.core.list_namespaced_service(namespace).items

    def get_service(self, namespace: str, name: str):
        return self.core.read_namespaced_service(name, namespace)

    def update_service(self, namespace: str, name: str, body: dict):
        return self.core.patch_namespaced_service(name, namespace, body)

    def create_service(self, namespace: str, body: dict):
        return self.core.create_namespaced_service(namespace, body)

    def delete_service(self, namespace: str, name: str):
        return self.core.delete_namespaced_service(name, namespace)

    # ConfigMap
    def get_configmaps(self, namespace: str):
        return self.core.list_namespaced_config_map(namespace).items

    def get_configmap(self, namespace: str, name: str):
        return self.core.read_namespaced_config_map(name, namespace)

    def create_configmap(self, namespace: str, name: str, data: dict):
        body = client.V1ConfigMap(metadata=client.V1ObjectMeta(name=name), data=data)
        return self.core.create_namespaced_config_map(namespace, body)

    def update_configmap(self, namespace: str, name: str, data: dict):
        body = client.V1ConfigMap(metadata=client.V1ObjectMeta(name=name), data=data)
        return self.core.patch_namespaced_config_map(name, namespace, body)

    def delete_configmap(self, namespace: str, name: str):
        return self.core.delete_namespaced_config_map(name, namespace)


    # DeamonSet
    def get_daemonsets(self, namespace: str):
        return self.apps.list_namespaced_daemon_set(namespace).items
    
    def get_daemonset(self, namespace: str, name: str):
        return self.apps.read_namespaced_daemon_set(name, namespace)
    
    def create_daemonset(self, namespace: str, body: dict):
        return self.apps.create_namespaced_daemon_set(namespace, body)
    
    def update_daemonset(self, namespace: str, name: str, body: dict):
        return self.apps.patch_namespaced_daemon_set(name, namespace, body)
    
    def delete_daemonset(self, namespace: str, name: str):
        return self.apps.delete_namespaced_daemon_set(name, namespace)