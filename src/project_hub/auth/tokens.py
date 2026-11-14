from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt

from project_hub.core.exceptions import AuthenticationError

TOKEN_TTL = timedelta(hours=1)
ALGORITHM = "HS256"


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class TokenClaims:
    user_id: UUID
    token_version: int


class TokenService:
    def __init__(self, secret: str, *, clock: Callable[[], datetime] = _utc_now) -> None:
        self._secret = secret
        self._clock = clock

    def issue(self, user_id: UUID, token_version: int) -> str:
        issued_at = int(self._clock().timestamp())
        claims = {
            "sub": str(user_id),
            "ver": token_version,
            "iat": issued_at,
            "exp": issued_at + int(TOKEN_TTL.total_seconds()),
        }
        return jwt.encode(claims, self._secret, algorithm=ALGORITHM)  # pyright: ignore[reportUnknownMemberType]

    def decode(self, token: str) -> TokenClaims:
        try:
            claims = jwt.decode(  # pyright: ignore[reportUnknownMemberType]
                token,
                self._secret,
                algorithms=[ALGORITHM],
                options={"require": ["exp", "iat", "sub", "ver"]},
            )
            version = claims["ver"]
            # bool is a subclass of int, so `true` must be rejected explicitly.
            if not isinstance(version, int) or isinstance(version, bool):
                raise ValueError("ver must be an integer")
            return TokenClaims(user_id=UUID(str(claims["sub"])), token_version=version)
        except (jwt.InvalidTokenError, ValueError):
            raise AuthenticationError("Invalid or expired token") from None
