"""Contract tests every `UserRepository` backend must pass (via the `database` fixture)."""

import secrets
from uuid import UUID, uuid4

import pytest

from project_hub.core.exceptions import ConflictError
from project_hub.db.database import Database
from project_hub.users.entities import NewUser, User

pytestmark = pytest.mark.anyio


async def test_add_returns_user_with_generated_fields(database: Database) -> None:
    async with database.unit_of_work() as uow:
        user = await uow.users.add(NewUser("mila", "hash"))

    assert type(user) is User
    assert isinstance(user.id, UUID)
    assert user.created_at.tzinfo is not None
    assert user.login == "mila"
    assert user.password_hash == "hash"


async def test_get_by_id_and_login_return_added_user(database: Database) -> None:
    async with database.unit_of_work() as uow:
        added = await uow.users.add(NewUser("mila", "hash"))
        await uow.commit()

    async with database.unit_of_work() as uow:
        by_id = await uow.users.get_by_id(added.id)
        by_login = await uow.users.get_by_login("mila")

    assert type(by_id) is User
    assert type(by_login) is User
    assert by_id == added
    assert by_login == added


async def test_unknown_id_and_login_return_none(database: Database) -> None:
    async with database.unit_of_work() as uow:
        assert await uow.users.get_by_id(uuid4()) is None
        assert await uow.users.get_by_login("nobody") is None


async def test_duplicate_login_raises_conflict_and_uow_stays_usable(database: Database) -> None:
    async with database.unit_of_work() as uow:
        await uow.users.add(NewUser("mila", "hash"))
        await uow.commit()

    async with database.unit_of_work() as uow:
        await uow.users.add(NewUser("anna", "hash"))
        with pytest.raises(ConflictError, match="Login 'mila' is already taken"):
            await uow.users.add(NewUser("mila", "other"))
        await uow.users.add(NewUser("bob", "hash"))
        await uow.commit()

    async with database.unit_of_work() as uow:
        assert await uow.users.get_by_login("anna") is not None
        assert await uow.users.get_by_login("bob") is not None


async def test_login_is_case_sensitive(database: Database) -> None:
    async with database.unit_of_work() as uow:
        lower = await uow.users.add(NewUser("mila", "hash"))
        upper = await uow.users.add(NewUser("Mila", "hash"))
        await uow.commit()

    async with database.unit_of_work() as uow:
        found_lower = await uow.users.get_by_login("mila")
        found_upper = await uow.users.get_by_login("Mila")

    assert found_lower == lower
    assert found_upper == upper
    assert lower.id != upper.id


async def test_failed_add_keeps_unit_of_work_usable(database: Database) -> None:
    async with database.unit_of_work() as uow:
        await uow.users.add(NewUser("anna", "hash"))
        with pytest.raises(Exception) as exc_info:
            await uow.users.add(NewUser(secrets.token_hex(4000), "h"))
        assert not isinstance(exc_info.value, ConflictError)
        await uow.users.add(NewUser("bob", "hash"))
        await uow.commit()

    async with database.unit_of_work() as uow:
        assert await uow.users.get_by_login("anna") is not None
        assert await uow.users.get_by_login("bob") is not None
