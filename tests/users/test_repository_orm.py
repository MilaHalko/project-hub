"""ORM-only behaviour the shared contract tests cannot reach (they never hold a model)."""

from collections.abc import AsyncIterator

import psycopg
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from project_hub.db.urls import sqlalchemy_url
from project_hub.users.entities import NewUser
from project_hub.users.models import UserModel
from project_hub.users.repository_orm import OrmUserRepository
from tests.support.database import truncate_tables

pytestmark = pytest.mark.anyio


@pytest.fixture
async def session(migrated_database_url: str) -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(sqlalchemy_url(migrated_database_url))
    try:
        async with AsyncSession(engine, expire_on_commit=False) as s:
            yield s
    finally:
        await engine.dispose()
        truncate_tables(migrated_database_url)


async def test_increment_token_version_refreshes_a_stale_model_held_in_the_session(
    session: AsyncSession, migrated_database_url: str
) -> None:
    repo = OrmUserRepository(session)
    added = await repo.add(NewUser("mila", "hash"))
    await session.commit()
    held = await session.get(UserModel, added.id)  # e.g. loaded through a relationship
    assert held is not None
    assert held.token_version == 0
    with psycopg.connect(migrated_database_url) as other:  # a concurrent logout commits
        other.execute(
            "UPDATE users SET token_version = token_version + 1 WHERE id = %s", (added.id,)
        )

    updated = await repo.increment_token_version(added.id)

    assert updated is not None
    assert updated.token_version == 2
    assert held.token_version == 2
