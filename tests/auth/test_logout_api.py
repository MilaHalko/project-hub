import pytest
from fastapi.testclient import TestClient

from tests.support.auth import bearer, login, register


def test_logout_revokes_token(api_client: TestClient) -> None:
    register(api_client)
    token = login(api_client)
    assert api_client.get("/users/me", headers=bearer(token)).status_code == 200

    r = api_client.post("/logout", headers=bearer(token))

    assert r.status_code == 204
    assert r.content == b""
    after = api_client.get("/users/me", headers=bearer(token))
    assert after.status_code == 401
    assert after.json() == {"detail": "Invalid or expired token"}


def test_logout_revokes_every_token_of_the_user(api_client: TestClient) -> None:
    register(api_client)
    first = login(api_client)
    second = login(api_client)

    assert api_client.post("/logout", headers=bearer(first)).status_code == 204

    assert api_client.get("/users/me", headers=bearer(first)).status_code == 401
    assert api_client.get("/users/me", headers=bearer(second)).status_code == 401
    third = login(api_client)
    assert api_client.get("/users/me", headers=bearer(third)).status_code == 200


def test_logout_leaves_other_users_logged_in(api_client: TestClient) -> None:
    register(api_client, login="mila")
    register(api_client, login="anna")
    mila = login(api_client, login="mila")
    anna = login(api_client, login="anna")

    assert api_client.post("/logout", headers=bearer(mila)).status_code == 204

    assert api_client.get("/users/me", headers=bearer(anna)).status_code == 200


@pytest.mark.parametrize(
    "headers",
    [
        pytest.param({}, id="no-header"),
        pytest.param(bearer("garbage"), id="garbage-token"),
    ],
)
def test_logout_without_valid_token_is_401(api_client: TestClient, headers: dict[str, str]) -> None:
    r = api_client.post("/logout", headers=headers)
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"


def test_logout_twice_is_401_not_500(api_client: TestClient) -> None:
    register(api_client)
    token = login(api_client)
    assert api_client.post("/logout", headers=bearer(token)).status_code == 204

    r = api_client.post("/logout", headers=bearer(token))

    assert r.status_code == 401
    assert r.json() == {"detail": "Invalid or expired token"}
