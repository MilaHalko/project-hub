from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt

TOKEN_TTL = timedelta(hours=1)
ALGORITHM = "HS256"


def _utc_now() -> datetime:
    return datetime.now(UTC)


class TokenService:
    def __init__(self, secret: str, *, clock: Callable[[], datetime] = _utc_now) -> None:
        self._secret = secret
        self._clock = clock

    def issue(self, user_id: UUID) -> str:
        issued_at = int(self._clock().timestamp())
        claims = {
            "sub": str(user_id),
            "iat": issued_at,
            "exp": issued_at + int(TOKEN_TTL.total_seconds()),
        }
        return jwt.encode(claims, self._secret, algorithm=ALGORITHM)  # pyright: ignore[reportUnknownMemberType]
