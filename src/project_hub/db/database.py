from typing import Protocol

from project_hub.db.uow import UnitOfWork


class Database(Protocol):
    """A database backend: owns the connections and hands out units of work."""

    def unit_of_work(self) -> UnitOfWork: ...

    async def open(self) -> None: ...

    async def close(self) -> None: ...
