import base64
import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi.testclient import TestClient

from project_hub.auth.tokens import TokenService
from tests.conftest import TEST_JWT_SECRET
from tests.support.auth import bearer, login, register


def _encode(claims: dict[str, Any], secret: str = TEST_JWT_SECRET) -> str:
    return jwt.encode(claims, secret, algorithm="HS256")  # pyright: ignore[reportUnknownMemberType]


def _b64(data: dict[str, Any]) -> str:
    raw = json.dumps(data, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def test_me_returns_current_user(api_client: TestClient) -> None:
    registered = register(api_client)
    token = login(api_client)
    r = api_client.get("/users/me", headers=bearer(token))
    assert r.status_code == 200
    assert r.json() == registered.json()
    assert "password" not in r.text


def test_token_expiry_boundary(api_client: TestClient) -> None:
    user_id = register(api_client).json()["id"]
    now = datetime.now(UTC)

    def token_aged(seconds: int) -> str:
        service = TokenService(TEST_JWT_SECRET, clock=lambda: now - timedelta(seconds=seconds))
        return service.issue(UUID(user_id))

    assert api_client.get("/users/me", headers=bearer(token_aged(3590))).status_code == 200
    assert api_client.get("/users/me", headers=bearer(token_aged(3600))).status_code == 401


@pytest.mark.parametrize(
    "headers",
    [
        pytest.param({}, id="no-header"),
        pytest.param({"Authorization": "Basic bWlsYTp4"}, id="basic-scheme"),
        pytest.param({"Authorization": "Bearer"}, id="bearer-without-token"),
        pytest.param({"Authorization": "Bearer garbage"}, id="garbage-token"),
    ],
)
def test_missing_or_malformed_auth_is_401(api_client: TestClient, headers: dict[str, str]) -> None:
    r = api_client.get("/users/me", headers=headers)
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"


def _good_claims(user_id: str, **overrides: Any) -> dict[str, Any]:
    now = int(datetime.now(UTC).timestamp())
    claims: dict[str, Any] = {"sub": user_id, "iat": now, "exp": now + 3600}
    claims.update(overrides)
    return claims


def test_forged_tokens_are_401(api_client: TestClient) -> None:
    user_id = register(api_client).json()["id"]
    claims = _good_claims(user_id)
    wrong_secret = _encode(claims, secret="b" * 32)
    alg_none = f"{_b64({'alg': 'none', 'typ': 'JWT'})}.{_b64(claims)}."
    for token in (wrong_secret, alg_none):
        r = api_client.get("/users/me", headers=bearer(token))
        assert r.status_code == 401


def test_token_without_required_claims_is_401(api_client: TestClient) -> None:
    user_id = register(api_client).json()["id"]
    no_exp = _good_claims(user_id)
    del no_exp["exp"]
    no_sub = _good_claims(user_id)
    del no_sub["sub"]
    for claims in (no_exp, no_sub, _good_claims("nope")):
        r = api_client.get("/users/me", headers=bearer(_encode(claims)))
        assert r.status_code == 401


def test_token_for_missing_user_is_401(api_client: TestClient) -> None:
    token = TokenService(TEST_JWT_SECRET).issue(uuid4())
    r = api_client.get("/users/me", headers=bearer(token))
    assert r.status_code == 401
    assert r.json() == {"detail": "Invalid or expired token"}


def test_lowercase_bearer_scheme_works(api_client: TestClient) -> None:
    register(api_client)
    token = login(api_client)
    r = api_client.get("/users/me", headers={"Authorization": f"bearer {token}"})
    assert r.status_code == 200
