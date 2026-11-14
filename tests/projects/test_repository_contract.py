from uuid import UUID, uuid4

import psycopg
import pytest

from project_hub.core.exceptions import ConflictError
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


async def test_add_member_gives_participant_access(database: Database) -> None:
    async with database.unit_of_work() as uow:
        owner = await uow.users.add(NewUser("mila", "hash"))
        anna = await uow.users.add(NewUser("anna", "hash"))
        project = await uow.projects.add(NewProject(owner.id, "Diploma", ""))
        await uow.projects.add_member(project.id, anna.id)
        await uow.commit()

    async with database.unit_of_work() as uow:
        access = await uow.projects.get_for_user(project.id, anna.id)

    assert access == ProjectAccess(
        project=project, owner_login="mila", role=ProjectRole.PARTICIPANT
    )


async def test_add_member_twice_conflicts_and_uow_stays_usable(database: Database) -> None:
    async with database.unit_of_work() as uow:
        owner = await uow.users.add(NewUser("mila", "hash"))
        anna = await uow.users.add(NewUser("anna", "hash"))
        project = await uow.projects.add(NewProject(owner.id, "Diploma", ""))
        await uow.projects.add_member(project.id, anna.id)

        with pytest.raises(ConflictError, match="User is already a participant of this project"):
            await uow.projects.add_member(project.id, anna.id)

        second = await uow.projects.add(NewProject(owner.id, "Second", ""))
        await uow.commit()

    async with database.unit_of_work() as uow:
        assert await uow.projects.get_for_user(second.id, owner.id) is not None
        assert await uow.projects.get_for_user(project.id, anna.id) is not None


async def test_add_member_unknown_ids_raise_and_uow_stays_usable(database: Database) -> None:
    async with database.unit_of_work() as uow:
        owner = await uow.users.add(NewUser("mila", "hash"))
        anna = await uow.users.add(NewUser("anna", "hash"))
        project = await uow.projects.add(NewProject(owner.id, "Diploma", ""))

        with pytest.raises(Exception) as unknown_project:
            await uow.projects.add_member(uuid4(), anna.id)
        with pytest.raises(Exception) as unknown_user:
            await uow.projects.add_member(project.id, uuid4())

        second = await uow.projects.add(NewProject(owner.id, "Second", ""))
        await uow.commit()

    assert not isinstance(unknown_project.value, ConflictError)
    assert not isinstance(unknown_user.value, ConflictError)
    async with database.unit_of_work() as uow:
        assert await uow.projects.get_for_user(second.id, owner.id) is not None


def _set_updated_at(database_url: str, project_ids: list[UUID], ago: str) -> None:
    with psycopg.connect(database_url) as conn:
        conn.execute(
            "UPDATE projects SET updated_at = now() - %s::interval WHERE id = ANY(%s)",
            (ago, project_ids),
        )


async def test_list_for_user_returns_owned_and_shared_newest_first(
    database: Database, migrated_database_url: str
) -> None:
    async with database.unit_of_work() as uow:
        mila = await uow.users.add(NewUser("mila", "hash"))
        anna = await uow.users.add(NewUser("anna", "hash"))
        old = await uow.projects.add(NewProject(mila.id, "Old", ""))
        new = await uow.projects.add(NewProject(mila.id, "New", ""))
        shared = await uow.projects.add(NewProject(anna.id, "Shared", ""))
        await uow.projects.add(NewProject(anna.id, "Private", ""))
        await uow.projects.add_member(shared.id, mila.id)
        await uow.commit()
    _set_updated_at(migrated_database_url, [old.id], "2 days")
    _set_updated_at(migrated_database_url, [shared.id], "1 day")

    async with database.unit_of_work() as uow:
        listed = await uow.projects.list_for_user(mila.id, role=None, limit=50, offset=0)
        expected = [
            await uow.projects.get_for_user(project.id, mila.id) for project in (new, shared, old)
        ]

    assert listed == expected
    assert [access.role for access in listed] == [
        ProjectRole.OWNER,
        ProjectRole.PARTICIPANT,
        ProjectRole.OWNER,
    ]
    assert [access.owner_login for access in listed] == ["mila", "anna", "mila"]


async def test_list_for_user_ties_ordered_by_id_desc(
    database: Database, migrated_database_url: str
) -> None:
    async with database.unit_of_work() as uow:
        mila = await uow.users.add(NewUser("mila", "hash"))
        projects = [await uow.projects.add(NewProject(mila.id, f"P{i}", "")) for i in range(3)]
        await uow.commit()
    _set_updated_at(migrated_database_url, [project.id for project in projects], "1 hour")

    async with database.unit_of_work() as uow:
        listed = await uow.projects.list_for_user(mila.id, role=None, limit=50, offset=0)

    assert [access.project.id for access in listed] == sorted(
        (project.id for project in projects), reverse=True
    )


