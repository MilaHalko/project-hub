from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import class_row, dict_row

from project_hub.projects.entities import NewProject, Project, ProjectAccess, ProjectRole


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
                    "RETURNING id, owner_id, name, description, created_at, updated_at",
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
                "SELECT p.id, p.owner_id, p.name, p.description, p.created_at, p.updated_at, "
                "u.login AS owner_login "
                "FROM projects p JOIN users u ON u.id = p.owner_id "
                "WHERE p.id = %s AND (p.owner_id = %s OR EXISTS ("
                "SELECT 1 FROM project_members m WHERE m.project_id = p.id AND m.user_id = %s))",
                (project_id, user_id, user_id),
            )
            row = await cur.fetchone()
        if row is None:
            return None
        owner_login = row.pop("owner_login")
        project = Project(**row)
        role = ProjectRole.OWNER if project.owner_id == user_id else ProjectRole.PARTICIPANT
        return ProjectAccess(project=project, owner_login=owner_login, role=role)
