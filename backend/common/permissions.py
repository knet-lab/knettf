from rest_framework.exceptions import PermissionDenied
from . import Request


def check_owner(request: Request, owner_pk: int):
    if request.user.pk != owner_pk:
        raise PermissionDenied()
