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
from project_hub.documents.models import DocumentModel
from project_hub.projects.models import ProjectMemberModel, ProjectModel
from project_hub.shares.models import ShareModel
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
    assert _fetchall(fresh_database_url, "select version_num from alembic_version") == [("0007",)]


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


def _columns(url: str, table: str) -> set[tuple[object, ...]]:
    with psycopg.connect(url) as conn:
        rows = conn.execute(
            "select column_name, data_type, is_nullable from information_schema.columns "
            "where table_schema = 'public' and table_name = %s",
            (table,),
        ).fetchall()
    return set(rows)


def _exists(url: str, table: str) -> bool:
    with psycopg.connect(url) as conn:
        row = conn.execute("select to_regclass(%s) is not null", (f"public.{table}",)).fetchone()
    assert row is not None
    return row[0] is True


def test_upgrade_creates_projects_tables(fresh_database_url: str) -> None:
    upgrade(fresh_database_url)

    assert _columns(fresh_database_url, "projects") == {
        ("id", "uuid", "NO"),
        ("owner_id", "uuid", "NO"),
        ("name", "text", "NO"),
        ("description", "text", "NO"),
        ("created_at", "timestamp with time zone", "NO"),
        ("updated_at", "timestamp with time zone", "NO"),
        ("storage_used_bytes", "bigint", "NO"),
        ("storage_counted_at", "timestamp with time zone", "YES"),
    }
    assert _columns(fresh_database_url, "project_members") == {
        ("project_id", "uuid", "NO"),
        ("user_id", "uuid", "NO"),
        ("created_at", "timestamp with time zone", "NO"),
    }
    indexes = {
        row[0]
        for row in _fetchall(
            fresh_database_url, "select indexname from pg_indexes where schemaname = 'public'"
        )
    }
    assert {"ix_projects_owner_id", "ix_project_members_user_id"} <= indexes
    constraints = {
        row[0] for row in _fetchall(fresh_database_url, "select conname from pg_constraint")
    }
    assert {
        "fk_projects_owner_id_users",
        "ck_projects_name_length",
        "ck_projects_description_length",
        "fk_project_members_project_id_projects",
        "fk_project_members_user_id_users",
        "pk_project_members",
    } <= constraints


def test_projects_constraints_reject_bad_rows(fresh_database_url: str) -> None:
    upgrade(fresh_database_url)
    with psycopg.connect(fresh_database_url, autocommit=True) as conn:
        owner = conn.execute(
            "insert into users (login, password_hash) values ('mila', 'h') returning id"
        ).fetchone()
        member = conn.execute(
            "insert into users (login, password_hash) values ('anna', 'h') returning id"
        ).fetchone()
        assert owner is not None
        assert member is not None
        for name in ("x" * 101, ""):
            with pytest.raises(psycopg.errors.CheckViolation):
                conn.execute(
                    "insert into projects (owner_id, name) values (%s, %s)", (owner[0], name)
                )
        project = conn.execute(
            "insert into projects (owner_id, name) values (%s, 'Diploma') returning id",
            (owner[0],),
        ).fetchone()
        assert project is not None
        conn.execute(
            "insert into project_members (project_id, user_id) values (%s, %s)",
            (project[0], member[0]),
        )
        with pytest.raises(psycopg.errors.RestrictViolation):
            conn.execute("delete from users where id = %s", (owner[0],))

        conn.execute("delete from users where id = %s", (member[0],))
        row = conn.execute("select count(*) from project_members").fetchone()
        assert row == (0,)

        other = conn.execute(
            "insert into users (login, password_hash) values ('bob', 'h') returning id"
        ).fetchone()
        assert other is not None
        conn.execute(
            "insert into project_members (project_id, user_id) values (%s, %s)",
            (project[0], other[0]),
        )
        row = conn.execute("select count(*) from project_members").fetchone()
        assert row == (1,)
        conn.execute("delete from projects where id = %s", (project[0],))

        row = conn.execute("select count(*) from project_members").fetchone()
    assert row == (0,)


