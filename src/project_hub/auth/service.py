import logging
from uuid import UUID

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

logger = logging.getLogger(__name__)


def _log_event(event: str, login: str, user_id: UUID | None = None) -> None:
    """One INFO record per security event; never a password, hash or token.

    `%r` escapes control characters in the login, so it cannot forge extra log lines.
    """
    extra: dict[str, object] = {"event": event, "login": login}
    if user_id is not None:
        extra["user_id"] = user_id
    logger.info(
        "%s login=%r user_id=%s", event, login, user_id if user_id is not None else "-", extra=extra
    )


async def register(uow: UnitOfWork, hasher: PasswordHasher, data: RegisterRequest) -> User:
    password_hash = await hasher.hash(data.password.get_secret_value())
    user = await users_service.create_user(uow, data.login, password_hash)
    await uow.commit()
    _log_event("user registered", user.login, user.id)
    return user


def _mask(login: str) -> str:
    return login[:2] + "***"


async def login(
    uow: UnitOfWork, hasher: PasswordHasher, tokens: TokenService, data: LoginRequest
) -> TokenResponse:
    user = await users_service.get_user_by_login(uow, data.login)
    password = data.password.get_secret_value()
    if user is None:
        await hasher.verify_dummy(password)
        _log_event("login failed", _mask(data.login))
        raise AuthenticationError("Invalid login or password")
    if not await hasher.verify(user.password_hash, password):
        _log_event("login failed", data.login, user.id)
        raise AuthenticationError("Invalid login or password")
    _log_event("login succeeded", user.login, user.id)
    return TokenResponse(
        access_token=tokens.issue(user.id, user.token_version),
        expires_in=int(TOKEN_TTL.total_seconds()),
    )


async def logout(uow: UnitOfWork, user: User) -> None:
    await users_service.revoke_tokens(uow, user.id)
    await uow.commit()
    _log_event("logout", user.login, user.id)


async def change_password(
    uow: UnitOfWork,
    hasher: PasswordHasher,
    tokens: TokenService,
    user: User,
    data: ChangePasswordRequest,
) -> TokenResponse:
    if not await hasher.verify(user.password_hash, data.current_password.get_secret_value()):
        raise DomainError("Current password is incorrect")
    new_password = data.new_password.get_secret_value()
    if new_password == user.login:
        raise ValidationFailedError("Password must not equal the login")
    updated = await users_service.set_password(uow, user.id, await hasher.hash(new_password))
    if updated is None:  # the user behind the token was deleted meanwhile
        raise AuthenticationError("Invalid or expired token")
    await uow.commit()
    _log_event("password changed", updated.login, updated.id)
    return TokenResponse(
        access_token=tokens.issue(updated.id, updated.token_version),
        expires_in=int(TOKEN_TTL.total_seconds()),
    )
