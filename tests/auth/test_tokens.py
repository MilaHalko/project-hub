import base64
import json
import warnings
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import jwt
import pytest

from project_hub.auth.tokens import TokenClaims, TokenService
from project_hub.core.exceptions import AuthenticationError
from tests.conftest import TEST_JWT_SECRET


def test_issue_sets_sub_iat_and_exp_one_hour_later() -> None:
    fixed = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)
    user_id = uuid4()
    token = TokenService(TEST_JWT_SECRET, clock=lambda: fixed).issue(user_id, token_version=0)

    # PyJWT leaves its key type partly unknown without the optional cryptography package.
    claims = jwt.decode(  # pyright: ignore[reportUnknownMemberType]
        token, TEST_JWT_SECRET, algorithms=["HS256"], options={"verify_exp": False}
    )
    assert claims["sub"] == str(user_id)
    assert claims["iat"] == int(fixed.timestamp())
    assert claims["exp"] - claims["iat"] == 3600
    assert jwt.get_unverified_header(token)["alg"] == "HS256"


S = "a" * 32


def _b64(data: dict[str, Any]) -> str:
    raw = json.dumps(data, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _encode(claims: dict[str, Any], secret: str = S, algorithm: str = "HS256") -> str:
    with warnings.catch_warnings():
        # A 32-byte key is short for HS512; that is the point of the test, so silence the warning.
        warnings.simplefilter("ignore", jwt.warnings.InsecureKeyLengthWarning)
        return jwt.encode(claims, secret, algorithm=algorithm)  # pyright: ignore[reportUnknownMemberType]


def _good_claims(**overrides: Any) -> dict[str, Any]:
    now = int(datetime.now(UTC).timestamp())
    claims: dict[str, Any] = {"sub": str(uuid4()), "ver": 0, "iat": now, "exp": now + 3600}
    claims.update(overrides)
    return claims


def _issue_at(age: timedelta, user_id: Any = None) -> str:
    now = datetime.now(UTC)
    return TokenService(S, clock=lambda: now - age).issue(user_id or uuid4(), token_version=0)


def test_decode_returns_claims_of_issued_token() -> None:
    user_id = uuid4()
    service = TokenService(S)
    assert service.decode(service.issue(user_id, token_version=0)) == TokenClaims(
        user_id=user_id, token_version=0
    )


def test_ver_round_trips_through_issue_and_decode() -> None:
    user_id = uuid4()
    service = TokenService(S)
    token = service.issue(user_id, token_version=7)

    claims = jwt.decode(token, S, algorithms=["HS256"])  # pyright: ignore[reportUnknownMemberType]
    assert claims["ver"] == 7
    assert service.decode(token) == TokenClaims(user_id=user_id, token_version=7)


def test_decode_rejects_expired_token() -> None:
    with pytest.raises(AuthenticationError, match="Invalid or expired token"):
        TokenService(S).decode(_issue_at(timedelta(seconds=3600)))


def test_decode_accepts_token_just_before_expiry() -> None:
    user_id = uuid4()
    assert TokenService(S).decode(_issue_at(timedelta(seconds=3590), user_id)).user_id == user_id


def _alg_none_token() -> str:
    return f"{_b64({'alg': 'none', 'typ': 'JWT'})}.{_b64(_good_claims())}."


def _payload_swapped_token() -> str:
    header, _, signature = _encode(_good_claims()).split(".")
    return f"{header}.{_b64(_good_claims())}.{signature}"


@pytest.mark.parametrize(
    "token",
    [
        pytest.param(_encode(_good_claims(), secret="b" * 32), id="wrong-secret"),
        pytest.param(_encode(_good_claims(), algorithm="HS512"), id="hs512"),
        pytest.param(_alg_none_token(), id="alg-none"),
        pytest.param(_payload_swapped_token(), id="modified-payload"),
        pytest.param("garbage", id="garbage"),
    ],
)
def test_decode_rejects_tampering(token: str) -> None:
    with pytest.raises(AuthenticationError, match="Invalid or expired token"):
        TokenService(S).decode(token)


def _without(key: str) -> dict[str, Any]:
    claims = _good_claims()
    del claims[key]
    return claims


@pytest.mark.parametrize(
    "claims",
    [
        pytest.param(_without("exp"), id="no-exp"),
        pytest.param(_without("iat"), id="no-iat"),
        pytest.param(_without("sub"), id="no-sub"),
        pytest.param(_good_claims(sub="not-a-uuid"), id="sub-not-uuid"),
        pytest.param(_without("ver"), id="no-ver"),
        pytest.param(_good_claims(ver="0"), id="ver-string"),
        pytest.param(_good_claims(ver=True), id="ver-bool"),
    ],
)
def test_decode_requires_claims(claims: dict[str, Any]) -> None:
    with pytest.raises(AuthenticationError, match="Invalid or expired token"):
        TokenService(S).decode(_encode(claims))
