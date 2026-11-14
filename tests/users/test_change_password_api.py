import pytest
from fastapi.testclient import TestClient

from tests.support.auth import bearer, login, register

OLD = "correct-horse-1"
NEW = "battery-staple-2"
LONG_LOGIN = "mila-user-1"  # long enough to also be a valid password


def test_change_password_rotates_token_and_password(api_client: TestClient) -> None:
    register(api_client)
    old_token = login(api_client)

    r = api_client.put(
        "/users/me/password",
        headers=bearer(old_token),
        json={"current_password": OLD, "new_password": NEW, "repeat_new_password": NEW},
    )

    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 3600
    new_token = body["access_token"]
    assert api_client.get("/users/me", headers=bearer(new_token)).status_code == 200
    assert api_client.get("/users/me", headers=bearer(old_token)).status_code == 401
    ok = api_client.post("/login", json={"login": "mila", "password": NEW})
    assert ok.status_code == 200
    bad = api_client.post("/login", json={"login": "mila", "password": OLD})
    assert bad.status_code == 401


def test_wrong_current_password_is_400_and_changes_nothing(api_client: TestClient) -> None:
    register(api_client)
    token = login(api_client)

    r = api_client.put(
        "/users/me/password",
        headers=bearer(token),
        json={
            "current_password": "not-the-password",
            "new_password": NEW,
            "repeat_new_password": NEW,
        },
    )

    assert r.status_code == 400
    assert r.json() == {"detail": "Current password is incorrect"}
    assert api_client.get("/users/me", headers=bearer(token)).status_code == 200
    assert api_client.post("/login", json={"login": "mila", "password": OLD}).status_code == 200
    assert api_client.post("/login", json={"login": "mila", "password": NEW}).status_code == 401


def test_non_english_current_password_is_400_not_422(api_client: TestClient) -> None:
    register(api_client)
    token = login(api_client)
    r = api_client.put(
        "/users/me/password",
        headers=bearer(token),
        json={"current_password": "пароль-12345", "new_password": NEW, "repeat_new_password": NEW},
    )
    assert r.status_code == 400
    assert r.json() == {"detail": "Current password is incorrect"}


@pytest.mark.parametrize(
    ("new", "repeat"),
    [
        pytest.param(NEW, "something-else-3", id="repeat-mismatch"),
        pytest.param(OLD, OLD, id="same-as-current"),
        pytest.param(LONG_LOGIN, LONG_LOGIN, id="equals-login"),
        pytest.param("1234567", "1234567", id="7-chars"),
        pytest.param("x" * 129, "x" * 129, id="129-chars"),
        pytest.param("пароль-12345", "пароль-12345", id="cyrillic"),
    ],
)
def test_change_password_invalid_input_is_422(
    api_client: TestClient, new: str, repeat: str
) -> None:
    register(api_client, login=LONG_LOGIN)
    token = login(api_client, login=LONG_LOGIN)

    r = api_client.put(
        "/users/me/password",
        headers=bearer(token),
        json={"current_password": OLD, "new_password": new, "repeat_new_password": repeat},
    )

    assert r.status_code == 422
    assert new not in r.text
    assert api_client.get("/users/me", headers=bearer(token)).status_code == 200


def test_new_password_equal_to_login_has_a_plain_detail(api_client: TestClient) -> None:
    register(api_client, login=LONG_LOGIN)
    token = login(api_client, login=LONG_LOGIN)

    r = api_client.put(
        "/users/me/password",
        headers=bearer(token),
        json={
            "current_password": OLD,
            "new_password": LONG_LOGIN,
            "repeat_new_password": LONG_LOGIN,
        },
    )

    assert r.status_code == 422
    assert r.json() == {"detail": "Password must not equal the login"}


@pytest.mark.parametrize(
    "headers",
    [
        pytest.param({}, id="no-header"),
        pytest.param(bearer("garbage"), id="garbage-token"),
    ],
)
def test_change_password_without_valid_token_is_401(
    api_client: TestClient, headers: dict[str, str]
) -> None:
    r = api_client.put(
        "/users/me/password",
        headers=headers,
        json={"current_password": OLD, "new_password": NEW, "repeat_new_password": NEW},
    )
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"
