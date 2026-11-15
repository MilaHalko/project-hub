import logging
from uuid import UUID

from project_hub.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError
from project_hub.db.uow import UnitOfWork
from project_hub.projects.entities import NewProject, ProjectAccess, ProjectMember, ProjectRole
from project_hub.projects.schemas import ProjectIn
from project_hub.storage.files import FileStorage, discard_quietly
from project_hub.users.entities import User

logger = logging.getLogger(__name__)


def _log_event(event: str, user: User, project_id: UUID, member_id: UUID | None = None) -> None:
    extra: dict[str, object] = {
        "event": event,
        "login": user.login,
        "user_id": user.id,
        "project_id": project_id,
    }
    message = "%s login=%r user_id=%s project_id=%s"
    args: tuple[object, ...] = (event, user.login, user.id, project_id)
    if member_id is not None:
        message += " member_id=%s"
        args += (member_id,)
        extra["member_id"] = member_id
    logger.info(message, *args, extra=extra)


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


async def list_projects(
    uow: UnitOfWork, user: User, *, role: ProjectRole | None, limit: int, offset: int
) -> list[ProjectAccess]:
    return await uow.projects.list_for_user(user.id, role=role, limit=limit, offset=offset)


async def update_project(
    uow: UnitOfWork, user: User, project_id: UUID, data: ProjectIn
) -> ProjectAccess:
    access = await get_project(uow, user, project_id)
    updated = await uow.projects.update(project_id, data.name, data.description)
    if updated is None:
        raise NotFoundError("Project not found")
    await uow.commit()
    return ProjectAccess(project=updated, owner_login=access.owner_login, role=access.role)


async def delete_project(
    uow: UnitOfWork, storage: FileStorage, user: User, project_id: UUID
) -> None:
    access = await get_project(uow, user, project_id)
    if access.role is ProjectRole.PARTICIPANT:
        raise PermissionDeniedError("Only the project owner can delete the project")
    keys = await uow.documents.storage_keys_for_project(project_id)
    if not await uow.projects.delete(project_id):
        raise NotFoundError("Project not found")
    await uow.commit()
    _log_event("project deleted", user, project_id)
    await discard_quietly(storage, keys, project_id=project_id)


async def list_members(uow: UnitOfWork, user: User, project_id: UUID) -> list[ProjectMember]:
    await get_project(uow, user, project_id)
    return await uow.projects.list_members(project_id)


async def invite(uow: UnitOfWork, user: User, project_id: UUID, login: str) -> ProjectMember:
    access = await get_project(uow, user, project_id)
    if access.role is ProjectRole.PARTICIPANT:
        raise PermissionDeniedError("Only the project owner can invite users")
    invited = await uow.users.get_by_login(login)
    if invited is None:
        raise NotFoundError("User not found")
    if invited.id == access.project.owner_id:
        raise ConflictError("You already own this project")
    joined_at = await uow.projects.add_member(project_id, invited.id)
    await uow.commit()
    _log_event("participant invited", user, project_id, member_id=invited.id)
    return ProjectMember(invited.id, invited.login, ProjectRole.PARTICIPANT, joined_at)


async def remove_member(uow: UnitOfWork, user: User, project_id: UUID, member_id: UUID) -> None:
    access = await get_project(uow, user, project_id)
    is_self = member_id == user.id
    if access.role is ProjectRole.PARTICIPANT and not is_self:
        raise PermissionDeniedError("Only the project owner can remove participants")
    if access.role is ProjectRole.OWNER and is_self:
        raise ConflictError("The owner cannot leave the project")
    if not await uow.projects.remove_member(project_id, member_id):
        raise NotFoundError("Participant not found")
    await uow.commit()
    event = "participant left" if is_self else "participant removed"
    _log_event(event, user, project_id, member_id=member_id)
