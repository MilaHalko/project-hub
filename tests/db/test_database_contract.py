"""Backend-level contract tests that need no migrated database."""

import logging

import anyio
import pytest

from project_hub.db.sql import SqlDatabase
from project_hub.users.entities import NewUser
from tests.conftest import _build_database  # pyright: ignore[reportPrivateUsage]
from tests.support.database import truncate_tables

pytestmark = pytest.mark.anyio

_UNREACHABLE_URL = "postgresql://project_hub:project_hub@127.0.0.1:1/x"


@pytest.mark.parametrize("backend", ["orm", "sql"])
async def test_open_fails_fast_when_database_is_unreachable(backend: str) -> None:
    db = _build_database(backend, _UNREACHABLE_URL)
    with anyio.fail_after(15), pytest.raises(Exception):  # noqa: B017
        await db.open()
    await db.close()


@pytest.mark.parametrize("backend", ["orm", "sql"])
async def test_backend_accepts_sqlalchemy_style_url(
    backend: str, migrated_database_url: str
) -> None:
    url = "postgresql+psycopg://" + migrated_database_url.partition("://")[2]
    db = _build_database(backend, url)
    await db.open()
    try:
        async with db.unit_of_work() as uow:
            await uow.users.add(NewUser("mila", "hash"))
            await uow.commit()
        async with db.unit_of_work() as uow:
            assert await uow.users.get_by_login("mila") is not None
    finally:
        try:
            await db.close()
        finally:
            truncate_tables(migrated_database_url)


@pytest.mark.parametrize(
    ("url", "password"),
    [
        ("postgresql+psycopg://project_hub:leak-check-pw@127.0.0.1:1/x", "leak-check-pw"),
        ("postgresql://project_hub:leak-check-pw@[::1/x", "leak-check-pw"),
        ("postgresql://project_hub:pw%zz@127.0.0.1:1/x", "pw%zz"),
    ],
    ids=["psycopg-scheme", "bad-ipv6", "bad-percent"],
)
async def test_sql_backend_does_not_log_password(
    caplog: pytest.LogCaptureFixture, url: str, password: str
) -> None:
    caplog.set_level(logging.DEBUG)
    errors: list[str] = []
    try:
        db = SqlDatabase(url)
    except ValueError as err:
        errors.append(str(err))
    else:
        with anyio.fail_after(15), pytest.raises(Exception) as excinfo:
            await db.open()
        errors.append(str(excinfo.value))
        await db.close()
    assert password not in caplog.text
    assert all(password not in text for text in errors)
