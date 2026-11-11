from typing import Protocol, assert_never

from project_hub.core.config import Settings
from project_hub.db.orm import OrmDatabase
from project_hub.db.sql import SqlDatabase
from project_hub.db.uow import UnitOfWork
from project_hub.db.urls import sqlalchemy_url


class Database(Protocol):
    """A database backend: owns the connections and hands out units of work.

    Open it once with ``open()`` before calling ``unit_of_work()`` and close it once
    at shutdown with ``close()``. A closed database is not reopened.
    """

    def unit_of_work(self) -> UnitOfWork: ...

    async def open(self) -> None: ...

    async def close(self) -> None: ...


def create_database(settings: Settings) -> Database:
    """Build the backend selected by ``settings.db_backend``."""
    if settings.database_url is None:
        raise ValueError("database_url is not set")
    url = settings.database_url.get_secret_value()
    if not url.strip():
        raise ValueError("database_url is not set")
    sqlalchemy_url(url)  # fail fast on a bad scheme; each backend normalizes the URL itself
    match settings.db_backend:
        case "sql":
            return SqlDatabase(url)
        case "orm":
            return OrmDatabase(url)
        case _:
            assert_never(settings.db_backend)
