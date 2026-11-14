from rest_framework.views import exception_handler as drf_exception_handler
from common.response import ResponseMixin
def exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is not None:
        return ResponseMixin(data=None, status=response.status_code, message=str(exc.detail) if hasattr(exc, 'detail') else str(exc), code=1 if response.status_code < 500 else 2)
    else:
        return response