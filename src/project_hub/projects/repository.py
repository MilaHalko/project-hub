from datetime import datetime
from typing import Protocol
from uuid import UUID

from project_hub.projects.entities import (
    NewProject,
    Project,
    ProjectAccess,
    ProjectMember,
    ProjectRole,
)


class ProjectRepository(Protocol):
    async def add(self, project: NewProject) -> Project: ...

    async def get_for_user(self, project_id: UUID, user_id: UUID) -> ProjectAccess | None: ...

    async def list_for_user(
        self, user_id: UUID, *, role: ProjectRole | None, limit: int, offset: int
    ) -> list[ProjectAccess]: ...

    async def update(self, project_id: UUID, name: str, description: str) -> Project | None: ...

    async def touch(self, project_id: UUID) -> None: ...

    async def refresh_storage_used(self, project_id: UUID) -> int: ...

    # Call it before any write on the project: the row lock makes concurrent uploads check the
    # limit one at a time, and READ COMMITTED gives each later statement a fresh snapshot, so the
    # SUM refresh after the lock counts every row other writers committed meanwhile.
    async def lock_storage_used(
        self, project_id: UUID, *, except_document: UUID | None = None
    ) -> int | None: ...

    async def delete(self, project_id: UUID) -> bool: ...

    async def add_member(self, project_id: UUID, user_id: UUID) -> datetime: ...

    async def remove_member(self, project_id: UUID, user_id: UUID) -> bool: ...

    async def list_members(self, project_id: UUID) -> list[ProjectMember]: ...
