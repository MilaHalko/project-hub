import re

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

_FORM_OVERHEAD = 1_048_576
_UPLOAD_PATH = re.compile(r"^/project/[^/]+/documents/?$")
_REPLACE_PATH = re.compile(r"^/document/[^/]+/?$")


def _refusal(status_code: int, detail: str) -> JSONResponse:
    return JSONResponse({"detail": detail}, status_code=status_code)


class UploadLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        settings = scope["app"].state.settings
        method: str = scope["method"]
        path: str = scope["path"]
        if method == "POST" and _UPLOAD_PATH.match(path):
            limit = settings.document_max_files * settings.document_max_bytes + _FORM_OVERHEAD
        elif method == "PUT" and _REPLACE_PATH.match(path):
            limit = settings.document_max_bytes + _FORM_OVERHEAD
        else:
            await self.app(scope, receive, send)
            return

        refusal = self._check(scope, limit)
        if refusal is not None:
            await refusal(scope, receive, send)
            return
        await self.app(scope, receive, send)

    @staticmethod
    def _check(scope: Scope, limit: int) -> JSONResponse | None:
        headers: list[tuple[bytes, bytes]] = scope["headers"]
        lengths = [v for k, v in headers if k == b"content-length"]
        if any(k == b"transfer-encoding" for k, _ in headers):
            return _refusal(411, "Content-Length is required")
        if not lengths:
            return _refusal(411, "Content-Length is required")
        if len(lengths) > 1:
            return _refusal(400, "Invalid Content-Length")
        text = lengths[0].decode("latin-1")
        if not (text.isascii() and text.isdigit()):
            return _refusal(400, "Invalid Content-Length")
        length = int(text)
        if length > limit:
            return _refusal(413, "Request is too large")
        return None
