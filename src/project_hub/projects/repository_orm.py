from uuid import UUID

from sqlalchemy import exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from project_hub.projects.entities import NewProject, Project, ProjectAccess, ProjectRole
from project_hub.projects.models import ProjectMemberModel, ProjectModel
from project_hub.users.models import UserModel


def _to_entity(model: ProjectModel) -> Project:
    return Project(
        id=model.id,
        owner_id=model.owner_id,
        name=model.name,
        description=model.description,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _role(project: Project, user_id: UUID) -> ProjectRole:
    return ProjectRole.OWNER if project.owner_id == user_id else ProjectRole.PARTICIPANT


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
        is_member = exists().where(
            ProjectMemberModel.project_id == ProjectModel.id,
            ProjectMemberModel.user_id == user_id,
        )
        statement = (
            select(ProjectModel, UserModel.login)
            .join(UserModel, UserModel.id == ProjectModel.owner_id)
            .where(ProjectModel.id == project_id, or_(ProjectModel.owner_id == user_id, is_member))
        )
        row = (await self._session.execute(statement)).one_or_none()
        if row is None:
            return None
        project = _to_entity(row[0])
        return ProjectAccess(project=project, owner_login=row[1], role=_role(project, user_id))
