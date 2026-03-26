from rest_framework.response import Response


"""
# No problem
200:  { "status": "success", "data": {...}, "code": 0 }
201:  { "status": "success", "data": {...}, "code": 0 }

# Request error
400:  { "status": "error", "message": "Bad Request", "code": 1 }
401:  { "status": "error", "message": "Unauthorized", "code": 1 }
403:  { "status": "error", "message": "Forbidden", "code": 1 }
404:  { "status": "error", "message": "Not Found", "code": 1 }

# Server error
500:  { "status": "error", "message": "Internal Server Error", "code": 2 }

"""


class ResponseMixin(Response):
    def __init__(self, data: dict = None, status: int = None, message: str = None, code: int = None):
        if data is not None:
            data = {
                'status': 'success' if status in range(200, 300) else 'error',
                'data': data
            }
        self.message = message
        self.code = code
        super().__init__(data=data, status=status)