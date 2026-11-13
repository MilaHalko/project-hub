import os
from collections.abc import AsyncIterator, Iterator

import argon2
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from project_hub.auth.passwords import PasswordHasher
from project_hub.db.database import Database
from project_hub.db.migrate import upgrade
from project_hub.db.orm import OrmDatabase
from project_hub.db.sql import SqlDatabase
from project_hub.main import create_app
from tests.isolated_settings import IsolatedSettings
from tests.support.database import (
    DEFAULT_ADMIN_URL,
    TestDatabaseConfigError,
    TestDatabaseUnavailableError,
    create_test_database,
    drop_test_database,
    truncate_tables,
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("APP_NAME", "APP_DEBUG", "APP_DB_BACKEND", "APP_DATABASE_URL"):
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
    except (TestDatabaseUnavailableError, TestDatabaseConfigError) as err:
        failure = str(err)
    if failure is not None:
        pytest.fail(failure, pytrace=False)
    try:
        yield url
    finally:
        drop_test_database(admin_url, url)


@pytest.fixture(scope="session")
def migrated_database_url(database_url: str) -> str:
    upgrade(database_url)
    return database_url


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _build_database(backend: str, url: str) -> Database:
    """Build the `Database` for one backend name; add new backends here."""
    if backend == "orm":
        return OrmDatabase(url)
    if backend == "sql":
        return SqlDatabase(url)
    raise ValueError(f"unknown database backend: {backend!r}")


@pytest.fixture(params=["orm", "sql"], ids=["orm", "sql"])
async def database(
    request: pytest.FixtureRequest, migrated_database_url: str
) -> AsyncIterator[Database]:
    db = _build_database(request.param, migrated_database_url)
    await db.open()
    try:
        yield db
    finally:
        try:
            await db.close()
        finally:
            truncate_tables(migrated_database_url)


@pytest.fixture(params=["orm", "sql"], ids=["orm", "sql"])
def api_client(request: pytest.FixtureRequest, migrated_database_url: str) -> Iterator[TestClient]:
    settings = IsolatedSettings(
        db_backend=request.param, database_url=SecretStr(migrated_database_url)
    )
    app = create_app(settings)
    # Cheapest Argon2 parameters keep the tests fast; never use them outside tests.
    app.state.password_hasher = PasswordHasher(
        argon2.PasswordHasher.from_parameters(argon2.profiles.CHEAPEST)
    )
    try:
        with TestClient(app) as c:
            yield c
    finally:
        truncate_tables(migrated_database_url)
