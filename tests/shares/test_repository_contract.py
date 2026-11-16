from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from project_hub.core.exceptions import NotFoundError
from project_hub.db.database import Database
from project_hub.db.uow import UnitOfWork
from project_hub.projects.entities import NewProject, Project
from project_hub.shares.entities import ShareLink
from project_hub.shares.tokens import hash_token
from project_hub.users.entities import NewUser

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)
LATER = NOW + timedelta(days=7)
SECOND = timedelta(seconds=1)


async def _project(uow: UnitOfWork, name: str = "Diploma") -> Project:
    owner = await uow.users.add(NewUser(f"mila-{uuid4().hex[:8]}", "hash"))
    return await uow.projects.add(NewProject(owner.id, name, ""))


async def test_put_then_find_pending_returns_link_until_it_expires(database: Database) -> None:
    async with database.unit_of_work() as uow:
        project = await _project(uow)
        await uow.shares.put(project.id, "anna@example.com", hash_token("one"), LATER)
        await uow.commit()

    async with database.unit_of_work() as uow:
        link = await uow.shares.find_pending(hash_token("one"), NOW)
        expired = await uow.shares.find_pending(hash_token("one"), LATER + SECOND)
        unknown = await uow.shares.find_pending(hash_token("other"), NOW)

    assert type(link) is ShareLink
    assert isinstance(link.id, UUID)
    assert link == ShareLink(link.id, project.id, "anna@example.com", LATER)
    assert expired is None
    assert unknown is None


async def test_second_put_replaces_the_link_for_that_address_only(database: Database) -> None:
    async with database.unit_of_work() as uow:
        project = await _project(uow)
        other = await _project(uow, "Other")
        await uow.shares.put(project.id, "anna@example.com", hash_token("old"), LATER)
        await uow.shares.put(other.id, "anna@example.com", hash_token("elsewhere"), LATER)
        await uow.commit()

    async with database.unit_of_work() as uow:
        await uow.shares.put(project.id, "anna@example.com", hash_token("new"), LATER + SECOND)
        await uow.commit()

    async with database.unit_of_work() as uow:
        old = await uow.shares.find_pending(hash_token("old"), NOW)
        new = await uow.shares.find_pending(hash_token("new"), NOW)
        elsewhere = await uow.shares.find_pending(hash_token("elsewhere"), NOW)

    assert old is None
    assert new is not None
    assert (new.project_id, new.email, new.expires_at) == (
        project.id,
        "anna@example.com",
        LATER + SECOND,
    )
    assert elsewhere is not None
    assert elsewhere.project_id == other.id
    assert elsewhere.id != new.id


async def test_count_pending_counts_unexpired_links_of_the_project_except_one_address(
    database: Database,
) -> None:
    async with database.unit_of_work() as uow:
        project = await _project(uow)
        other = await _project(uow, "Other")
        await uow.shares.put(project.id, "a@example.com", hash_token("a"), LATER)
        await uow.shares.put(project.id, "b@example.com", hash_token("b"), LATER)
        await uow.shares.put(project.id, "old@example.com", hash_token("old"), NOW - SECOND)
        await uow.shares.put(other.id, "c@example.com", hash_token("c"), LATER)
        await uow.commit()

    async with database.unit_of_work() as uow:
        assert await uow.shares.count_pending(project.id, NOW, except_email="x@example.com") == 2
        assert await uow.shares.count_pending(project.id, NOW, except_email="a@example.com") == 1
        assert await uow.shares.count_pending(other.id, NOW, except_email="x@example.com") == 1
        assert await uow.shares.count_pending(uuid4(), NOW, except_email="x@example.com") == 0


async def test_delete_expired_removes_only_that_projects_expired_links(
    database: Database,
) -> None:
    async with database.unit_of_work() as uow:
        project = await _project(uow)
        other = await _project(uow, "Other")
        await uow.shares.put(project.id, "live@example.com", hash_token("live"), LATER)
        await uow.shares.put(project.id, "old@example.com", hash_token("old"), NOW - SECOND)
        await uow.shares.put(other.id, "old@example.com", hash_token("other-old"), NOW - SECOND)
        await uow.commit()

    async with database.unit_of_work() as uow:
        await uow.shares.delete_expired(project.id, NOW)
        await uow.commit()

    past = NOW - timedelta(days=1)
    async with database.unit_of_work() as uow:
        assert await uow.shares.find_pending(hash_token("live"), NOW) is not None
        assert await uow.shares.find_pending(hash_token("old"), past) is None
        assert await uow.shares.find_pending(hash_token("other-old"), past) is not None


async def test_claim_succeeds_once_and_the_link_is_gone(database: Database) -> None:
    async with database.unit_of_work() as uow:
        project = await _project(uow)
        await uow.shares.put(project.id, "anna@example.com", hash_token("one"), LATER)
        await uow.commit()

    async with database.unit_of_work() as uow:
        link = await uow.shares.find_pending(hash_token("one"), NOW)
        assert link is not None
        assert await uow.shares.claim(link.id) is True
        assert await uow.shares.claim(link.id) is False
        await uow.commit()

    async with database.unit_of_work() as uow:
        assert await uow.shares.find_pending(hash_token("one"), NOW) is None
        assert await uow.shares.claim(link.id) is False


async def test_claim_without_commit_is_lost(database: Database) -> None:
    async with database.unit_of_work() as uow:
        project = await _project(uow)
        await uow.shares.put(project.id, "anna@example.com", hash_token("one"), LATER)
        await uow.commit()

    async with database.unit_of_work() as uow:
        link = await uow.shares.find_pending(hash_token("one"), NOW)
        assert link is not None
        assert await uow.shares.claim(link.id) is True

    async with database.unit_of_work() as uow:
        assert await uow.shares.find_pending(hash_token("one"), NOW) == link


async def test_put_for_unknown_project_is_not_found_and_uow_stays_usable(
    database: Database,
) -> None:
    async with database.unit_of_work() as uow:
        project = await _project(uow)

        with pytest.raises(NotFoundError, match="Project not found"):
            await uow.shares.put(uuid4(), "anna@example.com", hash_token("lost"), LATER)

        await uow.shares.put(project.id, "anna@example.com", hash_token("kept"), LATER)
        await uow.commit()

    async with database.unit_of_work() as uow:
        assert await uow.shares.find_pending(hash_token("lost"), NOW) is None
        assert await uow.shares.find_pending(hash_token("kept"), NOW) is not None


async def test_deleting_the_project_removes_its_links(database: Database) -> None:
    async with database.unit_of_work() as uow:
        project = await _project(uow)
        await uow.shares.put(project.id, "anna@example.com", hash_token("one"), LATER)
        await uow.commit()

    async with database.unit_of_work() as uow:
        assert await uow.projects.delete(project.id) is True
        await uow.commit()

    async with database.unit_of_work() as uow:
        assert await uow.shares.find_pending(hash_token("one"), NOW) is None


async def test_a_replaced_link_cannot_be_claimed(database: Database) -> None:
    async with database.unit_of_work() as uow:
        project = await _project(uow)
        await uow.shares.put(project.id, "anna@example.com", hash_token("old"), LATER)
        await uow.commit()

    async with database.unit_of_work() as uow:
        old = await uow.shares.find_pending(hash_token("old"), NOW)
        assert old is not None
        await uow.shares.put(project.id, "anna@example.com", hash_token("new"), LATER)
        assert await uow.shares.claim(old.id) is False
        await uow.commit()

    async with database.unit_of_work() as uow:
        assert await uow.shares.find_pending(hash_token("new"), NOW) is not None
