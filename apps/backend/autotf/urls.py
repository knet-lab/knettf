from django.urls import path
from . import views

urlpatterns = [
    # Config (user-scoped)
    path('users/<int:user_pk>/tf-configs/',
         views.TerraformConfigList.as_view(), name='tf-config-list'),
    path('users/<int:user_pk>/tf-configs/text/',
         views.TerraformConfigTextCreate.as_view(), name='tf-config-text-create'),

    # Config (config-scoped)
    path('tf-configs/<int:config_pk>/',
         views.TerraformConfigDetail.as_view(), name='tf-config-detail'),
    path('tf-configs/<int:config_pk>/content/',
         views.TerraformConfigContent.as_view(), name='tf-config-content'),
    path('tf-configs/<int:config_pk>/scan/',
         views.TerraformConfigFullScan.as_view(), name='tf-config-scan-full'),
    path('tf-configs/<int:config_pk>/scan/manual/',
         views.TerraformConfigManualScan.as_view(), name='tf-config-scan-manual'),
    path('tf-configs/<int:config_pk>/apply/',
         views.TerraformConfigApply.as_view(), name='tf-config-apply'),
    path('tf-configs/<int:config_pk>/report/',
         views.ScanReportDetail.as_view(), name='tf-config-report'),

    # Tools (global, admin-managed)
    path('tf-tools/',
         views.TerraformToolList.as_view(), name='tf-tool-list'),
    path('tf-tools/<int:tool_id>/',
         views.TerraformToolDetail.as_view(), name='tf-tool-detail'),

    # Report HTML / PDF (token via query param)
    path('tf-configs/<int:config_pk>/report/html/',
         views.ScanReportHTMLView.as_view(), name='tf-config-report-html'),
    path('tf-configs/<int:config_pk>/report/pdf/',
         views.ScanReportPDFView.as_view(), name='tf-config-report-pdf'),
]
