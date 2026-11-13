from datetime import UTC, datetime
from uuid import uuid4

import jwt

from project_hub.auth.tokens import TokenService
from tests.conftest import TEST_JWT_SECRET


def test_issue_sets_sub_iat_and_exp_one_hour_later() -> None:
    fixed = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)
    user_id = uuid4()
    token = TokenService(TEST_JWT_SECRET, clock=lambda: fixed).issue(user_id)

    # PyJWT leaves its key type partly unknown without the optional cryptography package.
    claims = jwt.decode(  # pyright: ignore[reportUnknownMemberType]
        token, TEST_JWT_SECRET, algorithms=["HS256"], options={"verify_exp": False}
    )
    assert claims["sub"] == str(user_id)
    assert claims["iat"] == int(fixed.timestamp())
    assert claims["exp"] - claims["iat"] == 3600
    assert jwt.get_unverified_header(token)["alg"] == "HS256"
