import pytest
from pydantic import SecretStr

from project_hub.db.database import create_database
from project_hub.db.orm import OrmDatabase
from project_hub.db.sql import SqlDatabase
from tests.isolated_settings import IsolatedSettings


@pytest.mark.parametrize(
    ("backend", "expected"),
    [("orm", OrmDatabase), ("sql", SqlDatabase)],
)
def test_create_database_picks_backend(backend: str, expected: type) -> None:
    settings = IsolatedSettings.model_validate(
        {"db_backend": backend, "database_url": SecretStr("postgresql://u:p@localhost:1/d")}
    )
    assert isinstance(create_database(settings), expected)


def test_create_database_requires_url() -> None:
    with pytest.raises(ValueError, match="database_url is not set"):
        create_database(IsolatedSettings(db_backend="sql"))
