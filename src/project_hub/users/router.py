from typing import Annotated

from fastapi import APIRouter, Depends

from project_hub.auth import service as auth_service
from project_hub.auth.dependencies import CurrentUser, get_password_hasher, get_token_service
from project_hub.auth.passwords import PasswordHasher
from project_hub.auth.schemas import ChangePasswordRequest, TokenResponse
from project_hub.auth.tokens import TokenService
from project_hub.db.dependencies import get_uow
from project_hub.db.uow import UnitOfWork
from project_hub.users.schemas import UserResponse

router = APIRouter(tags=["users"])


@router.get("/users/me")
async def read_me(user: CurrentUser) -> UserResponse:
    return UserResponse.from_user(user)


@router.put("/users/me/password")
async def change_password(
    data: ChangePasswordRequest,
    user: CurrentUser,
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    hasher: Annotated[PasswordHasher, Depends(get_password_hasher)],
    tokens: Annotated[TokenService, Depends(get_token_service)],
) -> TokenResponse:
    return await auth_service.change_password(uow, hasher, tokens, user, data)
