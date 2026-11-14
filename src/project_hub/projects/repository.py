from typing import Protocol
from uuid import UUID

from project_hub.projects.entities import NewProject, Project, ProjectAccess, ProjectRole


class ProjectRepository(Protocol):
    async def add(self, project: NewProject) -> Project: ...

    async def get_for_user(self, project_id: UUID, user_id: UUID) -> ProjectAccess | None: ...

    async def list_for_user(
        self, user_id: UUID, *, role: ProjectRole | None, limit: int, offset: int
    ) -> list[ProjectAccess]: ...

    async def update(self, project_id: UUID, name: str, description: str) -> Project | None: ...

    async def delete(self, project_id: UUID) -> bool: ...

    async def add_member(self, project_id: UUID, user_id: UUID) -> None: ...
