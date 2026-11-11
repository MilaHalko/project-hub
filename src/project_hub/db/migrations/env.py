from alembic import context
from sqlalchemy import create_engine, pool

from project_hub.core.config import Settings
from project_hub.db.urls import sqlalchemy_url

config = context.config
target_metadata = None


def _database_url() -> str:
    url = config.get_main_option("sqlalchemy.url")
    if url:
        return url
    settings_url = Settings().database_url
    if settings_url is None:
        raise RuntimeError("APP_DATABASE_URL is not set")
    return sqlalchemy_url(settings_url.get_secret_value())


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_database_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
