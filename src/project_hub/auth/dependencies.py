from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from project_hub.auth.passwords import PasswordHasher
from project_hub.auth.tokens import TokenService
from project_hub.core.exceptions import AuthenticationError
from project_hub.db.dependencies import get_uow
from project_hub.db.uow import UnitOfWork
from project_hub.users import service as users_service
from project_hub.users.entities import User

# auto_error=False: a missing header gives our own 401 (with the same error body as other 401s).
bearer_scheme = HTTPBearer(auto_error=False)


def get_password_hasher(request: Request) -> PasswordHasher:
    hasher: PasswordHasher = request.app.state.password_hasher
    return hasher


def get_token_service(request: Request) -> TokenService:
    tokens: TokenService | None = request.app.state.token_service
    if tokens is None:
        raise RuntimeError("APP_JWT_SECRET is not set")
    return tokens


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    tokens: Annotated[TokenService, Depends(get_token_service)],
) -> User:
    if credentials is None:
        raise AuthenticationError("Not authenticated")
    claims = tokens.decode(credentials.credentials)
    user = await users_service.get_user(uow, claims.user_id)
    if user is None:
        raise AuthenticationError("Invalid or expired token")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