def test_downgrade_to_0002_drops_projects(fresh_database_url: str) -> None:
    upgrade(fresh_database_url)

    downgrade(fresh_database_url, "0002")

    assert not _exists(fresh_database_url, "projects")
    assert not _exists(fresh_database_url, "project_members")
    assert _users_exists(fresh_database_url)


def test_upgrade_creates_documents_table(fresh_database_url: str) -> None:
    upgrade(fresh_database_url)

    assert _columns(fresh_database_url, "documents") == {
        ("id", "uuid", "NO"),
        ("project_id", "uuid", "NO"),
        ("name", "text", "NO"),
        ("content_type", "text", "NO"),
        ("size", "bigint", "NO"),
        ("storage_key", "text", "NO"),
        ("uploaded_by", "uuid", "YES"),
        ("created_at", "timestamp with time zone", "NO"),
        ("updated_at", "timestamp with time zone", "NO"),
    }
    indexes = _fetchall(
        fresh_database_url,
        "select indexdef from pg_indexes "
        "where schemaname = 'public' and indexname = 'ix_documents_project_id'",
    )
    assert len(indexes) == 1
    assert str(indexes[0][0]).endswith("(project_id)")
    constraints = set(
        _fetchall(
            fresh_database_url,
            "select conname, contype, confdeltype from pg_constraint "
            "where conrelid = 'public.documents'::regclass and contype in ('f', 'c', 'u')",
        )
    )
    assert constraints == {
        ("fk_documents_project_id_projects", "f", "c"),
        ("fk_documents_uploaded_by_users", "f", "n"),
        ("ck_documents_name_length", "c", " "),
        ("ck_documents_content_type", "c", " "),
        ("ck_documents_size_positive", "c", " "),
        ("uq_documents_storage_key", "u", " "),
    }


PDF_TYPE = "application/pdf"


def test_documents_constraints_reject_bad_rows(fresh_database_url: str) -> None:
    upgrade(fresh_database_url)
    with psycopg.connect(fresh_database_url, autocommit=True) as conn:
        user = conn.execute(
            "insert into users (login, password_hash) values ('mila', 'h') returning id"
        ).fetchone()
        assert user is not None
        project = conn.execute(
            "insert into projects (owner_id, name) values (%s, 'Diploma') returning id",
            (user[0],),
        ).fetchone()
        assert project is not None

        def insert(name: str, content_type: str, size: int, key: str) -> None:
            conn.execute(
                "insert into documents "
                "(project_id, name, content_type, size, storage_key, uploaded_by) "
                "values (%s, %s, %s, %s, %s, %s)",
                (project[0], name, content_type, size, key, user[0]),
            )

        insert("a.pdf", PDF_TYPE, 1, "k")
        for name, content_type, size in (
            ("", PDF_TYPE, 1),
            ("x" * 256, PDF_TYPE, 1),
            ("a.txt", "text/plain", 1),
            ("a.pdf", PDF_TYPE, 0),
        ):
            with pytest.raises(psycopg.errors.CheckViolation):
                insert(name, content_type, size, "other")
        with pytest.raises(psycopg.errors.UniqueViolation):
            insert("b.pdf", PDF_TYPE, 1, "k")
        insert("x" * 255, PDF_TYPE, 1, "longest")

        row = conn.execute("select count(*) from documents").fetchone()
    assert row == (2,)


def test_downgrade_to_0003_drops_documents(fresh_database_url: str) -> None:
    upgrade(fresh_database_url)

    downgrade(fresh_database_url, "0003")

    assert not _exists(fresh_database_url, "documents")
    assert _exists(fresh_database_url, "projects")
    upgrade(fresh_database_url)
    assert _exists(fresh_database_url, "documents")


def test_upgrade_creates_project_shares_table(fresh_database_url: str) -> None:
    upgrade(fresh_database_url)

    assert _columns(fresh_database_url, "project_shares") == {
        ("id", "uuid", "NO"),
        ("project_id", "uuid", "NO"),
        ("email", "text", "NO"),
        ("token_hash", "text", "NO"),
        ("expires_at", "timestamp with time zone", "NO"),
        ("created_at", "timestamp with time zone", "NO"),
    }
    constraints = set(
        _fetchall(
            fresh_database_url,
            "select conname, contype, confdeltype from pg_constraint "
            "where conrelid = 'public.project_shares'::regclass and contype in ('f', 'c', 'u')",
        )
    )
    assert constraints == {
        ("fk_project_shares_project_id_projects", "f", "c"),
        ("uq_project_shares_project_id_email", "u", " "),
        ("uq_project_shares_token_hash", "u", " "),
        ("ck_project_shares_email_length", "c", " "),
        ("ck_project_shares_token_hash_format", "c", " "),
    }


