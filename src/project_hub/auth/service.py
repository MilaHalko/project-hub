from project_hub.auth.passwords import PasswordHasher
from project_hub.auth.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
)
from project_hub.auth.tokens import TOKEN_TTL, TokenService
from project_hub.core.exceptions import (
    AuthenticationError,
    DomainError,
    ValidationFailedError,
)
from project_hub.db.uow import UnitOfWork
from project_hub.users import service as users_service
from project_hub.users.entities import User


async def register(uow: UnitOfWork, hasher: PasswordHasher, data: RegisterRequest) -> User:
    password_hash = await hasher.hash(data.password.get_secret_value())
    user = await users_service.create_user(uow, data.login, password_hash)
    await uow.commit()
    return user


async def login(
    uow: UnitOfWork, hasher: PasswordHasher, tokens: TokenService, data: LoginRequest
) -> TokenResponse:
    user = await users_service.get_user_by_login(uow, data.login)
    password = data.password.get_secret_value()
    if user is None:
        await hasher.verify_dummy(password)
        raise AuthenticationError("Invalid login or password")
    if not await hasher.verify(user.password_hash, password):
        raise AuthenticationError("Invalid login or password")
    return TokenResponse(
        access_token=tokens.issue(user.id, user.token_version),
        expires_in=int(TOKEN_TTL.total_seconds()),
    )


async def logout(uow: UnitOfWork, user: User) -> None:
    """End every session of the user: tokens with the old version are refused from now on."""
    await users_service.revoke_tokens(uow, user.id)
    await uow.commit()


async def change_password(
    uow: UnitOfWork,
    hasher: PasswordHasher,
    tokens: TokenService,
    user: User,
    data: ChangePasswordRequest,
) -> TokenResponse:
    """Replace the password; every older token stops working, a fresh one is returned."""
    if not await hasher.verify(user.password_hash, data.current_password.get_secret_value()):
        raise DomainError("Current password is incorrect")
    new_password = data.new_password.get_secret_value()
    if new_password == user.login:
        raise ValidationFailedError("Password must not equal the login")
    updated = await users_service.set_password(uow, user.id, await hasher.hash(new_password))
    if updated is None:  # the user behind the token was deleted meanwhile
        raise AuthenticationError("Invalid or expired token")
    await uow.commit()
    return TokenResponse(
        access_token=tokens.issue(updated.id, updated.token_version),
        expires_in=int(TOKEN_TTL.total_seconds()),
    )
