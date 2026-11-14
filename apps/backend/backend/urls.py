from django.contrib import admin
from django.urls import path, include, re_path
from django.http import FileResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from pathlib import Path

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / 'frontend' / 'dist'


def spa_view(request, *args, **kwargs):
    return FileResponse(open(FRONTEND_DIR / 'index.html', 'rb'), content_type='text/html')


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/kcore/', include('kcore.urls')),
    path('api/autotf/', include('autotf.urls')),
    path('api/vigil/', include('vigil.urls')),
    path('api/auth/token/', csrf_exempt(TokenObtainPairView.as_view()), name='token-obtain'),
    path('api/auth/token/refresh/', csrf_exempt(TokenRefreshView.as_view()), name='token-refresh'),
    re_path(r'^(?!api/|admin/|static/|ws/).*$', spa_view),
]
