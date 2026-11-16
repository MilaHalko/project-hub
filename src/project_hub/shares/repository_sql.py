from datetime import datetime
from typing import Any
from uuid import UUID

import psycopg
from psycopg import errors
from psycopg.rows import class_row

from project_hub.core.exceptions import NotFoundError
from project_hub.shares.entities import ShareLink

_SHARE_PROJECT_FK = "fk_project_shares_project_id_projects"


class SqlShareRepository:
    def __init__(self, conn: psycopg.AsyncConnection[Any]) -> None:
        self._conn = conn

    async def delete_expired(self, project_id: UUID, now: datetime) -> None:
        await self._conn.execute(
            "DELETE FROM project_shares WHERE project_id = %s AND expires_at <= %s",
            (project_id, now),
        )

    async def count_pending(self, project_id: UUID, now: datetime, *, except_email: str) -> int:
        async with self._conn.cursor() as cur:
            await cur.execute(
                "SELECT count(*) FROM project_shares "
                "WHERE project_id = %s AND expires_at > %s AND email <> %s",
                (project_id, now, except_email),
            )
            row = await cur.fetchone()
        assert row is not None
        count: int = row[0]
        return count

    async def put(
        self, project_id: UUID, email: str, token_hash: str, expires_at: datetime
    ) -> None:
        await self._conn.execute("SAVEPOINT put_share")
        try:
            # A new id, so a join that looked up the replaced link cannot claim this one.
            await self._conn.execute(
                "INSERT INTO project_shares (project_id, email, token_hash, expires_at) "
                "VALUES (%s, %s, %s, %s) "
                "ON CONFLICT ON CONSTRAINT uq_project_shares_project_id_email DO UPDATE SET "
                "id = gen_random_uuid(), token_hash = EXCLUDED.token_hash, "
                "expires_at = EXCLUDED.expires_at, created_at = now()",
                (project_id, email, token_hash, expires_at),
            )
        except psycopg.Error as err:
            await self._conn.execute("ROLLBACK TO SAVEPOINT put_share")
            await self._conn.execute("RELEASE SAVEPOINT put_share")
            if (
                isinstance(err, errors.ForeignKeyViolation)
                and err.diag.constraint_name == _SHARE_PROJECT_FK
            ):
                raise NotFoundError("Project not found") from err
            raise
        await self._conn.execute("RELEASE SAVEPOINT put_share")

    async def find_pending(self, token_hash: str, now: datetime) -> ShareLink | None:
        async with self._conn.cursor(row_factory=class_row(ShareLink)) as cur:
            await cur.execute(
                "SELECT id, project_id, email, expires_at FROM project_shares "
                "WHERE token_hash = %s AND expires_at > %s",
                (token_hash, now),
            )
            return await cur.fetchone()

    async def claim(self, share_id: UUID) -> bool:
        async with self._conn.cursor() as cur:
            await cur.execute("DELETE FROM project_shares WHERE id = %s", (share_id,))
            return cur.rowcount > 0
