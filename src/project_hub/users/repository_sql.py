from typing import Any, LiteralString
from uuid import UUID

import psycopg
from psycopg import errors
from psycopg.rows import class_row

from project_hub.core.exceptions import ConflictError
from project_hub.users.entities import NewUser, User

_LOGIN_CONSTRAINT = "uq_users_login"


class SqlUserRepository:
    def __init__(self, conn: psycopg.AsyncConnection[Any]) -> None:
        self._conn = conn

    async def add(self, user: NewUser) -> User:
        # Explicit savepoint, not `conn.transaction()`: with no transaction open yet,
        # `conn.transaction()` would start and COMMIT an outer one, breaking the UoW.
        await self._conn.execute("SAVEPOINT add_user")
        try:
            async with self._conn.cursor(row_factory=class_row(User)) as cur:
                await cur.execute(
                    "INSERT INTO users (login, password_hash) VALUES (%s, %s) "
                    "RETURNING id, login, password_hash, created_at",
                    (user.login, user.password_hash),
                )
                row = await cur.fetchone()
        except errors.UniqueViolation as err:
            await self._conn.execute("ROLLBACK TO SAVEPOINT add_user")
            if err.diag.constraint_name == _LOGIN_CONSTRAINT:
                raise ConflictError(f"Login {user.login!r} is already taken") from err
            raise
        await self._conn.execute("RELEASE SAVEPOINT add_user")
        assert row is not None  # INSERT ... RETURNING always yields a row
        return row

    async def get_by_id(self, user_id: UUID) -> User | None:
        return await self._fetch_one(
            "SELECT id, login, password_hash, created_at FROM users WHERE id = %s", (user_id,)
        )

    async def get_by_login(self, login: str) -> User | None:
        return await self._fetch_one(
            "SELECT id, login, password_hash, created_at FROM users WHERE login = %s", (login,)
        )

    async def _fetch_one(self, query: LiteralString, params: tuple[object, ...]) -> User | None:
        async with self._conn.cursor(row_factory=class_row(User)) as cur:
            await cur.execute(query, params)
            return await cur.fetchone()
