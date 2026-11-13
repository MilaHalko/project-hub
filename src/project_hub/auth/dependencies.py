from fastapi import Request

from project_hub.auth.passwords import PasswordHasher


def get_password_hasher(request: Request) -> PasswordHasher:
    hasher: PasswordHasher = request.app.state.password_hasher
    return hasher
