from datetime import datetime
from typing import Any, LiteralString
from uuid import UUID

import psycopg
from psycopg import errors
from psycopg.rows import class_row, dict_row

from project_hub.core.exceptions import ConflictError, NotFoundError
from project_hub.projects.entities import (
    NewProject,
    Project,
    ProjectAccess,
    ProjectMember,
    ProjectRole,
    project_role,
)

_MEMBER_CONSTRAINT = "pk_project_members"
_MEMBER_PROJECT_FK = "fk_project_members_project_id_projects"

_IS_MEMBER = (
    "EXISTS (SELECT 1 FROM project_members m WHERE m.project_id = p.id AND m.user_id = %(user_id)s)"
)
_ACCESS_CONDITION: dict[ProjectRole | None, LiteralString] = {
    None: f"(p.owner_id = %(user_id)s OR {_IS_MEMBER})",
    ProjectRole.OWNER: "p.owner_id = %(user_id)s",
    ProjectRole.PARTICIPANT: f"(p.owner_id <> %(user_id)s AND {_IS_MEMBER})",
}
_SELECT_ACCESS = (
    "SELECT p.id, p.owner_id, p.name, p.description, p.created_at, p.updated_at, "
    "p.storage_used_bytes, "
    "u.login AS owner_login "
    "FROM projects p JOIN users u ON u.id = p.owner_id "
)


def _to_access(row: dict[str, Any], user_id: UUID) -> ProjectAccess:
    owner_login = row.pop("owner_login")
    project = Project(**row)
    return ProjectAccess(
        project=project, owner_login=owner_login, role=project_role(project.owner_id, user_id)
    )


