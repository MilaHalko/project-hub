from typing import Protocol

from project_hub.core.config import Settings
from project_hub.db.orm import OrmDatabase
from project_hub.db.sql import SqlDatabase
from project_hub.db.uow import UnitOfWork


class Database(Protocol):
    """A database backend: owns the connections and hands out units of work."""

    def unit_of_work(self) -> UnitOfWork: ...

    async def open(self) -> None: ...

    async def close(self) -> None: ...


def create_database(settings: Settings) -> Database:
    """Build the backend selected by ``settings.db_backend``."""
    if settings.database_url is None:
        raise ValueError("database_url is not set")
    url = settings.database_url.get_secret_value()
    if settings.db_backend == "sql":
        return SqlDatabase(url)
    return OrmDatabase(url)
