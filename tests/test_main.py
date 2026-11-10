from fastapi.testclient import TestClient

from project_hub.core.config import Settings
from project_hub.main import create_app


def test_create_app_uses_settings_name() -> None:
    settings = Settings(_env_file=None, name="x")  # pyright: ignore[reportCallIssue]
    assert create_app(settings).title == "x"


def test_unknown_path_returns_json_404(client: TestClient) -> None:
    r = client.get("/does-not-exist")
    assert r.status_code == 404
    assert r.headers["content-type"] == "application/json"
    assert r.json() == {"detail": "Not Found"}


def test_module_app_exposes_health() -> None:
    from project_hub.main import app

    assert TestClient(app).get("/health").status_code == 200