async def test_list_for_user_filters_by_role(database: Database) -> None:
    async with database.unit_of_work() as uow:
        mila = await uow.users.add(NewUser("mila", "hash"))
        anna = await uow.users.add(NewUser("anna", "hash"))
        owned = await uow.projects.add(NewProject(mila.id, "Owned", ""))
        shared = await uow.projects.add(NewProject(anna.id, "Shared", ""))
        await uow.projects.add(NewProject(anna.id, "Private", ""))
        await uow.projects.add_member(shared.id, mila.id)
        await uow.commit()

    async with database.unit_of_work() as uow:
        as_owner = await uow.projects.list_for_user(
            mila.id, role=ProjectRole.OWNER, limit=50, offset=0
        )
        as_participant = await uow.projects.list_for_user(
            mila.id, role=ProjectRole.PARTICIPANT, limit=50, offset=0
        )

    assert [(a.project.id, a.role) for a in as_owner] == [(owned.id, ProjectRole.OWNER)]
    assert [(a.project.id, a.role) for a in as_participant] == [
        (shared.id, ProjectRole.PARTICIPANT)
    ]


async def test_list_for_user_pages_with_limit_and_offset(database: Database) -> None:
    async with database.unit_of_work() as uow:
        mila = await uow.users.add(NewUser("mila", "hash"))
        for i in range(5):
            await uow.projects.add(NewProject(mila.id, f"P{i}", ""))
        await uow.commit()

    async with database.unit_of_work() as uow:
        full = await uow.projects.list_for_user(mila.id, role=None, limit=50, offset=0)
        pages = [
            await uow.projects.list_for_user(mila.id, role=None, limit=2, offset=offset)
            for offset in (0, 2, 4)
        ]

    assert len(full) == 5
    assert [len(page) for page in pages] == [2, 2, 1]
    assert [access for page in pages for access in page] == full


async def test_list_for_user_owner_listed_once_even_if_member(database: Database) -> None:
    async with database.unit_of_work() as uow:
        mila = await uow.users.add(NewUser("mila", "hash"))
        project = await uow.projects.add(NewProject(mila.id, "Diploma", ""))
        await uow.projects.add_member(project.id, mila.id)
        await uow.commit()

    async with database.unit_of_work() as uow:
        listed = await uow.projects.list_for_user(mila.id, role=None, limit=50, offset=0)
        owned = await uow.projects.list_for_user(
            mila.id, role=ProjectRole.OWNER, limit=50, offset=0
        )
        shared = await uow.projects.list_for_user(
            mila.id, role=ProjectRole.PARTICIPANT, limit=50, offset=0
        )

    assert (
        listed
        == owned
        == [ProjectAccess(project=project, owner_login="mila", role=ProjectRole.OWNER)]
    )
    assert shared == []


async def test_update_changes_fields_and_updated_at(database: Database) -> None:
    async with database.unit_of_work() as uow:
        owner = await uow.users.add(NewUser("mila", "hash"))
        project = await uow.projects.add(NewProject(owner.id, "Diploma", "Old"))
        await uow.commit()

    async with database.unit_of_work() as uow:
        updated = await uow.projects.update(project.id, "Thesis", "New")
        await uow.commit()

    assert updated is not None
    assert (updated.id, updated.owner_id) == (project.id, owner.id)
    assert (updated.name, updated.description) == ("Thesis", "New")
    assert updated.created_at == project.created_at
    assert updated.updated_at > project.created_at
    async with database.unit_of_work() as uow:
        access = await uow.projects.get_for_user(project.id, owner.id)
    assert access is not None
    assert access.project == updated


async def test_update_unknown_id_returns_none(database: Database) -> None:
    async with database.unit_of_work() as uow:
        assert await uow.projects.update(uuid4(), "Thesis", "New") is None


async def test_update_is_fresh_after_earlier_read(database: Database) -> None:
    async with database.unit_of_work() as uow:
        owner = await uow.users.add(NewUser("mila", "hash"))
        project = await uow.projects.add(NewProject(owner.id, "Diploma", "Old"))
        await uow.commit()

    async with database.unit_of_work() as uow:
        before = await uow.projects.get_for_user(project.id, owner.id)
        await uow.projects.update(project.id, "Thesis", "New")
        after = await uow.projects.get_for_user(project.id, owner.id)

    assert before is not None
    assert before.project.name == "Diploma"
    assert after is not None
    assert (after.project.name, after.project.description) == ("Thesis", "New")


async def test_update_needs_commit(database: Database) -> None:
    async with database.unit_of_work() as uow:
        owner = await uow.users.add(NewUser("mila", "hash"))
        project = await uow.projects.add(NewProject(owner.id, "Diploma", "Old"))
        await uow.commit()

    async with database.unit_of_work() as uow:
        await uow.projects.update(project.id, "Thesis", "New")

    async with database.unit_of_work() as uow:
        access = await uow.projects.get_for_user(project.id, owner.id)
    assert access is not None
    assert access.project == project
