import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import LiteralString

import psycopg
import pytest
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine

from project_hub.db.base import Base
from project_hub.db.migrate import downgrade, upgrade
from project_hub.db.urls import sqlalchemy_url
from project_hub.users.models import UserModel
from tests.support.database import DEFAULT_ADMIN_URL, create_test_database, drop_test_database


@pytest.fixture
def fresh_database_url() -> Iterator[str]:
    admin_url = os.environ.get("TEST_DATABASE_URL", DEFAULT_ADMIN_URL)
    url = create_test_database(admin_url)
    try:
        yield url
    finally:
        drop_test_database(admin_url, url)


def _fetchall(url: str, query: LiteralString) -> list[tuple[object, ...]]:
    with psycopg.connect(url) as conn:
        return conn.execute(query).fetchall()


def _users_exists(url: str) -> bool:
    rows = _fetchall(url, "select to_regclass('public.users') is not null")
    return rows[0][0] is True


def _cli_env(**extra: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("APP_")}
    env.update(extra)
    return env


def _run_cli(tmp_path: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "project_hub.db.migrate"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_upgrade_creates_users_table(fresh_database_url: str) -> None:
    upgrade(fresh_database_url)

    columns = _fetchall(
        fresh_database_url,
        "select column_name, data_type, is_nullable from information_schema.columns "
        "where table_schema = 'public' and table_name = 'users'",
    )
    assert set(columns) == {
        ("id", "uuid", "NO"),
        ("login", "text", "NO"),
        ("password_hash", "text", "NO"),
        ("created_at", "timestamp with time zone", "NO"),
        ("token_version", "integer", "NO"),
    }
    constraints = _fetchall(
        fresh_database_url,
        "select conname from pg_constraint where conrelid = 'public.users'::regclass "
        "and contype = 'u'",
    )
    assert constraints == [("uq_users_login",)]
    with psycopg.connect(fresh_database_url) as conn:
        row = conn.execute(
            "insert into users (login, password_hash) values ('a', 'h') returning id, created_at"
        ).fetchone()
    assert row is not None
    assert row[0] is not None
    assert row[1] is not None


def test_downgrade_then_upgrade_round_trip(fresh_database_url: str) -> None:
    upgrade(fresh_database_url)
    downgrade(fresh_database_url)
    assert not _users_exists(fresh_database_url)
    upgrade(fresh_database_url)
    assert _users_exists(fresh_database_url)


def test_upgrade_twice_is_noop(fresh_database_url: str) -> None:
    upgrade(fresh_database_url)
    upgrade(fresh_database_url)
    assert _fetchall(fresh_database_url, "select version_num from alembic_version") == [("0002",)]


def _users_columns(url: str) -> set[object]:
    rows = _fetchall(
        url,
        "select column_name from information_schema.columns "
        "where table_schema = 'public' and table_name = 'users'",
    )
    return {row[0] for row in rows}


def test_token_version_defaults_to_zero_for_existing_rows(fresh_database_url: str) -> None:
    upgrade(fresh_database_url, "0001")
    with psycopg.connect(fresh_database_url) as conn:
        conn.execute("insert into users (login, password_hash) values ('old', 'h')")

    upgrade(fresh_database_url)

    rows = _fetchall(fresh_database_url, "select token_version from users where login = 'old'")
    assert rows == [(0,)]


def test_downgrade_to_0001_drops_token_version(fresh_database_url: str) -> None:
    upgrade(fresh_database_url)
    assert "token_version" in _users_columns(fresh_database_url)

    downgrade(fresh_database_url, "0001")

    assert _users_exists(fresh_database_url)
    assert "token_version" not in _users_columns(fresh_database_url)


def test_orm_metadata_matches_migrated_schema(fresh_database_url: str) -> None:
    upgrade(fresh_database_url)
    assert UserModel.__tablename__ in Base.metadata.tables
    engine = create_engine(sqlalchemy_url(fresh_database_url))
    try:
        with engine.connect() as conn:
            diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    finally:
        engine.dispose()
    assert diff == []


def test_migrate_cli_applies_migrations(fresh_database_url: str, tmp_path: Path) -> None:
    result = _run_cli(tmp_path, _cli_env(APP_DATABASE_URL=fresh_database_url))
    assert result.returncode == 0, result.stderr
    assert _users_exists(fresh_database_url)


def test_migrate_cli_without_url_fails(tmp_path: Path) -> None:
    result = _run_cli(tmp_path, _cli_env())
    assert result.returncode == 1
    assert "APP_DATABASE_URL is not set" in result.stderr
