from collections.abc import AsyncIterator

from fastapi import Request

from project_hub.db.database import Database
from project_hub.db.uow import UnitOfWork


async def get_uow(request: Request) -> AsyncIterator[UnitOfWork]:
    """Yield a unit of work for one request; it never commits."""
    database: Database | None = request.app.state.database
    if database is None:
        raise RuntimeError("Database is not configured: set APP_DATABASE_URL")
    async with database.unit_of_work() as uow:
        yield uow
