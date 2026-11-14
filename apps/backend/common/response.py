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


class ResponseMixin(Response):
    def __init__(self, data = None, status: int = None, message: str = None, code: int = None):
        base_data = {
            'status': 'success' if code == 0 else 'error',
            'code': code,
            'message': message,
            'data': data,
        }
        super().__init__(data=base_data, status=status)



    def success_response(self, data: dict = None, status: int = 200):
        return ResponseMixin(data=data, status=status, code=0, message='Success')


    def created_response(self, data: dict = None, status: int = 201):
        return ResponseMixin(data=data, status=status, code=0, message='Created')
    

    def bad_request_response(self, message: str = 'Bad Request', status: int = 400):
        return ResponseMixin(data=None, status=status, message=message, code=1)
    
    def unauthorized_response(self, message: str = 'Unauthorized', status: int = 401):
        return ResponseMixin(data=None, status=status, message=message, code=1)
    
    def forbidden_response(self, message: str = 'Forbidden', status: int = 403):
        return ResponseMixin(data=None, status=status, message=message, code=1)

    def not_found_response(self, message: str = 'Not Found', status: int = 404):
        return ResponseMixin(data=None, status=status, message=message, code=1)

    def error_response(self, message: str, status: int = 400, data: dict = None):
        return ResponseMixin(data=data, status=status, message=message, code=1)

    def server_error_response(self, message: str = 'Internal Server Error', status: int = 500):
        return ResponseMixin(data=None, status=status, message=message, code=2)