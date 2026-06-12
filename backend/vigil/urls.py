from django.urls import path
from . import views

urlpatterns = [
    path("detect/", views.DetectView.as_view(), name="vigil-detect"),
    path("detect/batch/", views.DetectBatchView.as_view(), name="vigil-detect-batch"),
    path("records/", views.RecordsView.as_view(), name="vigil-records"),
    path("stats/", views.StatsView.as_view(), name="vigil-stats"),
    path("models/", views.ModelsView.as_view(), name="vigil-models"),
]
