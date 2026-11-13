from typing import Annotated

from fastapi import APIRouter, Depends

from project_hub.auth import service
from project_hub.auth.dependencies import get_password_hasher, get_token_service
from project_hub.auth.passwords import PasswordHasher
from project_hub.auth.schemas import LoginRequest, RegisterRequest, TokenResponse
from project_hub.auth.tokens import TokenService
from project_hub.db.dependencies import get_uow
from project_hub.db.uow import UnitOfWork
from project_hub.users.schemas import UserResponse

router = APIRouter(tags=["auth"])


@router.post("/auth", status_code=201)
async def register_user(
    data: RegisterRequest,
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    hasher: Annotated[PasswordHasher, Depends(get_password_hasher)],
) -> UserResponse:
    user = await service.register(uow, hasher, data)
    return UserResponse.from_user(user)


@router.post("/login")
async def log_in(
    data: LoginRequest,
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    hasher: Annotated[PasswordHasher, Depends(get_password_hasher)],
    tokens: Annotated[TokenService, Depends(get_token_service)],
) -> TokenResponse:
    return await service.login(uow, hasher, tokens, data)
