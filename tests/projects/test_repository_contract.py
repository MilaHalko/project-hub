from uuid import UUID, uuid4

import pytest

from project_hub.db.database import Database
from project_hub.projects.entities import NewProject, Project, ProjectAccess, ProjectRole
from project_hub.users.entities import NewUser

pytestmark = pytest.mark.anyio


async def test_add_returns_project_with_generated_fields(database: Database) -> None:
    async with database.unit_of_work() as uow:
        owner = await uow.users.add(NewUser("mila", "hash"))
        project = await uow.projects.add(NewProject(owner.id, "Diploma", "Final project"))

    assert type(project) is Project
    assert isinstance(project.id, UUID)
    assert project.created_at.tzinfo is not None
    assert project.created_at == project.updated_at
    assert project.owner_id == owner.id
    assert project.name == "Diploma"
    assert project.description == "Final project"


async def test_get_for_user_owner_sees_role_owner(database: Database) -> None:
    async with database.unit_of_work() as uow:
        owner = await uow.users.add(NewUser("mila", "hash"))
        project = await uow.projects.add(NewProject(owner.id, "Diploma", ""))
        await uow.commit()

    async with database.unit_of_work() as uow:
        access = await uow.projects.get_for_user(project.id, owner.id)

    assert access == ProjectAccess(project=project, owner_login="mila", role=ProjectRole.OWNER)


async def test_get_for_user_none_for_unknown_and_outsider(database: Database) -> None:
    async with database.unit_of_work() as uow:
        owner = await uow.users.add(NewUser("mila", "hash"))
        outsider = await uow.users.add(NewUser("anna", "hash"))
        project = await uow.projects.add(NewProject(owner.id, "Diploma", ""))
        await uow.commit()

    async with database.unit_of_work() as uow:
        assert await uow.projects.get_for_user(uuid4(), owner.id) is None
        assert await uow.projects.get_for_user(project.id, outsider.id) is None


async def test_add_project_needs_commit(database: Database) -> None:
    async with database.unit_of_work() as uow:
        owner = await uow.users.add(NewUser("mila", "hash"))
        await uow.commit()

    async with database.unit_of_work() as uow:
        project = await uow.projects.add(NewProject(owner.id, "Diploma", ""))

    async with database.unit_of_work() as uow:
        assert await uow.projects.get_for_user(project.id, owner.id) is None
