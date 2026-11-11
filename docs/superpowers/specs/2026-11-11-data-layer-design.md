# Epic 1b: Data layer

Date: 2026-11-11
Status: approved design
Roadmap: [`docs/PRDs/roadmap.md`](../../PRDs/roadmap.md), epic 1b

## Goal

Give the app a swappable data layer: repository and Unit of Work protocols,
two interchangeable implementations (SQLAlchemy ORM and plain psycopg SQL)
selected by `APP_DB_BACKEND`, hand-written Alembic migrations, and one contract
test suite that runs against both implementations on real Postgres. This covers
the spec's "Creation of db with and without ORM".

## Decisions

| Area | Decision | Why |
|---|---|---|
| Entities | Only `User` (`users` table) | Exactly what epic 3 needs; projects and members come in epic 4 on the same pattern |
| Migrations | Alembic, migrations written by hand (no autogenerate) | Standard tool with history and downgrade; the roadmap requires a schema independent of ORM models |
| Running migrations in Docker | One-shot compose service `migrate`; `api` waits for it | API replicas never race on migrations; maps to a one-off ECS task in epic 8 |
| Async | SQLAlchemy 2 async (`postgresql+psycopg`) and `psycopg.AsyncConnection` from `psycopg_pool.AsyncConnectionPool` | FastAPI is async; both backends use the same driver |
| Primary keys | `uuid`, `DEFAULT gen_random_uuid()` | IDs in URLs do not reveal row counts; works on Postgres 13+ and RDS |
| Async tests | `anyio` pytest plugin | Already installed with FastAPI; no new dev dependency |
| `APP_DATABASE_URL` | Optional `SecretStr`, plain `postgresql://` form | App and existing tests still run without a database; password never shows in `repr` |

## 1. Layout

```
alembic.ini                         CLI config for developers (upgrade, downgrade, revision)
src/project_hub/
  core/config.py                    + database_url, db_backend
  db/
    base.py                         SQLAlchemy DeclarativeBase (no feature imports)
    uow.py                          UnitOfWork Protocol
    database.py                     Database Protocol, create_database(settings)
    orm.py                          OrmDatabase, OrmUnitOfWork
    sql.py                          SqlDatabase, SqlUnitOfWork
    dependencies.py                 get_uow FastAPI dependency
    migrate.py                      python -m project_hub.db.migrate → upgrade head
    migrations/env.py
    migrations/script.py.mako
    migrations/versions/0001_create_users.py
  users/
    entities.py                     User, NewUser (frozen dataclasses)
    repository.py                   UserRepository Protocol
    models.py                       UserModel (ORM; never leaves the repository)
    repository_orm.py               OrmUserRepository
    repository_sql.py               SqlUserRepository
```

- `db/` lives outside `core/` because the Unit of Work imports repositories from
  feature modules (roadmap). `core/` still never imports feature modules.
- `db/base.py` imports nothing from features, so `users/models.py` can import it
  without a cycle.
- Migrations live inside the package, so the Docker image ships them without
  `Dockerfile` changes.
- New main dependencies: `sqlalchemy[asyncio]` (2.x), `alembic`, `psycopg-pool`.

## 2. Settings

- `db_backend: Literal["orm", "sql"] = "orm"`, env `APP_DB_BACKEND`. Anything
  else (`sqll`, `ORM`, empty) is a validation error.
- `database_url: SecretStr | None = None`, env `APP_DATABASE_URL`, a plain
  `postgresql://user:pass@host:port/db` URL (the form compose already passes).
  The ORM backend converts it to `postgresql+psycopg://` internally.

## 3. Domain model and repository

```python
@dataclass(frozen=True, slots=True)
class NewUser:
    login: str
    password_hash: str

@dataclass(frozen=True, slots=True)
class User:
    id: UUID
    login: str
    password_hash: str
    created_at: datetime

class UserRepository(Protocol):
    async def add(self, user: NewUser) -> User: ...
    async def get_by_id(self, user_id: UUID) -> User | None: ...
    async def get_by_login(self, login: str) -> User | None: ...
```

- Both implementations return `User`, never ORM objects or rows.
- `add` raises `ConflictError` (from `core/exceptions.py`) when the login is
  taken. Only a violation of the `uq_users_login` constraint is translated; any
  other database error propagates unchanged.
- `add` runs the insert inside a savepoint (`session.begin_nested()` /
  nested `conn.transaction()`), so after a `ConflictError` the surrounding
  Unit of Work is still usable.
- Login validation (length, characters, case) is epic 3's job (pydantic).

## 4. Unit of Work and Database

```python
class UnitOfWork(Protocol):
    users: UserRepository
    async def commit(self) -> None: ...
    async def rollback(self) -> None: ...
    async def __aenter__(self) -> Self: ...
    async def __aexit__(self, exc_type, exc, tb) -> None: ...

class Database(Protocol):
    def unit_of_work(self) -> UnitOfWork: ...
    async def open(self) -> None: ...
    async def close(self) -> None: ...

def create_database(settings: Settings) -> Database: ...
```

Usage from a service:

```python
async with database.unit_of_work() as uow:
    user = await uow.users.add(NewUser(login="mila", password_hash="..."))
    await uow.commit()
```

- Leaving the block without `commit()` rolls back.
- An exception inside the block rolls back and propagates.
- One Unit of Work = one transaction on one session (ORM) or one pooled
  connection (SQL).
