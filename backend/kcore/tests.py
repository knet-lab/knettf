from unittest.mock import MagicMock, patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from kcore.models import User, KubeCluster


KUBECONFIG = "apiVersion: v1\nclusters: []\ncontexts: []\ncurrent-context: ''\nkind: Config\nusers: []\n"


class BaseKcoreTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='alice', email='alice@test.com', password='pass')
        self.other = User.objects.create_user(
            username='bob', email='bob@test.com', password='pass')
        self.client.force_authenticate(user=self.user)

    def create_cluster(self, name='test-cluster', owner=None):
        return KubeCluster.objects.create(
            owner=owner or self.user, name=name, kubeconfig=KUBECONFIG)


# ── UserMe ─────────────────────────────────────────────────────────────────────

class UserMeTests(BaseKcoreTest):
    def setUp(self):
        super().setUp()
        self.url = reverse('user-me')

    def test_get_me(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['data']['username'], 'alice')
        self.assertEqual(resp.data['data']['email'], 'alice@test.com')

    def test_get_me_unauthenticated(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


# ── UserList ───────────────────────────────────────────────────────────────────

class UserListTests(BaseKcoreTest):
    def setUp(self):
        super().setUp()
        self.url = reverse('user-list')

    def test_register_new_user(self):
        resp = self.client.post(self.url, {
            'username': 'charlie', 'email': 'charlie@test.com', 'password': 'pass123'
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(username='charlie').exists())

    def test_register_duplicate_username_rejected(self):
        resp = self.client.post(self.url, {
            'username': 'alice', 'email': 'new@test.com', 'password': 'pass'
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_duplicate_email_rejected(self):
        resp = self.client.post(self.url, {
            'username': 'newuser', 'email': 'alice@test.com', 'password': 'pass'
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_missing_fields_rejected(self):
        resp = self.client.post(self.url, {'username': 'x'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_can_list_users(self):
        admin = User.objects.create_user(
            username='admin', email='admin@test.com', password='pass', is_staff=True)
        self.client.force_authenticate(user=admin)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        usernames = [u['username'] for u in resp.data['data']]
        self.assertIn('alice', usernames)
        self.assertIn('bob', usernames)

    def test_non_admin_cannot_list_users(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_unauthenticated(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


# ── UserDetail ─────────────────────────────────────────────────────────────────

class UserDetailTests(BaseKcoreTest):
    def setUp(self):
        super().setUp()
        self.url = reverse('user-detail', kwargs={'pk': self.user.pk})

    def test_get_own_user(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['data']['username'], 'alice')

    def test_get_other_user_forbidden(self):
        resp = self.client.get(
            reverse('user-detail', kwargs={'pk': self.other.pk}))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_not_found(self):
        resp = self.client.get(reverse('user-detail', kwargs={'pk': 9999}))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_own_user(self):
        resp = self.client.put(self.url, {'username': 'alice2', 'email': 'alice2@test.com'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'alice2')

    def test_update_other_user_forbidden(self):
        resp = self.client.put(
            reverse('user-detail', kwargs={'pk': self.other.pk}),
            {'username': 'hacked'})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_own_user(self):
        resp = self.client.delete(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())

    def test_delete_other_user_forbidden(self):
        resp = self.client.delete(
            reverse('user-detail', kwargs={'pk': self.other.pk}))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(User.objects.filter(pk=self.other.pk).exists())


# ── KubeClusterList ────────────────────────────────────────────────────────────

class KubeClusterListTests(BaseKcoreTest):
    def setUp(self):
        super().setUp()
        self.url = reverse('user-cluster-list', kwargs={'pk': self.user.pk})

    def test_list_own_clusters(self):
        self.create_cluster('c1')
        self.create_cluster('c2')
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data['data']), 2)

    def test_list_excludes_other_user_clusters(self):
        self.create_cluster('other-c', owner=self.other)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data['data']), 0)

    def test_list_forbidden_for_other_user(self):
        self.client.force_authenticate(user=self.other)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_cluster(self):
        resp = self.client.post(self.url, {'name': 'new-c', 'kubeconfig': KUBECONFIG})
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(KubeCluster.objects.filter(owner=self.user, name='new-c').exists())

    def test_create_duplicate_cluster_name_rejected(self):
        self.create_cluster('dup')
        resp = self.client.post(self.url, {'name': 'dup', 'kubeconfig': KUBECONFIG})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_missing_fields_rejected(self):
        resp = self.client.post(self.url, {'name': 'no-kube'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_forbidden_for_other_user(self):
        self.client.force_authenticate(user=self.other)
        resp = self.client.post(self.url, {'name': 'x', 'kubeconfig': KUBECONFIG})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


# ── KubeClusterDetail ──────────────────────────────────────────────────────────

class KubeClusterDetailTests(BaseKcoreTest):
    def setUp(self):
        super().setUp()
        self.cluster = self.create_cluster()
        self.url = reverse('cluster-detail', kwargs={'pk': self.cluster.pk})

    def test_get_cluster(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['data']['name'], 'test-cluster')

    def test_get_cluster_forbidden_for_other_user(self):
        self.client.force_authenticate(user=self.other)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_cluster_not_found(self):
        resp = self.client.get(reverse('cluster-detail', kwargs={'pk': 9999}))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_cluster_name(self):
        resp = self.client.put(self.url, {'name': 'renamed'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.cluster.refresh_from_db()
        self.assertEqual(self.cluster.name, 'renamed')

    def test_update_duplicate_name_rejected(self):
        self.create_cluster('other-cluster')
        resp = self.client.put(self.url, {'name': 'other-cluster'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_forbidden_for_other_user(self):
        self.client.force_authenticate(user=self.other)
        resp = self.client.put(self.url, {'name': 'hacked'})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_cluster(self):
        resp = self.client.delete(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(KubeCluster.objects.filter(pk=self.cluster.pk).exists())

    def test_delete_forbidden_for_other_user(self):
        self.client.force_authenticate(user=self.other)
        resp = self.client.delete(self.url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(KubeCluster.objects.filter(pk=self.cluster.pk).exists())


# ── KubeResource (mock KubeClient) ────────────────────────────────────────────

def _fake_resource(name='fake', namespace='default'):
    r = MagicMock()
    r.to_dict.return_value = {'name': name, 'namespace': namespace}
    return r


class KubeResourceListTests(BaseKcoreTest):
    def setUp(self):
        super().setUp()
        self.cluster = self.create_cluster()
        self.base_url = reverse('kube-resource-list', kwargs={
            'cluster_id': self.cluster.pk, 'resource_type': 'pods'})

    def _url(self, resource_type):
        return reverse('kube-resource-list', kwargs={
            'cluster_id': self.cluster.pk, 'resource_type': resource_type})

    @patch('kcore.services.KubeClient')
    def test_list_namespaces(self, MockClient):
        MockClient.return_value.get_namespaces.return_value = [_fake_resource('ns')]
        resp = self.client.get(self._url('namespaces'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data['data']['resources']), 1)

    @patch('kcore.services.KubeClient')
    def test_list_pods(self, MockClient):
        MockClient.return_value.get_pods.return_value = [_fake_resource('pod-1')]
        resp = self.client.get(self._url('pods'), {'namespace': 'default'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    @patch('kcore.services.KubeClient')
    def test_list_pods_missing_namespace_returns_400(self, MockClient):
        resp = self.client.get(self._url('pods'))
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('kcore.services.KubeClient')
    def test_list_invalid_resource_type_returns_400(self, MockClient):
        resp = self.client.get(self._url('widgets'), {'namespace': 'default'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('kcore.services.KubeClient')
    def test_list_forbidden_for_other_user(self, MockClient):
        self.client.force_authenticate(user=self.other)
        resp = self.client.get(self._url('pods'), {'namespace': 'default'})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    @patch('kcore.services.KubeClient')
    def test_create_namespace(self, MockClient):
        MockClient.return_value.create_namespace.return_value = _fake_resource('new-ns')
        resp = self.client.post(self._url('namespaces'), {'name': 'new-ns'})
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    @patch('kcore.services.KubeClient')
    def test_create_namespace_missing_name_returns_400(self, MockClient):
        resp = self.client.post(self._url('namespaces'), {})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('kcore.services.KubeClient')
    def test_create_deployment(self, MockClient):
        MockClient.return_value.create_deployment.return_value = _fake_resource('dep')
        resp = self.client.post(self._url('deployments'), {
            'namespace': 'default', 'name': 'dep', 'image': 'nginx'})
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    @patch('kcore.services.KubeClient')
    def test_create_deployment_missing_namespace_returns_400(self, MockClient):
        resp = self.client.post(self._url('deployments'), {'name': 'dep'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('kcore.services.KubeClient')
    def test_create_configmap(self, MockClient):
        MockClient.return_value.create_configmap.return_value = _fake_resource('cm')
        resp = self.client.post(self._url('configmaps'), {
            'namespace': 'default', 'name': 'cm', 'data': {'key': 'val'}})
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    @patch('kcore.services.KubeClient')
    def test_create_configmap_missing_data_returns_400(self, MockClient):
        resp = self.client.post(self._url('configmaps'), {
            'namespace': 'default', 'name': 'cm'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('kcore.services.KubeClient')
    def test_create_invalid_type_returns_400(self, MockClient):
        resp = self.client.post(self._url('widgets'), {
            'namespace': 'default', 'name': 'x'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('kcore.services.KubeClient')
    def test_delete_namespace(self, MockClient):
        MockClient.return_value.delete_namespace.return_value = None
        resp = self.client.delete(self._url('namespaces'), {'name': 'old-ns'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    @patch('kcore.services.KubeClient')
    def test_delete_namespace_missing_name_returns_400(self, MockClient):
        resp = self.client.delete(self._url('namespaces'), {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('kcore.services.KubeClient')
    def test_delete_pod(self, MockClient):
        MockClient.return_value.delete_pod.return_value = None
        resp = self.client.delete(self._url('pods'), {
            'namespace': 'default', 'name': 'pod-1'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    @patch('kcore.services.KubeClient')
    def test_delete_missing_namespace_returns_400(self, MockClient):
        resp = self.client.delete(self._url('pods'), {'name': 'pod-1'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('kcore.services.KubeClient')
    def test_delete_missing_name_returns_400(self, MockClient):
        resp = self.client.delete(self._url('pods'), {'namespace': 'default'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('kcore.services.KubeClient')
    def test_delete_invalid_type_returns_400(self, MockClient):
        resp = self.client.delete(self._url('widgets'), {
            'namespace': 'default', 'name': 'x'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('kcore.services.KubeClient')
    def test_update_deployment(self, MockClient):
        MockClient.return_value.update_deployment.return_value = _fake_resource('dep')
        resp = self.client.put(self._url('deployments'), {
            'namespace': 'default', 'name': 'dep', 'replicas': 3})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    @patch('kcore.services.KubeClient')
    def test_update_missing_namespace_returns_400(self, MockClient):
        resp = self.client.put(self._url('deployments'), {'name': 'dep'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('kcore.services.KubeClient')
    def test_update_missing_name_returns_400(self, MockClient):
        resp = self.client.put(self._url('deployments'), {'namespace': 'default'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('kcore.services.KubeClient')
    def test_update_configmap_missing_data_returns_400(self, MockClient):
        resp = self.client.put(self._url('configmaps'), {
            'namespace': 'default', 'name': 'cm'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('kcore.services.KubeClient')
    def test_update_invalid_type_returns_400(self, MockClient):
        resp = self.client.put(self._url('widgets'), {
            'namespace': 'default', 'name': 'x'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


# ── KubeApply ──────────────────────────────────────────────────────────────────

VALID_YAML = """
apiVersion: v1
kind: Namespace
metadata:
  name: test-ns
"""


class KubeApplyTests(BaseKcoreTest):
    def setUp(self):
        super().setUp()
        self.cluster = self.create_cluster()
        self.url = reverse('kube-apply', kwargs={'cluster_id': self.cluster.pk})

    @patch('kcore.services.KubeClient')
    def test_apply_success(self, MockClient):
        MockClient.return_value.apply_yaml.return_value = [
            {'status': 'ok', 'name': 'test-ns', 'kind': 'Namespace'}]
        resp = self.client.post(self.url, {'yaml': VALID_YAML})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data['data']['results']), 1)

    @patch('kcore.services.KubeClient')
    def test_apply_with_error_result_returns_400(self, MockClient):
        MockClient.return_value.apply_yaml.return_value = [
            {'status': 'error', 'name': 'x', 'kind': 'Namespace', 'error': 'forbidden'}]
        resp = self.client.post(self.url, {'yaml': VALID_YAML})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('kcore.services.KubeClient')
    def test_apply_exception_returns_400(self, MockClient):
        MockClient.return_value.apply_yaml.side_effect = Exception('k8s error')
        resp = self.client.post(self.url, {'yaml': VALID_YAML})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_apply_missing_yaml_returns_400(self):
        resp = self.client.post(self.url, {})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_apply_empty_yaml_returns_400(self):
        resp = self.client.post(self.url, {'yaml': '   '})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('kcore.services.KubeClient')
    def test_apply_forbidden_for_other_user(self, MockClient):
        self.client.force_authenticate(user=self.other)
        resp = self.client.post(self.url, {'yaml': VALID_YAML})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


# ── KubeResourceDetail ─────────────────────────────────────────────────────────

class KubeResourceDetailTests(BaseKcoreTest):
    def setUp(self):
        super().setUp()
        self.cluster = self.create_cluster()

    def _url(self, resource_type, name):
        return reverse('kube-resource-detail', kwargs={
            'cluster_id': self.cluster.pk,
            'resource_type': resource_type,
            'name': name,
        })

    @patch('kcore.services.KubeClient')
    def test_get_resource_yaml(self, MockClient):
        MockClient.return_value.get_resource_yaml.return_value = 'apiVersion: v1\n'
        resp = self.client.get(self._url('pods', 'my-pod'), {'namespace': 'default'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('yaml', resp.data['data'])

    @patch('kcore.services.KubeClient')
    def test_get_resource_yaml_value_error_returns_400(self, MockClient):
        MockClient.return_value.get_resource_yaml.side_effect = ValueError('bad type')
        resp = self.client.get(self._url('widgets', 'x'), {'namespace': 'default'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('kcore.services.KubeClient')
    def test_get_resource_yaml_exception_returns_502(self, MockClient):
        MockClient.return_value.get_resource_yaml.side_effect = Exception('k8s error')
        resp = self.client.get(self._url('pods', 'dead-pod'), {'namespace': 'default'})
        self.assertEqual(resp.status_code, status.HTTP_502_BAD_GATEWAY)

    @patch('kcore.services.KubeClient')
    def test_restart_deployment(self, MockClient):
        MockClient.return_value.restart_deployment.return_value = None
        resp = self.client.post(self._url('deployments', 'my-dep'), {
            'namespace': 'default'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('restarted', resp.data['data']['message'])

    @patch('kcore.services.KubeClient')
    def test_restart_missing_namespace_returns_400(self, MockClient):
        resp = self.client.post(self._url('deployments', 'my-dep'), {})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('kcore.services.KubeClient')
    def test_restart_unsupported_type_returns_400(self, MockClient):
        MockClient.return_value.restart_resource.side_effect = ValueError('not supported')
        resp = self.client.post(self._url('configmaps', 'my-cm'), {'namespace': 'default'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('kcore.services.KubeClient')
    def test_delete_resource(self, MockClient):
        MockClient.return_value.delete_pod.return_value = None
        resp = self.client.delete(self._url('pods', 'dead-pod'), {
            'namespace': 'default'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    @patch('kcore.services.KubeClient')
    def test_delete_namespace_resource(self, MockClient):
        MockClient.return_value.delete_namespace.return_value = None
        resp = self.client.delete(self._url('namespaces', 'old-ns'), {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    @patch('kcore.services.KubeClient')
    def test_delete_invalid_type_returns_400(self, MockClient):
        resp = self.client.delete(self._url('widgets', 'x'), {
            'namespace': 'default'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('kcore.services.KubeClient')
    def test_delete_exception_returns_502(self, MockClient):
        MockClient.return_value.delete_pod.side_effect = Exception('k8s error')
        resp = self.client.delete(self._url('pods', 'dead-pod'), {
            'namespace': 'default'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_502_BAD_GATEWAY)

    @patch('kcore.services.KubeClient')
    def test_get_forbidden_for_other_user(self, MockClient):
        self.client.force_authenticate(user=self.other)
        resp = self.client.get(self._url('pods', 'x'), {'namespace': 'default'})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
