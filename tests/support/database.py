"""Create and drop a throwaway Postgres database for the test session."""

from typing import Final
from urllib.parse import urlsplit
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict

DEFAULT_ADMIN_URL: Final = "postgresql://project_hub:project_hub@localhost:55433/postgres"
TEST_DATABASE_PREFIX: Final = "project_hub_test_"


class TestDatabaseUnavailableError(Exception):
    """The Postgres server for the test database cannot be reached."""

    __test__ = False


def unavailable_message(admin_url: str, reason: str | None = None) -> str:
    """Build a hint for an unreachable server, hiding the password from the reason."""
    info = conninfo_to_dict(admin_url)
    host = info.get("host", "localhost")
    port = info.get("port", "5432")
    message = f"Postgres is not reachable at {host}:{port}. Start it with: docker compose up -d db"
    if reason is not None:
        text = reason.strip()
        password = info.get("password")
        if password:
            text = text.replace(str(password), "***")
        message += f"\nReason: {text}"
    return message


def create_test_database(admin_url: str) -> str:
    """Create an empty database on the admin server and return its URL."""
    name = f"{TEST_DATABASE_PREFIX}{uuid4().hex}"
    try:
        with psycopg.connect(admin_url, autocommit=True, connect_timeout=3) as conn:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    except psycopg.OperationalError as err:
        raise TestDatabaseUnavailableError(unavailable_message(admin_url, str(err))) from None
    return urlsplit(admin_url)._replace(path=f"/{name}").geturl()


def drop_test_database(admin_url: str, database_url: str) -> None:
    """Drop a database made by `create_test_database`, even with open connections."""
    name = urlsplit(database_url).path.lstrip("/")
    if not name.startswith(TEST_DATABASE_PREFIX):
        raise ValueError(f"Refusing to drop {name!r}: not a {TEST_DATABASE_PREFIX}* database")
    try:
        with psycopg.connect(admin_url, autocommit=True, connect_timeout=3) as conn:
            conn.execute(
                sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name))
            )
    except psycopg.OperationalError as err:
        raise TestDatabaseUnavailableError(unavailable_message(admin_url, str(err))) from None
