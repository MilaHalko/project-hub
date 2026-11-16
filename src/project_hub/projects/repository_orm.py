from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    ColumnElement,
    Select,
    delete,
    exists,
    func,
    literal,
    or_,
    select,
    update,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from project_hub.core.exceptions import ConflictError, NotFoundError
from project_hub.documents.models import DocumentModel
from project_hub.projects.entities import (
    NewProject,
    Project,
    ProjectAccess,
    ProjectMember,
    ProjectRole,
    project_role,
)
from project_hub.projects.models import ProjectMemberModel, ProjectModel
from project_hub.users.models import UserModel

_MEMBER_CONSTRAINT = "pk_project_members"
_MEMBER_PROJECT_FK = "fk_project_members_project_id_projects"


def _violated_constraint(error: IntegrityError) -> str | None:
    diag = getattr(error.orig, "diag", None)
    name: str | None = getattr(diag, "constraint_name", None)
    return name


def _to_entity(model: ProjectModel) -> Project:
    return Project(
        id=model.id,
        owner_id=model.owner_id,
        name=model.name,
        description=model.description,
        created_at=model.created_at,
        updated_at=model.updated_at,
        storage_used_bytes=model.storage_used_bytes,
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

    async def update(self, project_id: UUID, name: str, description: str) -> Project | None:
        # Without populate_existing, a ProjectModel loaded earlier in this session stays stale.
        statement = (
            update(ProjectModel)
            .where(ProjectModel.id == project_id)
            .values(name=name, description=description, updated_at=func.now())
            .returning(ProjectModel)
            .execution_options(populate_existing=True)
        )
        model = (await self._session.execute(statement)).scalar_one_or_none()
        return None if model is None else _to_entity(model)

    async def touch(self, project_id: UUID) -> None:
        statement = (
            update(ProjectModel)
            .where(ProjectModel.id == project_id)
            .values(updated_at=func.now())
            .returning(ProjectModel)
            .execution_options(populate_existing=True)
        )
        await self._session.execute(statement)

    async def refresh_storage_used(self, project_id: UUID) -> int:
        total = (
            select(func.coalesce(func.sum(DocumentModel.size), 0))
            .where(DocumentModel.project_id == project_id)
            .scalar_subquery()
        )
        statement = (
            update(ProjectModel)
            .where(ProjectModel.id == project_id)
            .values(storage_used_bytes=total, storage_counted_at=func.clock_timestamp())
            .returning(ProjectModel.storage_used_bytes)
            .execution_options(populate_existing=True)
        )
        return (await self._session.execute(statement)).scalar_one_or_none() or 0

    async def delete(self, project_id: UUID) -> bool:
        statement = (
            delete(ProjectModel).where(ProjectModel.id == project_id).returning(ProjectModel.id)
        )
        return (await self._session.execute(statement)).scalar_one_or_none() is not None

    async def add_member(self, project_id: UUID, user_id: UUID) -> datetime:
        model = ProjectMemberModel(project_id=project_id, user_id=user_id)
        try:
            async with self._session.begin_nested():
                self._session.add(model)
                await self._session.flush()
        except IntegrityError as err:
            constraint = _violated_constraint(err)
            if constraint == _MEMBER_CONSTRAINT:
                raise ConflictError("User is already a participant of this project") from err
            if constraint == _MEMBER_PROJECT_FK:
                raise NotFoundError("Project not found") from err
            raise
        return model.created_at

    async def remove_member(self, project_id: UUID, user_id: UUID) -> bool:
        statement = (
            delete(ProjectMemberModel)
            .where(ProjectMemberModel.project_id == project_id)
            .where(ProjectMemberModel.user_id == user_id)
            .returning(ProjectMemberModel.user_id)
        )
        return (await self._session.execute(statement)).scalar_one_or_none() is not None

    async def list_members(self, project_id: UUID) -> list[ProjectMember]:
        owner = (
            select(
                UserModel.id.label("user_id"),
                UserModel.login.label("login"),
                literal(0).label("rank"),
                ProjectModel.created_at.label("joined_at"),
            )
            .join(ProjectModel, ProjectModel.owner_id == UserModel.id)
            .where(ProjectModel.id == project_id)
        )
        participants = (
            select(
                UserModel.id.label("user_id"),
                UserModel.login.label("login"),
                literal(1).label("rank"),
                ProjectMemberModel.created_at.label("joined_at"),
            )
            .join(ProjectMemberModel, ProjectMemberModel.user_id == UserModel.id)
            .join(ProjectModel, ProjectModel.id == ProjectMemberModel.project_id)
            .where(
                ProjectMemberModel.project_id == project_id,
                ProjectMemberModel.user_id != ProjectModel.owner_id,
            )
        )
        union = owner.union_all(participants).subquery()
        statement = select(union).order_by(union.c.rank, union.c.joined_at, union.c.login)
        rows = (await self._session.execute(statement)).all()
        return [
            ProjectMember(
                user_id=row.user_id,
                login=row.login,
                role=ProjectRole.OWNER if row.rank == 0 else ProjectRole.PARTICIPANT,
                joined_at=row.joined_at,
            )
            for row in rows
        ]
