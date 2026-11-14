import logging
from uuid import UUID

from project_hub.core.exceptions import NotFoundError
from project_hub.db.uow import UnitOfWork
from project_hub.projects.entities import NewProject, ProjectAccess, ProjectRole
from project_hub.projects.schemas import ProjectIn
from project_hub.users.entities import User

logger = logging.getLogger(__name__)


def _log_event(event: str, user: User, project_id: UUID) -> None:
    logger.info(
        "%s login=%r user_id=%s project_id=%s",
        event,
        user.login,
        user.id,
        project_id,
        extra={"event": event, "login": user.login, "user_id": user.id, "project_id": project_id},
    )


async def create_project(uow: UnitOfWork, user: User, data: ProjectIn) -> ProjectAccess:
    project = await uow.projects.add(
        NewProject(owner_id=user.id, name=data.name, description=data.description)
    )
    await uow.commit()
    _log_event("project created", user, project.id)
    return ProjectAccess(project=project, owner_login=user.login, role=ProjectRole.OWNER)


async def get_project(uow: UnitOfWork, user: User, project_id: UUID) -> ProjectAccess:
    access = await uow.projects.get_for_user(project_id, user.id)
    if access is None:
        raise NotFoundError("Project not found")
    return access
