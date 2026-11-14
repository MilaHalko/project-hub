from typing import Protocol
from uuid import UUID

from project_hub.projects.entities import NewProject, Project, ProjectAccess


class ProjectRepository(Protocol):
    async def add(self, project: NewProject) -> Project: ...

    async def get_for_user(self, project_id: UUID, user_id: UUID) -> ProjectAccess | None: ...

    async def add_member(self, project_id: UUID, user_id: UUID) -> None: ...
