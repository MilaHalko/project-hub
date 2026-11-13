from fastapi import Request

from project_hub.auth.passwords import PasswordHasher
from project_hub.auth.tokens import TokenService


def get_password_hasher(request: Request) -> PasswordHasher:
    hasher: PasswordHasher = request.app.state.password_hasher
    return hasher


def get_token_service(request: Request) -> TokenService:
    tokens: TokenService | None = request.app.state.token_service
    if tokens is None:
        raise RuntimeError("APP_JWT_SECRET is not set")
    return tokens
