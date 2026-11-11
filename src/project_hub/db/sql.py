from types import TracebackType
from typing import Any, Self

import psycopg
from psycopg_pool import AsyncConnectionPool

from project_hub.db.urls import psycopg_url
from project_hub.users.repository import UserRepository
from project_hub.users.repository_sql import SqlUserRepository

_OPEN_TIMEOUT = 10


class SqlUnitOfWork:
    """One pooled connection; anything not committed is rolled back on exit."""

    users: UserRepository

    def __init__(self, pool: AsyncConnectionPool[psycopg.AsyncConnection[Any]]) -> None:
        self._pool = pool
        self._conn: psycopg.AsyncConnection[Any] | None = None

    def _connection(self) -> psycopg.AsyncConnection[Any]:
        if self._conn is None:
            raise RuntimeError("Unit of work is not entered; use 'async with'")
        return self._conn

    async def commit(self) -> None:
        await self._connection().commit()

    async def rollback(self) -> None:
        await self._connection().rollback()

    async def __aenter__(self) -> Self:
        # Not `pool.connection()`: its context manager commits an open transaction on exit.
        self._conn = await self._pool.getconn()
        self.users = SqlUserRepository(self._conn)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        conn = self._conn
        if conn is None:
            return
        self._conn = None
        try:
            await conn.rollback()
        finally:
            await self._pool.putconn(conn)


class SqlDatabase:
    """Plain psycopg backend on a connection pool."""

    def __init__(self, url: str) -> None:
        self._pool: AsyncConnectionPool[psycopg.AsyncConnection[Any]] = AsyncConnectionPool(
            psycopg_url(url), open=False
        )

    async def open(self) -> None:
        await self._pool.open(wait=True, timeout=_OPEN_TIMEOUT)

    async def close(self) -> None:
        await self._pool.close()

    def unit_of_work(self) -> SqlUnitOfWork:
        return SqlUnitOfWork(self._pool)
