from project_hub.auth.passwords import PasswordHasher
from project_hub.auth.schemas import LoginRequest, RegisterRequest, TokenResponse
from project_hub.auth.tokens import TOKEN_TTL, TokenService
from project_hub.core.exceptions import AuthenticationError
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
        access_token=tokens.issue(user.id), expires_in=int(TOKEN_TTL.total_seconds())
    )
