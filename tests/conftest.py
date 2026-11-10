from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from project_hub.main import create_app
from tests.isolated_settings import IsolatedSettings


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("APP_NAME", "APP_DEBUG"):
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
def client() -> Iterator[TestClient]:
    settings = IsolatedSettings(name="Test Hub")
    with TestClient(create_app(settings)) as c:
        yield c
