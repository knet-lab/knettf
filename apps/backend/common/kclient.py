# k8s client tools
import yaml
from kubernetes import client, config


class KubeClient:
    def __init__(self, kubeconfig: str):
        kubeconfig_dict = yaml.safe_load(kubeconfig)
        self._api_client = config.new_client_from_config_dict(kubeconfig_dict)
        self.core = client.CoreV1Api(self._api_client)
        self.apps = client.AppsV1Api(self._api_client)

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


    # ── YAML Apply ──────────────────────────────────────────────────────────────

    def apply_yaml(self, yaml_str: str) -> list:
        """Server-side apply for one or more YAML documents (separated by ---)."""
        from kubernetes import dynamic
        dyn_client = dynamic.DynamicClient(self._api_client)
        results = []
        for doc in yaml.safe_load_all(yaml_str):
            if doc is None:
                continue
            api_version = doc.get('apiVersion', 'v1')
            kind        = doc.get('kind', '')
            name        = (doc.get('metadata') or {}).get('name', '')
            namespace   = (doc.get('metadata') or {}).get('namespace')
            try:
                resource_api = dyn_client.resources.get(api_version=api_version, kind=kind)
                try:
                    resource_api.server_side_apply(
                        body=doc,
                        field_manager='netsentinel',
                        force_conflicts=True,
                        namespace=namespace,
                    )
                except AttributeError:
                    # Older kubernetes-client: fall back to patch-or-create
                    try:
                        resource_api.patch(body=doc, name=name, namespace=namespace)
                    except Exception:
                        resource_api.create(body=doc, namespace=namespace)
                results.append({'kind': kind, 'name': name, 'status': 'applied'})
            except Exception as e:
                results.append({'kind': kind, 'name': name, 'status': 'error', 'message': str(e)})
        return results

    def get_resource_yaml(self, resource_type: str, namespace: str | None, name: str) -> str:
        """Return the live resource as a YAML string (camelCase, proper K8s format)."""
        _TYPE_MAP = {
            'deployments': ('apps/v1', 'Deployment'),
            'services':    ('v1',      'Service'),
            'configmaps':  ('v1',      'ConfigMap'),
            'daemonsets':  ('apps/v1', 'DaemonSet'),
            'namespaces':  ('v1',      'Namespace'),
            'pods':        ('v1',      'Pod'),
        }
        if resource_type not in _TYPE_MAP:
            raise ValueError(f'Unsupported resource type: {resource_type}')
        api_version, kind = _TYPE_MAP[resource_type]
        from kubernetes import dynamic
        dyn_client = dynamic.DynamicClient(self._api_client)
        resource_api = dyn_client.resources.get(api_version=api_version, kind=kind)
        obj = resource_api.get(name=name, namespace=namespace)
        return yaml.dump(obj.to_dict(), default_flow_style=False, allow_unicode=True)

    # ── Restart ─────────────────────────────────────────────────────────────────

    def _patch_restart_annotation(self, patch_fn, name: str, namespace: str) -> None:
        import datetime
        now = datetime.datetime.utcnow().isoformat() + 'Z'
        patch = {
            'spec': {
                'template': {
                    'metadata': {
                        'annotations': {'kubectl.kubernetes.io/restartedAt': now}
                    }
                }
            }
        }
        patch_fn(name, namespace, patch)

    def _force_delete_pods(self, namespace: str, match_labels: dict) -> None:
        selector = ','.join(f'{k}={v}' for k, v in (match_labels or {}).items())
        pods = self.core.list_namespaced_pod(namespace, label_selector=selector)
        for pod in pods.items:
            try:
                self.core.delete_namespaced_pod(
                    pod.metadata.name, namespace, grace_period_seconds=0
                )
            except Exception:
                pass

    def restart_deployment(self, namespace: str, name: str, force: bool = False) -> None:
        if not force:
            self._patch_restart_annotation(
                self.apps.patch_namespaced_deployment, name, namespace
            )
        else:
            dep = self.apps.read_namespaced_deployment(name, namespace)
            self._force_delete_pods(namespace, dep.spec.selector.match_labels)

    def restart_daemonset(self, namespace: str, name: str, force: bool = False) -> None:
        if not force:
            self._patch_restart_annotation(
                self.apps.patch_namespaced_daemon_set, name, namespace
            )
        else:
            ds = self.apps.read_namespaced_daemon_set(name, namespace)
            self._force_delete_pods(namespace, ds.spec.selector.match_labels)

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