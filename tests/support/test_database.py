import contextlib
import os
import socket
from urllib.parse import urlsplit

import psycopg
import pytest

from tests.support.database import (
    DEFAULT_ADMIN_URL,
    TestDatabaseUnavailableError,
    create_test_database,
    drop_test_database,
    unavailable_message,
)

ADMIN_URL = os.environ.get("TEST_DATABASE_URL", DEFAULT_ADMIN_URL)


def _db_name(url: str) -> str:
    return urlsplit(url).path.lstrip("/")


def _netloc_with_password(password: str) -> str:
    parts = urlsplit(ADMIN_URL)
    host = parts.hostname or "localhost"
    port = f":{parts.port}" if parts.port else ""
    return f"{parts.username}:{password}@{host}{port}"


def _exists(name: str) -> bool:
    with psycopg.connect(ADMIN_URL, autocommit=True) as conn:
        row = conn.execute("select 1 from pg_database where datname = %s", (name,)).fetchone()
    return row is not None


def test_creates_empty_connectable_database() -> None:
    url = create_test_database(ADMIN_URL)
    try:
        name = _db_name(url)
        assert name.startswith("project_hub_test_")
        with psycopg.connect(url) as conn:
            current = conn.execute("select current_database()").fetchone()
            tables = conn.execute(
                "select count(*) from information_schema.tables where table_schema = 'public'"
            ).fetchone()
        assert current == (name,)
        assert tables == (0,)
    finally:
        drop_test_database(ADMIN_URL, url)


def test_drop_removes_database() -> None:
    url = create_test_database(ADMIN_URL)
    drop_test_database(ADMIN_URL, url)
    assert not _exists(_db_name(url))


def test_drop_with_open_connection() -> None:
    url = create_test_database(ADMIN_URL)
    stale = psycopg.connect(url)
    try:
        drop_test_database(ADMIN_URL, url)
        assert not _exists(_db_name(url))
    finally:
        with contextlib.suppress(psycopg.Error):
            stale.close()


def test_two_databases_have_distinct_names() -> None:
    first = create_test_database(ADMIN_URL)
    second = create_test_database(ADMIN_URL)
    try:
        assert first != second
    finally:
        drop_test_database(ADMIN_URL, first)
        drop_test_database(ADMIN_URL, second)


def test_unreachable_server_raises_with_hint() -> None:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    with pytest.raises(TestDatabaseUnavailableError) as excinfo:
        create_test_database(f"postgresql://u:s3cret-pw@127.0.0.1:{port}/postgres")
    message = str(excinfo.value)
    assert message.splitlines()[0] == (
        f"Postgres is not reachable at 127.0.0.1:{port}. Start it with: docker compose up -d db"
    )
    assert "s3cret-pw" not in message


def test_wrong_password_reports_reason() -> None:
    wrong = urlsplit(ADMIN_URL)._replace(netloc=_netloc_with_password("wrong-s3cret")).geturl()
    info = urlsplit(wrong)
    with pytest.raises(TestDatabaseUnavailableError) as excinfo:
        create_test_database(wrong)
    message = str(excinfo.value)
    assert message.startswith(
        f"Postgres is not reachable at {info.hostname}:{info.port}. "
        "Start it with: docker compose up -d db\n"
    )
    assert "password authentication failed" in message
    assert "wrong-s3cret" not in message


def test_reason_redacts_password() -> None:
    message = unavailable_message("postgresql://u:s3cret-pw@h:1/postgres", reason="boom s3cret-pw")
    assert message == (
        "Postgres is not reachable at h:1. Start it with: docker compose up -d db\nReason: boom ***"
    )


def test_drop_unreachable_server_raises() -> None:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    with pytest.raises(TestDatabaseUnavailableError) as excinfo:
        drop_test_database(
            f"postgresql://u:s3cret-pw@127.0.0.1:{port}/postgres",
            f"postgresql://u:s3cret-pw@127.0.0.1:{port}/project_hub_test_abc",
        )
    assert str(excinfo.value).startswith(f"Postgres is not reachable at 127.0.0.1:{port}.")
    assert "s3cret-pw" not in str(excinfo.value)


def test_drop_refuses_non_test_database() -> None:
    with pytest.raises(ValueError, match="postgres"):
        drop_test_database(
            "postgresql://u:p@127.0.0.1:1/postgres", "postgresql://u:p@127.0.0.1:1/postgres"
        )


def test_unreachable_message_defaults_port_5432() -> None:
    message = unavailable_message("postgresql://u:s3cret-pw@db.invalid/postgres")
    assert message == (
        "Postgres is not reachable at db.invalid:5432. Start it with: docker compose up -d db"
    )
    assert "s3cret-pw" not in message


def test_database_url_fixture_gives_test_database(database_url: str) -> None:
    with psycopg.connect(database_url) as conn:
        row = conn.execute("select current_database()").fetchone()
    assert row is not None
    assert str(row[0]).startswith("project_hub_test_")
