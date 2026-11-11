"""Contract tests every `UnitOfWork` backend must pass (via the `database` fixture)."""

import pytest

from project_hub.db.database import Database
from project_hub.users.entities import NewUser

pytestmark = pytest.mark.anyio


async def test_commit_persists(database: Database) -> None:
    async with database.unit_of_work() as uow:
        await uow.users.add(NewUser("mila", "hash"))
        await uow.commit()

    async with database.unit_of_work() as uow:
        assert await uow.users.get_by_login("mila") is not None


async def test_exit_without_commit_persists_nothing(database: Database) -> None:
    async with database.unit_of_work() as uow:
        await uow.users.add(NewUser("mila", "hash"))

    async with database.unit_of_work() as uow:
        assert await uow.users.get_by_login("mila") is None


async def test_exception_rolls_back_and_propagates(database: Database) -> None:
    with pytest.raises(RuntimeError, match="boom"):
        async with database.unit_of_work() as uow:
            await uow.users.add(NewUser("mila", "hash"))
            raise RuntimeError("boom")

    async with database.unit_of_work() as uow:
        assert await uow.users.get_by_login("mila") is None


async def test_explicit_rollback_discards_changes(database: Database) -> None:
    async with database.unit_of_work() as uow:
        await uow.users.add(NewUser("mila", "hash"))
        await uow.rollback()
        await uow.commit()

    async with database.unit_of_work() as uow:
        assert await uow.users.get_by_login("mila") is None


async def test_concurrent_units_are_isolated(database: Database) -> None:
    async with database.unit_of_work() as writer:
        await writer.users.add(NewUser("mila", "hash"))

        async with database.unit_of_work() as reader:
            assert await reader.users.get_by_login("mila") is None

        await writer.commit()

    async with database.unit_of_work() as uow:
        assert await uow.users.get_by_login("mila") is not None
