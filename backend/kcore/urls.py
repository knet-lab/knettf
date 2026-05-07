from django.urls import path
from . import views

urlpatterns = [
    # User
    path('users/me/', views.UserMe.as_view(), name='user-me'),
    path('users/', views.UserList.as_view(), name='user-list'),
    path('users/<int:pk>/', views.UserDetail.as_view(), name='user-detail'),

    # Cluster (user-scoped)
    path('users/<int:pk>/clusters/',
         views.KubeClusterList.as_view(), name='user-cluster-list'),

    # Cluster (cluster-scoped)
    path('clusters/<int:pk>/', views.KubeClusterDetail.as_view(),
         name='cluster-detail'),

    # K8s Resources
    path('clusters/<int:cluster_id>/resources/<str:resource_type>/',
         views.KubeResourceList.as_view(), name='kube-resource-list'),
    path('clusters/<int:cluster_id>/resources/<str:resource_type>/<str:name>/',
         views.KubeResourceDetail.as_view(), name='kube-resource-detail'),

    # Apply YAML
    path('clusters/<int:cluster_id>/apply/',
         views.KubeApply.as_view(), name='kube-apply'),
]
