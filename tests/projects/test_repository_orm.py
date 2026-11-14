from collections.abc import AsyncIterator

import psycopg
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from project_hub.db.urls import sqlalchemy_url
from project_hub.projects.entities import NewProject
from project_hub.projects.models import ProjectModel
from project_hub.projects.repository_orm import OrmProjectRepository
from project_hub.users.entities import NewUser
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


async def test_update_refreshes_a_stale_model_held_in_the_session(
    session: AsyncSession, migrated_database_url: str
) -> None:
    owner = await OrmUserRepository(session).add(NewUser("mila", "hash"))
    repo = OrmProjectRepository(session)
    added = await repo.add(NewProject(owner.id, "Diploma", "Old"))
    await session.commit()
    held = await session.get(ProjectModel, added.id)
    assert held is not None
    assert held.created_at == added.created_at
    with psycopg.connect(migrated_database_url) as other:
        row = other.execute(
            "UPDATE projects SET created_at = created_at - interval '1 day' "
            "WHERE id = %s RETURNING created_at",
            (added.id,),
        ).fetchone()
    assert row is not None
    db_created_at = row[0]
    assert db_created_at != added.created_at

    updated = await repo.update(added.id, "Thesis", "New")

    assert updated is not None
    assert updated.created_at == db_created_at
    assert held.created_at == db_created_at
