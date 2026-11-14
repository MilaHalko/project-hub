from uuid import UUID

from sqlalchemy import ColumnElement, Select, exists, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from project_hub.core.exceptions import ConflictError
from project_hub.projects.entities import (
    NewProject,
    Project,
    ProjectAccess,
    ProjectRole,
    project_role,
)
from project_hub.projects.models import ProjectMemberModel, ProjectModel
from project_hub.users.models import UserModel

_MEMBER_CONSTRAINT = "pk_project_members"


def _is_member_conflict(error: IntegrityError) -> bool:
    diag = getattr(error.orig, "diag", None)
    return getattr(diag, "constraint_name", None) == _MEMBER_CONSTRAINT


def _to_entity(model: ProjectModel) -> Project:
    return Project(
        id=model.id,
        owner_id=model.owner_id,
        name=model.name,
        description=model.description,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _is_member(user_id: UUID) -> ColumnElement[bool]:
    return exists().where(
        ProjectMemberModel.project_id == ProjectModel.id,
        ProjectMemberModel.user_id == user_id,
    )


def _access_condition(user_id: UUID, role: ProjectRole | None) -> ColumnElement[bool]:
    if role is ProjectRole.OWNER:
        return ProjectModel.owner_id == user_id
    if role is ProjectRole.PARTICIPANT:
        return (ProjectModel.owner_id != user_id) & _is_member(user_id)
    return or_(ProjectModel.owner_id == user_id, _is_member(user_id))


def _access_select(user_id: UUID, role: ProjectRole | None) -> Select[ProjectModel, str]:
    return (
        select(ProjectModel, UserModel.login)
        .join(UserModel, UserModel.id == ProjectModel.owner_id)
        .where(_access_condition(user_id, role))
    )


def _to_access(model: ProjectModel, owner_login: str, user_id: UUID) -> ProjectAccess:
    project = _to_entity(model)
    return ProjectAccess(
        project=project, owner_login=owner_login, role=project_role(project.owner_id, user_id)
    )


class OrmProjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, project: NewProject) -> Project:
        model = ProjectModel(
            owner_id=project.owner_id, name=project.name, description=project.description
        )
        async with self._session.begin_nested():
            self._session.add(model)
            await self._session.flush()
        return _to_entity(model)

    async def get_for_user(self, project_id: UUID, user_id: UUID) -> ProjectAccess | None:
        statement = _access_select(user_id, None).where(ProjectModel.id == project_id)
        row = (await self._session.execute(statement)).one_or_none()
        if row is None:
            return None
        return _to_access(row[0], row[1], user_id)

    async def list_for_user(
        self, user_id: UUID, *, role: ProjectRole | None, limit: int, offset: int
    ) -> list[ProjectAccess]:
        statement = (
            _access_select(user_id, role)
            .order_by(ProjectModel.updated_at.desc(), ProjectModel.id.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(statement)).all()
        return [_to_access(model, owner_login, user_id) for model, owner_login in rows]

    async def add_member(self, project_id: UUID, user_id: UUID) -> None:
        try:
            async with self._session.begin_nested():
                self._session.add(ProjectMemberModel(project_id=project_id, user_id=user_id))
                await self._session.flush()
        except IntegrityError as err:
            if _is_member_conflict(err):
                raise ConflictError("User is already a participant of this project") from err
            raise
