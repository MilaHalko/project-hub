"""Create and drop a throwaway Postgres database for the test session."""

from typing import Final
from urllib.parse import urlsplit
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict

DEFAULT_ADMIN_URL: Final = "postgresql://project_hub:project_hub@localhost:55433/postgres"
TEST_DATABASE_PREFIX: Final = "project_hub_test_"
CONFIG_HINT: Final = (
    "TEST_DATABASE_URL must be a URL with an explicit TCP host and port, "
    "for example postgresql://project_hub:project_hub@localhost:55433/postgres"
)


class TestDatabaseUnavailableError(Exception):
    """The Postgres server for the test database cannot be reached."""

    __test__ = False


class TestDatabaseConfigError(Exception):
    """TEST_DATABASE_URL is unusable or the server rejected the request."""

    __test__ = False


def _validate_admin_url(admin_url: str) -> None:
    """Reject URLs libpq would resolve through a Unix socket or PG* defaults."""
    try:
        info = conninfo_to_dict(admin_url)
    except psycopg.ProgrammingError:
        raise TestDatabaseConfigError(CONFIG_HINT) from None
    host = info.get("host")
    if not host or str(host).startswith("/") or not info.get("port"):
        raise TestDatabaseConfigError(CONFIG_HINT)


def _redact(text: str, admin_url: str) -> str:
    """Strip the text and hide the URL's password in it."""
    text = text.strip()
    password = conninfo_to_dict(admin_url).get("password")
    if password:
        text = text.replace(str(password), "***")
    return text


def unavailable_message(admin_url: str, reason: str | None = None) -> str:
    """Build a hint for an unreachable server, hiding the password from the reason."""
    info = conninfo_to_dict(admin_url)
    host = info.get("host", "localhost")
    port = info.get("port", "5432")
    message = f"Postgres is not reachable at {host}:{port}. Start it with: docker compose up -d db"
    if reason is not None:
        message += f"\nReason: {_redact(reason, admin_url)}"
    return message


def _admin_execute(admin_url: str, query: sql.Composed) -> None:
    """Run one statement on the admin server, turning driver errors into hints."""
    try:
        with psycopg.connect(admin_url, autocommit=True, connect_timeout=3) as conn:
            conn.execute(query)
    except psycopg.OperationalError as err:
        raise TestDatabaseUnavailableError(unavailable_message(admin_url, str(err))) from None
    except psycopg.Error as err:
        info = conninfo_to_dict(admin_url)
        raise TestDatabaseConfigError(
            f"Postgres at {info.get('host')}:{info.get('port')} rejected the request.\n"
            f"Reason: {_redact(str(err), admin_url)}"
        ) from None


def create_test_database(admin_url: str) -> str:
    """Create an empty database on the admin server and return its URL."""
    _validate_admin_url(admin_url)
    name = f"{TEST_DATABASE_PREFIX}{uuid4().hex}"
    _admin_execute(admin_url, sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    return urlsplit(admin_url)._replace(path=f"/{name}").geturl()


def truncate_tables(database_url: str) -> None:
    """Empty every table in schema ``public`` except ``alembic_version``."""
    with psycopg.connect(database_url) as conn:
        rows = conn.execute(
            "SELECT tablename FROM pg_tables "
            "WHERE schemaname = 'public' AND tablename <> 'alembic_version'"
        ).fetchall()
        if rows:
            names = sql.SQL(", ").join(sql.Identifier("public", str(row[0])) for row in rows)
            conn.execute(sql.SQL("TRUNCATE {}").format(names))


def drop_test_database(admin_url: str, database_url: str) -> None:
    """Drop a database made by `create_test_database`, even with open connections."""
    name = urlsplit(database_url).path.lstrip("/")
    if not name.startswith(TEST_DATABASE_PREFIX):
        raise ValueError(f"Refusing to drop {name!r}: not a {TEST_DATABASE_PREFIX}* database")
    _validate_admin_url(admin_url)
    _admin_execute(
        admin_url, sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name))
    )
