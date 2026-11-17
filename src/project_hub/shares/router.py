from datetime import UTC, datetime
from typing import Annotated
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials

from project_hub.auth.dependencies import (
    CurrentUser,
    bearer_scheme,
    get_current_user,
    get_token_service,
)
from project_hub.auth.tokens import TokenService
from project_hub.core.exceptions import AuthenticationError
from project_hub.db.dependencies import get_uow
from project_hub.db.uow import UnitOfWork
from project_hub.shares import service
from project_hub.shares.dependencies import PublicUrl, ShareMailer
from project_hub.shares.schemas import JoinResponse, ShareEmail, ShareResponse

router = APIRouter(tags=["shares"])


@router.get("/project/{project_id}/share", response_model_exclude_none=True)
async def share_project(
    project_id: UUID,
    user: CurrentUser,
    mailer: ShareMailer,
    public_url: PublicUrl,
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    email: Annotated[ShareEmail, Query(alias="with")],
) -> ShareResponse:
    result = await service.share(
        uow, mailer, public_url, user, project_id, email, now=datetime.now(UTC)
    )
    return ShareResponse.from_result(result)


@router.get("/join", response_model=JoinResponse)
async def join_project(
    request: Request,
    token: Annotated[str, Query(min_length=1, max_length=128)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    tokens: Annotated[TokenService, Depends(get_token_service)],
) -> JoinResponse | RedirectResponse:
    if "authorization" not in request.headers:
        web_url = request.app.state.settings.web_url
        if web_url and "text/html" in request.headers.get("accept", ""):
            return RedirectResponse(
                f"{web_url}/join?{urlencode({'token': token})}", status_code=303
            )
        raise AuthenticationError("Not authenticated")
    user = await get_current_user(credentials, uow, tokens)
    result = await service.join(uow, user, token, now=datetime.now(UTC))
    return JoinResponse.from_result(
        user.login, result, request.app.state.settings.project_max_bytes
    )
