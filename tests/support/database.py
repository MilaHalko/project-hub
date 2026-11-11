"""Create and drop a throwaway Postgres database for the test session."""

from typing import Final
from urllib.parse import urlsplit
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict

DEFAULT_ADMIN_URL: Final = "postgresql://project_hub:project_hub@localhost:55433/postgres"


class TestDatabaseUnavailableError(Exception):
    """The Postgres server for the test database cannot be reached."""

    __test__ = False


def unavailable_message(admin_url: str) -> str:
    """Build a hint for an unreachable server without exposing credentials."""
    info = conninfo_to_dict(admin_url)
    host = info.get("host", "localhost")
    port = info.get("port", "5432")
    return f"Postgres is not reachable at {host}:{port}. Start it with: docker compose up -d db"


def create_test_database(admin_url: str) -> str:
    """Create an empty database on the admin server and return its URL."""
    name = f"project_hub_test_{uuid4().hex}"
    try:
        with psycopg.connect(admin_url, autocommit=True, connect_timeout=3) as conn:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    except psycopg.OperationalError:
        raise TestDatabaseUnavailableError(unavailable_message(admin_url)) from None
    return urlsplit(admin_url)._replace(path=f"/{name}").geturl()


def drop_test_database(admin_url: str, database_url: str) -> None:
    """Drop a database made by `create_test_database`, even with open connections."""
    name = urlsplit(database_url).path.lstrip("/")
    with psycopg.connect(admin_url, autocommit=True, connect_timeout=3) as conn:
        conn.execute(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name))
        )
