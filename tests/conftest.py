import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from project_hub.main import create_app
from tests.isolated_settings import IsolatedSettings
from tests.support.database import (
    DEFAULT_ADMIN_URL,
    TestDatabaseUnavailableError,
    create_test_database,
    drop_test_database,
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("APP_NAME", "APP_DEBUG"):
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
def client() -> Iterator[TestClient]:
    settings = IsolatedSettings(name="Test Hub")
    with TestClient(create_app(settings)) as c:
        yield c


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    admin_url = os.environ.get("TEST_DATABASE_URL", DEFAULT_ADMIN_URL)
    failure: str | None = None
    url = ""
    try:
        url = create_test_database(admin_url)
    except TestDatabaseUnavailableError as err:
        failure = str(err)
    if failure is not None:
        pytest.fail(failure, pytrace=False)
    try:
        yield url
    finally:
        drop_test_database(admin_url, url)
