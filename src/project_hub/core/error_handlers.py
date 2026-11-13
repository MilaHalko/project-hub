import logging
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from project_hub.core.exceptions import (
    AuthenticationError,
    ConflictError,
    DomainError,
    NotFoundError,
    PermissionDeniedError,
)

logger = logging.getLogger(__name__)

_STATUS_BY_ERROR: dict[type[DomainError], HTTPStatus] = {
    DomainError: HTTPStatus.BAD_REQUEST,
    NotFoundError: HTTPStatus.NOT_FOUND,
    PermissionDeniedError: HTTPStatus.FORBIDDEN,
    ConflictError: HTTPStatus.CONFLICT,
    AuthenticationError: HTTPStatus.UNAUTHORIZED,
}


def _status_for(exc: DomainError) -> HTTPStatus:
    for cls in type(exc).__mro__:
        if cls in _STATUS_BY_ERROR:
            return _STATUS_BY_ERROR[cls]
    return HTTPStatus.BAD_REQUEST


async def _handle_domain_error(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, DomainError):
        raise exc
    headers = {"WWW-Authenticate": "Bearer"} if isinstance(exc, AuthenticationError) else None
    return JSONResponse(
        status_code=_status_for(exc), content={"detail": exc.message}, headers=headers
    )


async def _handle_unhandled(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR, content={"detail": "Internal Server Error"}
    )


async def _handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        raise exc
    # Drop "input" and "ctx" so a rejected password is never echoed back.
    errors = [{k: v for k, v in e.items() if k not in ("input", "ctx")} for e in exc.errors()]
    return JSONResponse(
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        content=jsonable_encoder({"detail": errors}),
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, _handle_domain_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(Exception, _handle_unhandled)
