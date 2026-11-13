import argon2
import psycopg
import pytest
from fastapi.testclient import TestClient

from tests.support.auth import register


def test_register_returns_201_with_public_fields(api_client: TestClient) -> None:
    r = register(api_client)
    assert r.status_code == 201
    body = r.json()
    assert set(body) == {"id", "login", "created_at"}
    assert body["login"] == "mila"
    assert "correct-horse-1" not in r.text
    assert "argon2" not in r.text


def test_register_stores_argon2_hash(api_client: TestClient, migrated_database_url: str) -> None:
    register(api_client)
    with psycopg.connect(migrated_database_url) as conn:
        row = conn.execute("SELECT password_hash FROM users WHERE login = 'mila'").fetchone()
    assert row is not None
    stored = str(row[0])
    assert stored.startswith("$argon2id$")
    assert stored != "correct-horse-1"
    assert argon2.PasswordHasher().verify(stored, "correct-horse-1") is True


def test_register_duplicate_login_is_409(api_client: TestClient) -> None:
    register(api_client)
    r = register(api_client)
    assert r.status_code == 409
    assert r.json() == {"detail": "Login 'mila' is already taken"}


def test_register_password_mismatch_is_422_and_creates_nothing(
    api_client: TestClient, migrated_database_url: str
) -> None:
    r = api_client.post(
        "/auth",
        json={"login": "mila", "password": "correct-horse-1", "repeat_password": "other-horse-12"},
    )
    assert r.status_code == 422
    assert "Passwords do not match" in r.text
    with psycopg.connect(migrated_database_url) as conn:
        row = conn.execute("SELECT count(*) FROM users").fetchone()
    assert row is not None
    assert row[0] == 0


@pytest.mark.parametrize("login", ["ab", "a" * 33, "mi la", "mila ", "mila\n", "мила", "mila!"])
def test_register_rejects_bad_login(api_client: TestClient, login: str) -> None:
    assert register(api_client, login=login).status_code == 422


@pytest.mark.parametrize("password", ["short1!", "x" * 129])
def test_register_rejects_bad_password_without_echoing_it(
    api_client: TestClient, password: str
) -> None:
    r = register(api_client, password=password)
    assert r.status_code == 422
    assert password not in r.text


@pytest.mark.parametrize(
    "password",
    [
        pytest.param("пароль-12345", id="cyrillic"),
        pytest.param("café-horse-1", id="accented-latin"),
        pytest.param("horse-\U0001f434-123", id="emoji"),
        pytest.param("correct\thorse1", id="tab"),
        pytest.param("correct\nhorse1", id="newline"),
    ],
)
def test_register_rejects_non_english_password(api_client: TestClient, password: str) -> None:
    r = register(api_client, password=password)
    assert r.status_code == 422
    assert "English letters" in r.text
    assert password not in r.text


def test_register_accepts_every_keyboard_symbol_and_space(api_client: TestClient) -> None:
    password = "Aa1 !\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~"
    assert register(api_client, password=password).status_code == 201
    r = api_client.post("/login", json={"login": "mila", "password": password})
    assert r.status_code == 200


def test_register_password_equal_to_login_is_422(api_client: TestClient) -> None:
    assert register(api_client, login="mila_long", password="mila_long").status_code == 422


def test_register_missing_field_or_not_json_is_422(api_client: TestClient) -> None:
    r = api_client.post("/auth", json={"login": "mila", "password": "correct-horse-1"})
    assert r.status_code == 422
    r = api_client.post("/auth", content="not json", headers={"Content-Type": "application/json"})
    assert r.status_code == 422


def test_register_wrong_types_is_422(api_client: TestClient) -> None:
    r = api_client.post(
        "/auth", json={"login": "mila", "password": 12345678, "repeat_password": 12345678}
    )
    assert r.status_code == 422
    r = api_client.post(
        "/auth",
        json={
            "login": "mila",
            "password": "correct-horse-1",
            "repeat_password": "correct-horse-1",
            "admin": True,
        },
    )
    assert r.status_code == 201