def test_project_shares_constraints_reject_bad_rows(fresh_database_url: str) -> None:
    upgrade(fresh_database_url)
    with psycopg.connect(fresh_database_url, autocommit=True) as conn:
        user = conn.execute(
            "insert into users (login, password_hash) values ('mila', 'h') returning id"
        ).fetchone()
        assert user is not None
        project = conn.execute(
            "insert into projects (owner_id, name) values (%s, 'Diploma') returning id",
            (user[0],),
        ).fetchone()
        assert project is not None

        def insert(email: str, token_hash: str) -> None:
            conn.execute(
                "insert into project_shares (project_id, email, token_hash, expires_at) "
                "values (%s, %s, %s, now())",
                (project[0], email, token_hash),
            )

        insert("a@example.com", "a" * 64)
        for email, token_hash in (
            ("ab", "b" * 64),
            ("x" * 243 + "@example.com", "b" * 64),
            ("b@example.com", "A" * 64),
            ("b@example.com", "b" * 63),
            ("b@example.com", "g" * 64),
        ):
            with pytest.raises(psycopg.errors.CheckViolation):
                insert(email, token_hash)
        with pytest.raises(psycopg.errors.UniqueViolation):
            insert("a@example.com", "b" * 64)
        with pytest.raises(psycopg.errors.UniqueViolation):
            insert("b@example.com", "a" * 64)
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            conn.execute(
                "insert into project_shares (project_id, email, token_hash, expires_at) "
                "values (gen_random_uuid(), 'c@example.com', %s, now())",
                ("c" * 64,),
            )
        insert("b@example.com", "b" * 64)
        conn.execute("delete from projects where id = %s", (project[0],))

        row = conn.execute("select count(*) from project_shares").fetchone()
    assert row == (0,)


def test_downgrade_to_0004_drops_project_shares(fresh_database_url: str) -> None:
    upgrade(fresh_database_url)

    downgrade(fresh_database_url, "0004")

    assert not _exists(fresh_database_url, "project_shares")
    assert _exists(fresh_database_url, "documents")
    upgrade(fresh_database_url)
    assert _exists(fresh_database_url, "project_shares")


def test_0006_backfills_storage_used(fresh_database_url: str) -> None:
    upgrade(fresh_database_url, "0005")
    with psycopg.connect(fresh_database_url, autocommit=True) as conn:
        user = conn.execute(
            "insert into users (login, password_hash) values ('mila', 'h') returning id"
        ).fetchone()
        assert user is not None
        project_ids: dict[str, object] = {}
        for name in ("Full", "Empty"):
            row = conn.execute(
                "insert into projects (owner_id, name) values (%s, %s) returning id",
                (user[0], name),
            ).fetchone()
            assert row is not None
            project_ids[name] = row[0]
        full, empty = project_ids["Full"], project_ids["Empty"]
        for key, size in (("k1", 100), ("k2", 250)):
            conn.execute(
                "insert into documents "
                "(project_id, name, content_type, size, storage_key, uploaded_by) "
                "values (%s, %s, %s, %s, %s, %s)",
                (full, f"{key}.pdf", PDF_TYPE, size, key, user[0]),
            )

    upgrade(fresh_database_url)

    with psycopg.connect(fresh_database_url) as conn:
        rows = {
            row[0]: row[1:]
            for row in conn.execute(
                "select id, storage_used_bytes, storage_counted_at is not null from projects"
            ).fetchall()
        }
    assert rows[full] == (350, True)
    assert rows[empty] == (0, True)


