from collections.abc import Iterator
from typing import Annotated, Literal

import psycopg
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from project_hub.db.dependencies import get_uow
from project_hub.db.uow import UnitOfWork
from project_hub.main import create_app
from project_hub.users.entities import NewUser
from tests.isolated_settings import IsolatedSettings
from tests.support.database import truncate_tables


@pytest.fixture
def clean_tables(migrated_database_url: str) -> Iterator[None]:
    yield
    truncate_tables(migrated_database_url)


def _add_test_route(app: FastAPI) -> None:
    @app.post("/_test/users")
    async def create_user(uow: Annotated[UnitOfWork, Depends(get_uow)]) -> dict[str, str]:
        await uow.users.add(NewUser("mila", "h"))
        await uow.commit()
        return {"uow": type(uow).__name__}


@pytest.mark.usefixtures("clean_tables")
@pytest.mark.parametrize(
    ("backend", "expected"),
    [("orm", "OrmUnitOfWork"), ("sql", "SqlUnitOfWork")],
)
def test_get_uow_gives_working_unit_of_work(
    backend: Literal["orm", "sql"], expected: str, migrated_database_url: str
) -> None:
    settings = IsolatedSettings(
        db_backend=backend,
        database_url=SecretStr(migrated_database_url),
    )
    app = create_app(settings)
    _add_test_route(app)

    with TestClient(app) as client:
        response = client.post("/_test/users")

    assert response.status_code == 200
    assert response.json() == {"uow": expected}
    with psycopg.connect(migrated_database_url) as conn:
        row = conn.execute("SELECT login FROM users WHERE login = 'mila'").fetchone()
    assert row == ("mila",)


def test_get_uow_without_database_returns_500() -> None:
    app = create_app(IsolatedSettings())
    _add_test_route(app)

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/_test/users")

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal Server Error"}
