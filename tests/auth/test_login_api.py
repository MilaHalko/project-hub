import jwt
from fastapi.testclient import TestClient
from pydantic import SecretStr

from project_hub.main import create_app
from tests.conftest import TEST_JWT_SECRET
from tests.isolated_settings import IsolatedSettings
from tests.support.auth import login, register
from tests.support.database import truncate_tables


def test_login_returns_bearer_token(api_client: TestClient) -> None:
    register(api_client)
    r = api_client.post("/login", json={"login": "mila", "password": "correct-horse-1"})
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 3600
    assert body["access_token"]


def test_login_token_lasts_exactly_one_hour_and_names_the_user(api_client: TestClient) -> None:
    user_id = register(api_client).json()["id"]
    token = login(api_client)
    claims = jwt.decode(token, TEST_JWT_SECRET, algorithms=["HS256"])  # pyright: ignore[reportUnknownMemberType]
    assert claims["exp"] - claims["iat"] == 3600
    assert claims["sub"] == user_id
    assert claims["ver"] == 0


def test_wrong_password_and_unknown_login_look_the_same(api_client: TestClient) -> None:
    register(api_client)
    wrong_password = api_client.post("/login", json={"login": "mila", "password": "nope-nope-1"})
    unknown_login = api_client.post("/login", json={"login": "ghost", "password": "nope-nope-1"})
    for r in (wrong_password, unknown_login):
        assert r.status_code == 401
        assert r.json() == {"detail": "Invalid login or password"}
        assert r.headers["www-authenticate"] == "Bearer"


def test_login_missing_field_is_422(api_client: TestClient) -> None:
    assert api_client.post("/login", json={"login": "mila"}).status_code == 422


def test_password_is_checked_exactly_as_typed(api_client: TestClient) -> None:
    register(api_client, password="  horse 1234 ")
    ok = api_client.post("/login", json={"login": "mila", "password": "  horse 1234 "})
    assert ok.status_code == 200
    trimmed = api_client.post("/login", json={"login": "mila", "password": "horse 1234"})
    assert trimmed.status_code == 401


def test_login_without_jwt_secret_is_500(migrated_database_url: str) -> None:
    settings = IsolatedSettings(database_url=SecretStr(migrated_database_url))
    assert settings.jwt_secret is None
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        try:
            assert register(client).status_code == 201
            assert client.get("/health").status_code == 200
            r = client.post("/login", json={"login": "mila", "password": "correct-horse-1"})
            assert r.status_code == 500
            assert r.json() == {"detail": "Internal Server Error"}
        finally:
            truncate_tables(migrated_database_url)
