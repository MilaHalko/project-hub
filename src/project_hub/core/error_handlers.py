import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from project_hub.core.exceptions import (
    AuthenticationError,
    ConflictError,
    DomainError,
    NotFoundError,
    PermissionDeniedError,
)

logger = logging.getLogger(__name__)

_STATUS_BY_ERROR: dict[type[DomainError], int] = {
    DomainError: 400,
    NotFoundError: 404,
    PermissionDeniedError: 403,
    ConflictError: 409,
    AuthenticationError: 401,
}


def _status_for(exc: DomainError) -> int:
    for cls in type(exc).__mro__:
        if cls in _STATUS_BY_ERROR:
            return _STATUS_BY_ERROR[cls]
    return 400


async def _handle_domain_error(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, DomainError):
        raise exc
    headers = {"WWW-Authenticate": "Bearer"} if isinstance(exc, AuthenticationError) else None
    return JSONResponse(
        status_code=_status_for(exc), content={"detail": exc.message}, headers=headers
    )


async def _handle_unhandled(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, _handle_domain_error)
    app.add_exception_handler(Exception, _handle_unhandled)