class SqlProjectRepository:
    def __init__(self, conn: psycopg.AsyncConnection[Any]) -> None:
        self._conn = conn

    async def add(self, project: NewProject) -> Project:
        # Explicit savepoint, not `conn.transaction()`: see SqlUserRepository.add.
        await self._conn.execute("SAVEPOINT add_project")
        try:
            async with self._conn.cursor(row_factory=class_row(Project)) as cur:
                await cur.execute(
                    "INSERT INTO projects (owner_id, name, description) VALUES (%s, %s, %s) "
                    "RETURNING id, owner_id, name, description, created_at, updated_at, "
                    "storage_used_bytes",
                    (project.owner_id, project.name, project.description),
                )
                row = await cur.fetchone()
        except psycopg.Error:
            await self._conn.execute("ROLLBACK TO SAVEPOINT add_project")
            await self._conn.execute("RELEASE SAVEPOINT add_project")
            raise
        await self._conn.execute("RELEASE SAVEPOINT add_project")
        assert row is not None
        return row

    async def get_for_user(self, project_id: UUID, user_id: UUID) -> ProjectAccess | None:
        async with self._conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                _SELECT_ACCESS + f"WHERE p.id = %(project_id)s AND {_ACCESS_CONDITION[None]}",
                {"project_id": project_id, "user_id": user_id},
            )
            row = await cur.fetchone()
        if row is None:
            return None
        return _to_access(row, user_id)

    async def list_for_user(
        self, user_id: UUID, *, role: ProjectRole | None, limit: int, offset: int
    ) -> list[ProjectAccess]:
        async with self._conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                _SELECT_ACCESS + f"WHERE {_ACCESS_CONDITION[role]} "
                "ORDER BY p.updated_at DESC, p.id DESC LIMIT %(limit)s OFFSET %(offset)s",
                {"user_id": user_id, "limit": limit, "offset": offset},
            )
            rows = await cur.fetchall()
        return [_to_access(row, user_id) for row in rows]

    async def update(self, project_id: UUID, name: str, description: str) -> Project | None:
        async with self._conn.cursor(row_factory=class_row(Project)) as cur:
            await cur.execute(
                "UPDATE projects SET name = %s, description = %s, updated_at = now() "
                "WHERE id = %s "
                "RETURNING id, owner_id, name, description, created_at, updated_at, "
                "storage_used_bytes",
                (name, description, project_id),
            )
            return await cur.fetchone()

    async def touch(self, project_id: UUID) -> None:
        await self._conn.execute(
            "UPDATE projects SET updated_at = now() WHERE id = %s", (project_id,)
        )

    async def refresh_storage_used(self, project_id: UUID) -> int:
        async with self._conn.cursor() as cur:
            await cur.execute(
                "UPDATE projects SET storage_used_bytes = "
                "(SELECT COALESCE(SUM(size), 0) FROM documents WHERE project_id = %(id)s), "
                "storage_counted_at = clock_timestamp() "
                "WHERE id = %(id)s RETURNING storage_used_bytes",
                {"id": project_id},
            )
            row = await cur.fetchone()
        return 0 if row is None else int(row[0])

    async def lock_storage_used(
        self, project_id: UUID, *, except_document: UUID | None = None
    ) -> int | None:
        async with self._conn.cursor() as cur:
            await cur.execute(
                "SELECT id FROM projects WHERE id = %s FOR NO KEY UPDATE", (project_id,)
            )
            if await cur.fetchone() is None:
                return None
            await cur.execute(
                "SELECT COALESCE(SUM(size), 0) FROM documents "
                "WHERE project_id = %(id)s AND id IS DISTINCT FROM %(skip)s",
                {"id": project_id, "skip": except_document},
            )
            row = await cur.fetchone()
        return 0 if row is None else int(row[0])

    async def delete(self, project_id: UUID) -> bool:
        async with self._conn.cursor() as cur:
            await cur.execute("DELETE FROM projects WHERE id = %s", (project_id,))
            return cur.rowcount > 0

    async def add_member(self, project_id: UUID, user_id: UUID) -> datetime:
        await self._conn.execute("SAVEPOINT add_member")
        try:
            async with self._conn.cursor() as cur:
                await cur.execute(
                    "INSERT INTO project_members (project_id, user_id) VALUES (%s, %s) "
                    "RETURNING created_at",
                    (project_id, user_id),
                )
                row = await cur.fetchone()
        except psycopg.Error as err:
            await self._conn.execute("ROLLBACK TO SAVEPOINT add_member")
            await self._conn.execute("RELEASE SAVEPOINT add_member")
            if (
                isinstance(err, errors.UniqueViolation)
                and err.diag.constraint_name == _MEMBER_CONSTRAINT
            ):
                raise ConflictError("User is already a participant of this project") from err
            if (
                isinstance(err, errors.ForeignKeyViolation)
                and err.diag.constraint_name == _MEMBER_PROJECT_FK
            ):
                raise NotFoundError("Project not found") from err
            raise
        await self._conn.execute("RELEASE SAVEPOINT add_member")
        assert row is not None
        joined_at: datetime = row[0]
        return joined_at

    async def remove_member(self, project_id: UUID, user_id: UUID) -> bool:
        async with self._conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM project_members WHERE project_id = %s AND user_id = %s",
                (project_id, user_id),
            )
            return cur.rowcount > 0

    async def list_members(self, project_id: UUID) -> list[ProjectMember]:
        async with self._conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT user_id, login, role, joined_at FROM ("
                "SELECT u.id AS user_id, u.login, 'owner' AS role, 0 AS rank, "
                "p.created_at AS joined_at "
                "FROM projects p JOIN users u ON u.id = p.owner_id WHERE p.id = %(project_id)s "
                "UNION ALL "
                "SELECT u.id, u.login, 'participant', 1, m.created_at "
                "FROM project_members m JOIN projects p ON p.id = m.project_id "
                "JOIN users u ON u.id = m.user_id "
                "WHERE m.project_id = %(project_id)s AND m.user_id <> p.owner_id"
                ") members ORDER BY rank, joined_at, login",
                {"project_id": project_id},
            )
            rows = await cur.fetchall()
        return [
            ProjectMember(
                user_id=row["user_id"],
                login=row["login"],
                role=ProjectRole(row["role"]),
                joined_at=row["joined_at"],
            )
            for row in rows
        ]
