import sys

from alembic import command
from alembic.config import Config
from pydantic import ValidationError

from project_hub.core.config import Settings
from project_hub.db.urls import sqlalchemy_url

_SCRIPT_LOCATION = "project_hub.db:migrations"


def _config(database_url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", _SCRIPT_LOCATION)
    # ConfigParser interpolation: a literal "%" in the URL must be doubled.
    config.set_main_option("sqlalchemy.url", sqlalchemy_url(database_url).replace("%", "%%"))
    return config


def upgrade(database_url: str, revision: str = "head") -> None:
    command.upgrade(_config(database_url), revision)


def downgrade(database_url: str, revision: str = "base") -> None:
    command.downgrade(_config(database_url), revision)


def main() -> int:
    try:
        url = Settings().database_url
    except ValidationError as err:
        print(f"Invalid settings: {err}", file=sys.stderr)
        return 1
    if url is None:
        print("APP_DATABASE_URL is not set", file=sys.stderr)
        return 1
    upgrade(url.get_secret_value())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