- `create_database` returns `OrmDatabase` for `orm` and `SqlDatabase` for `sql`.
  It raises `ValueError` if `database_url` is not set.
- `OrmDatabase` owns an `AsyncEngine` and an `async_sessionmaker`;
  `SqlDatabase` owns an `AsyncConnectionPool` (`open=False`, opened in `open()`).

## 5. App wiring

- `create_app` gets a lifespan: if `settings.database_url` is set, it calls
  `create_database(settings)`, `await database.open()`, stores it in
  `app.state.database`, and closes it on shutdown. Without a URL the app starts
  with no database and `/health` works.
- `get_uow` (in `db/dependencies.py`) yields an entered Unit of Work from
  `app.state.database`. Without a configured database it raises
  `RuntimeError("Database is not configured: set APP_DATABASE_URL")`, which the
  existing handler turns into a 500 (the message is logged, not sent).
- The route or service decides when to commit; `get_uow` never commits.

## 6. Migrations

- `0001_create_users`:

  | column | type |
  |---|---|
  | `id` | `uuid` primary key, `DEFAULT gen_random_uuid()` |
  | `login` | `text NOT NULL`, constraint `uq_users_login UNIQUE` |
  | `password_hash` | `text NOT NULL` |
  | `created_at` | `timestamptz NOT NULL DEFAULT now()` |

  `downgrade` drops the table.
- `migrations/env.py` has no `target_metadata` (no autogenerate). It takes the
  URL from the Alembic config if one was set programmatically, otherwise from
  `Settings().database_url`, and runs with a sync `postgresql+psycopg` engine.
- `project_hub.db.migrate`: `upgrade(database_url)` builds an Alembic `Config`
  in code (`script_location = project_hub.db:migrations`), so it needs no
  `alembic.ini`. `python -m project_hub.db.migrate` reads `Settings()`; without
  `APP_DATABASE_URL` it exits with code 1 and the message
  `APP_DATABASE_URL is not set`.
- `alembic.ini` at the repo root points at the same scripts, for developer
  commands such as `poetry run alembic downgrade -1`.

## 7. Docker

- New compose service `migrate`: `build: .`, same `APP_DATABASE_URL` as `api`,
  `command: ["python", "-m", "project_hub.db.migrate"]`, `depends_on: db`
  (`service_healthy`).
- `api` adds `depends_on: migrate` with `condition: service_completed_successfully`.
- README: migrations section, `APP_DB_BACKEND`, `APP_DATABASE_URL`, new layout
  entries. `.env.example`: `APP_DB_BACKEND` and `APP_DATABASE_URL` for local runs.

## 8. Tests

All database tests run on the real Postgres from compose, using the session
database from epic 1a (`database_url` fixture).

- Session fixture `migrated_database_url` runs `upgrade(database_url)` once.
- Fixture `database` is parametrized over `orm` and `sql`; it opens the
  backend, yields it, closes it, and truncates `users` after each test.
- Migration round-trip tests use their own throwaway database
  (`create_test_database`), so they never disturb the shared one.

## Acceptance criteria

Settings and backend choice

1. Given no `APP_DB_BACKEND`, when settings load, then `db_backend == "orm"`.
2. Given `APP_DB_BACKEND` is `orm` or `sql`, settings load with that value; given
   any other value (`sqll`, `ORM`, empty), loading raises `ValidationError`.
3. Given `APP_DATABASE_URL`, settings expose it as a secret; the password does not
   appear in `repr(settings)` or `str(settings)`.
4. Given `db_backend="orm"` / `"sql"`, `create_database` returns `OrmDatabase` /
   `SqlDatabase`; given no `database_url`, it raises `ValueError`.

Migrations

5. Given an empty database, `upgrade head` creates `users` with the columns,
   types, defaults and `uq_users_login` constraint above.
6. Given a migrated database, downgrading to `base` drops `users`, and upgrading
   again recreates it.
7. Given a migrated database, comparing it with the ORM metadata reports no
   differences.
8. `python -m project_hub.db.migrate` migrates the database from
   `APP_DATABASE_URL`; without it the command exits with code 1 and prints
   `APP_DATABASE_URL is not set`.

User repository (each test runs for both `orm` and `sql`)

9. `add` returns a `User` with a database-generated `id` and `created_at` and the
   given login and password hash.
10. `get_by_id` and `get_by_login` return the added user; an unknown id or login
    returns `None`.
11. Adding a second user with the same login raises `ConflictError`; afterwards a
    different user can still be added and committed in the same Unit of Work.
12. Every repository method returns instances of exactly `User` (not ORM objects).

Unit of Work (each test runs for both `orm` and `sql`)

13. Data committed in one Unit of Work is visible in a new one.
14. Leaving a Unit of Work without `commit()` persists nothing.
15. An exception raised inside a Unit of Work rolls it back and propagates.

App

16. Given no `APP_DATABASE_URL`, the app starts and `GET /health` returns 200.
17. Given `APP_DATABASE_URL` and a backend, the app opens the database on startup,
    a route using `Depends(get_uow)` gets a working Unit of Work of that backend,
    and the database is closed on shutdown.

Docker (opt-in `docker` marker, as in epic 1a)

18. `docker compose up` runs `migrate` to successful completion before `api`
    starts; the `users` table exists and `/health` returns 200.

## Out of scope

Registration, login, password hashing and endpoints (epic 3); projects and
members (epic 4); CI (epic 2).