def test_storage_used_rejects_negative(fresh_database_url: str) -> None:
    upgrade(fresh_database_url)
    with psycopg.connect(fresh_database_url, autocommit=True) as conn:
        user = conn.execute(
            "insert into users (login, password_hash) values ('mila', 'h') returning id"
        ).fetchone()
        assert user is not None
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(
                "insert into projects (owner_id, name, storage_used_bytes) "
                "values (%s, 'Diploma', -1)",
                (user[0],),
            )


def test_downgrade_to_0005_drops_storage_columns(fresh_database_url: str) -> None:
    upgrade(fresh_database_url)

    downgrade(fresh_database_url, "0005")

    names = {row[0] for row in _columns(fresh_database_url, "projects")}
    assert "storage_used_bytes" not in names
    assert "storage_counted_at" not in names
    upgrade(fresh_database_url)
    names = {row[0] for row in _columns(fresh_database_url, "projects")}
    assert {"storage_used_bytes", "storage_counted_at"} <= names


def test_orm_metadata_matches_migrated_schema(fresh_database_url: str) -> None:
    upgrade(fresh_database_url)
    assert UserModel.__tablename__ in Base.metadata.tables
    assert ProjectModel.__tablename__ in Base.metadata.tables
    assert ProjectMemberModel.__tablename__ in Base.metadata.tables
    assert DocumentModel.__tablename__ in Base.metadata.tables
    assert ShareModel.__tablename__ in Base.metadata.tables
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


DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _insert_document(url: str, content_type: str, key: str) -> None:
    with psycopg.connect(url, autocommit=True) as conn:
        row = conn.execute("select id from users where login = 'mila'").fetchone()
        if row is None:
            row = conn.execute(
                "insert into users (login, password_hash) values ('mila', 'h') returning id"
            ).fetchone()
        assert row is not None
        project = conn.execute("select id from projects").fetchone()
        if project is None:
            project = conn.execute(
                "insert into projects (owner_id, name) values (%s, 'Diploma') returning id",
                (row[0],),
            ).fetchone()
        assert project is not None
        conn.execute(
            "insert into documents "
            "(project_id, name, content_type, size, storage_key, uploaded_by) "
            "values (%s, 'f', %s, 1, %s, %s)",
            (project[0], content_type, key, row[0]),
        )


def test_0007_accepts_image_content_types(fresh_database_url: str) -> None:
    upgrade(fresh_database_url)

    for index, content_type in enumerate((PDF_TYPE, DOCX_TYPE, "image/jpeg", "image/png")):
        _insert_document(fresh_database_url, content_type, f"k{index}")
    with pytest.raises(psycopg.errors.CheckViolation):
        _insert_document(fresh_database_url, "image/gif", "gif")

    assert _fetchall(fresh_database_url, "select count(*) from documents") == [(4,)]


def test_0006_rejects_image_content_types(fresh_database_url: str) -> None:
    upgrade(fresh_database_url, "0006")

    with pytest.raises(psycopg.errors.CheckViolation):
        _insert_document(fresh_database_url, "image/png", "k")


def test_downgrade_to_0006_restores_old_constraint(fresh_database_url: str) -> None:
    upgrade(fresh_database_url)
    _insert_document(fresh_database_url, PDF_TYPE, "k")

    downgrade(fresh_database_url, "0006")

    assert _fetchall(fresh_database_url, "select version_num from alembic_version") == [("0006",)]
    with pytest.raises(psycopg.errors.CheckViolation):
        _insert_document(fresh_database_url, "image/png", "img")
    _insert_document(fresh_database_url, DOCX_TYPE, "docx")
    upgrade(fresh_database_url)
    _insert_document(fresh_database_url, "image/png", "img")


def test_downgrade_to_0006_with_image_rows_fails_and_deletes_nothing(
    fresh_database_url: str,
) -> None:
    upgrade(fresh_database_url)
    _insert_document(fresh_database_url, PDF_TYPE, "k1")
    _insert_document(fresh_database_url, "image/png", "k2")

    with pytest.raises(Exception, match="ck_documents_content_type"):
        downgrade(fresh_database_url, "0006")

    assert _fetchall(fresh_database_url, "select version_num from alembic_version") == [("0007",)]
    assert _fetchall(fresh_database_url, "select count(*) from documents") == [(2,)]
    _insert_document(fresh_database_url, "image/jpeg", "k3")
