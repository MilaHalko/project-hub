from types import TracebackType
from typing import Self

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from project_hub.db.urls import sqlalchemy_url
from project_hub.users.repository import UserRepository
from project_hub.users.repository_orm import OrmUserRepository


class OrmUnitOfWork:
    """One `AsyncSession`; anything not committed is rolled back on exit."""

    users: UserRepository

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session = session_factory()
        self.users = OrmUserRepository(self._session)

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        try:
            await self._session.rollback()
        finally:
            await self._session.close()


class OrmDatabase:
    """SQLAlchemy backend."""

    def __init__(self, url: str) -> None:
        self._url = sqlalchemy_url(url)
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    async def open(self) -> None:
        engine = create_async_engine(self._url, hide_parameters=True)
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        except BaseException:
            await engine.dispose()
            raise
        self._engine = engine
        self._session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def close(self) -> None:
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None

    def unit_of_work(self) -> OrmUnitOfWork:
        if self._session_factory is None:
            raise RuntimeError("Database is not open; call open() first")
        return OrmUnitOfWork(self._session_factory)
