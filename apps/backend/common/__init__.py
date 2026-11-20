from typing import TYPE_CHECKING

from rest_framework.request import Request

if TYPE_CHECKING:
    # 只给类型检查器看：接口默认要求登录（settings.REST_FRAMEWORK 的 IsAuthenticated），
    # 视图里的 request.user 就是 kcore.User。运行时仍是 DRF 的 Request，行为不变。
    from kcore.models import User

    class Request(Request):  # type: ignore[no-redef]
        @property
        def user(self) -> User: ...  # pyright: ignore[reportIncompatibleMethodOverride]


__all__ = ['Request']
