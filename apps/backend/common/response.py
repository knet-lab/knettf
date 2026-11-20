from typing import Any

from rest_framework.response import Response


"""
# No problem
200:  { "status": "success", "data": {...}, "code": 0, "message": "Success" }
201:  { "status": "success", "data": {...}, "code": 0, "message": "Created" }

# Request error
400:  { "status": "error", "message": "Bad Request", "code": 1 }
401:  { "status": "error", "message": "Unauthorized", "code": 1 }
403:  { "status": "error", "message": "Forbidden", "code": 1 }
404:  { "status": "error", "message": "Not Found", "code": 1 }

# Server error
500:  { "status": "error", "message": "Internal Server Error", "code": 2 }

"""


class ApiResponse(Response):
    """统一格式的响应：{status, code, message, data}。"""

    def __init__(self, data: Any = None, status: int | None = None,
                 message: str | None = None, code: int | None = None):
        base_data = {
            'status': 'success' if code == 0 else 'error',
            'code': code,
            'message': message,
            'data': data,
        }
        super().__init__(data=base_data, status=status)


class ResponseMixin:
    """视图用的辅助方法（与 APIView 一起继承）。只提供方法，本身不是响应对象。"""

    def success_response(self, data: Any = None, status: int = 200) -> ApiResponse:
        return ApiResponse(data=data, status=status, code=0, message='Success')

    def created_response(self, data: Any = None, status: int = 201) -> ApiResponse:
        return ApiResponse(data=data, status=status, code=0, message='Created')

    def bad_request_response(self, message: str = 'Bad Request', status: int = 400) -> ApiResponse:
        return ApiResponse(data=None, status=status, message=message, code=1)

    def unauthorized_response(self, message: str = 'Unauthorized', status: int = 401) -> ApiResponse:
        return ApiResponse(data=None, status=status, message=message, code=1)

    def forbidden_response(self, message: str = 'Forbidden', status: int = 403) -> ApiResponse:
        return ApiResponse(data=None, status=status, message=message, code=1)

    def not_found_response(self, message: str = 'Not Found', status: int = 404) -> ApiResponse:
        return ApiResponse(data=None, status=status, message=message, code=1)

    def error_response(self, message: str, status: int = 400, data: Any = None) -> ApiResponse:
        return ApiResponse(data=data, status=status, message=message, code=1)

    def server_error_response(self, message: str = 'Internal Server Error', status: int = 500) -> ApiResponse:
        return ApiResponse(data=None, status=status, message=message, code=2)
