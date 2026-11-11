import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from project_hub.core.config import Settings
from project_hub.db.uow import UnitOfWork
from project_hub.main import create_app
from tests.isolated_settings import IsolatedSettings


def test_create_app_uses_settings_name() -> None:
    settings = IsolatedSettings(name="x")
    assert create_app(settings).title == "x"


def test_unknown_path_returns_json_404(client: TestClient) -> None:
    r = client.get("/does-not-exist")
    assert r.status_code == 404
    assert r.headers["content-type"] == "application/json"
    assert r.json() == {"detail": "Not Found"}


def test_module_app_exposes_health() -> None:
    from project_hub.main import app

    with TestClient(app) as client:
        assert client.get("/health").status_code == 200


def test_app_without_database_url_serves_health() -> None:
    app = create_app(IsolatedSettings())
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert app.state.database is None


def test_lifespan_opens_and_closes_database(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeDatabase:
        def __init__(self) -> None:
            self.opened = False
            self.closed = False

        def unit_of_work(self) -> UnitOfWork:
            raise NotImplementedError

        async def open(self) -> None:
            self.opened = True

        async def close(self) -> None:
            self.closed = True

    fake = FakeDatabase()

    def fake_create_database(_settings: Settings) -> FakeDatabase:
        return fake

    monkeypatch.setattr("project_hub.main.create_database", fake_create_database)
    settings = IsolatedSettings(database_url=SecretStr("postgresql://u:p@localhost:1/db"))
    app = create_app(settings)

    with TestClient(app):
        assert fake.opened
        assert not fake.closed
        assert app.state.database is fake

    assert fake.closed
