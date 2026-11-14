from django.middleware.csrf import CsrfViewMiddleware


class DisableCSRFForAPI(CsrfViewMiddleware):
    def process_request(self, request):
        if request.path.startswith('/api/') or request.path.startswith('/auth/'):
            setattr(request, '_dont_enforce_csrf_checks', True)
        return super().process_request(request)
