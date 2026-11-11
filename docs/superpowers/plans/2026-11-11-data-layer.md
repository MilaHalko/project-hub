# Epic 1b: Data Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A swappable data layer: `UserRepository` and `UnitOfWork` protocols with SQLAlchemy ORM and plain psycopg SQL implementations, chosen by `APP_DB_BACKEND`, hand-written Alembic migrations, shared contract tests on real Postgres.

**Architecture:** Feature code sees only protocols and the frozen `User` dataclass. `project_hub/db/` holds the Unit of Work, the two `Database` backends, the factory, the FastAPI dependency and the migrations; `project_hub/users/` holds the entity, the repository protocol, the ORM model and both repository implementations. One contract test suite is parametrized over `orm` and `sql`.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2.1 async (`postgresql+psycopg`), psycopg 3.3 + psycopg-pool 3.3, Alembic 1.20, pytest with the `anyio` plugin, Postgres 18 from docker compose.

**Spec:** [`docs/superpowers/specs/2026-11-11-data-layer-design.md`](../specs/2026-11-11-data-layer-design.md)

## Global Constraints

- Tooling: `poetry run ruff check`, `poetry run ruff format --check`, `poetry run pyright` (strict, covers `src` and `tests`), `poetry run pytest`. All must stay green after every task.
- Dependencies go in `[project].dependencies` in PEP 621 style, like the existing `"psycopg[binary] (>=3.2)"`: add `"sqlalchemy[asyncio] (>=2.1,<3)"`, `"alembic (>=1.20,<2)"`, `"psycopg-pool (>=3.3,<4)"`, then `poetry lock` and `poetry install`. No new dev dependencies.
- Async tests use `@pytest.mark.anyio` (plugin ships with anyio); the default `anyio_backend` is asyncio.
- Database tests need `docker compose up -d --wait db`. They use the 1a session fixture `database_url` (plain `postgresql://` URL). Never mock the database.
- `core/` never imports `db/` or feature modules. ORM objects and psycopg rows never leave a repository.
- Constraint name `uq_users_login`; table `users`; columns `id uuid PK DEFAULT gen_random_uuid()`, `login text NOT NULL`, `password_hash text NOT NULL`, `created_at timestamptz NOT NULL DEFAULT now()`.
- Error message strings, verbatim: `APP_DATABASE_URL is not set` (migrate CLI), `Database is not configured: set APP_DATABASE_URL` (`get_uow`).
- Commits: plain messages, **no `Co-Authored-By` trailer and no Claude attribution**.
- Never modify, weaken or delete existing tests without asking the user. Adding env keys to the autouse `_clean_env` fixture is allowed (it only strengthens isolation).

## Review Focus

1. `APP_DATABASE_URL` in `postgres://` form (common on hosting platforms) must work on both backends → Task 1 tests `sqlalchemy_url("postgres://…")`.
2. Login case: at the data layer `"Mila"` and `"mila"` are different users on both backends (normalization is epic 3) → Task 3 contract test.
3. Two Unit of Work instances open at once must not share a transaction: uncommitted data in one is invisible to the other → Task 3 contract test.
4. `migrate` runs on every `docker compose up`, so `upgrade` on an already migrated database must be a no-op → Task 2 test.
5. An unreachable database must make `Database.open()` fail within seconds, not hang app startup → Task 4 contract test (both backends).

---

### Task 1: Settings and URL helper

AC 1, 2, 3; Review Focus 1.

**Files:**
- Modify: `pyproject.toml`, `poetry.lock` (add the three dependencies)
- Modify: `src/project_hub/core/config.py`
- Create: `src/project_hub/db/__init__.py`, `src/project_hub/db/urls.py`
- Modify: `tests/conftest.py` (`_clean_env` also deletes `APP_DB_BACKEND`, `APP_DATABASE_URL`)
- Modify: `.env.example` (document `APP_DB_BACKEND=orm` and a commented local `APP_DATABASE_URL=postgresql://project_hub:project_hub@localhost:55433/project_hub`)
- Test: `tests/test_config.py` (add tests), `tests/db/__init__.py`, `tests/db/test_urls.py`

**Interfaces:**
- Produces: `project_hub.core.config.DbBackend = Literal["orm", "sql"]`; `Settings.db_backend: DbBackend = "orm"`; `Settings.database_url: SecretStr | None = None`.
- Produces: `project_hub.db.urls.sqlalchemy_url(url: str) -> str`.

- [ ] **Step 1: Write failing tests**

`tests/test_config.py`:
- `test_db_backend_defaults_to_orm`: `IsolatedSettings().db_backend == "orm"`.
- `test_db_backend_accepts_known_values` (parametrize `"orm"`, `"sql"`): env `APP_DB_BACKEND` → same value.
- `test_db_backend_rejects_unknown_values` (parametrize `"sqll"`, `"ORM"`, `""`): `pytest.raises(ValidationError)`.
- `test_database_url_defaults_to_none`: `IsolatedSettings().database_url is None`.
- `test_database_url_is_secret`: env `APP_DATABASE_URL=postgresql://u:s3cret@h:5432/d` → `get_secret_value()` equals it; `"s3cret"` not in `repr(s)` nor `str(s)`.

`tests/db/test_urls.py`, `test_sqlalchemy_url` parametrized:

| input | expected |
|---|---|
| `postgresql://u:p@h:5432/d` | `postgresql+psycopg://u:p@h:5432/d` |
| `postgres://u:p@h:5432/d` | `postgresql+psycopg://u:p@h:5432/d` |
| `postgresql+psycopg://u:p@h:5432/d` | unchanged |

and `test_sqlalchemy_url_rejects_other_schemes`: `mysql://h/d` → `ValueError`.

- [ ] **Step 2: Run, expect failures** — `poetry run pytest tests/test_config.py tests/db/test_urls.py -v` → new tests FAIL (missing attributes / module).
- [ ] **Step 3: Add dependencies, fields and `sqlalchemy_url`** — replace only the scheme part before `://`.
- [ ] **Step 4: Run, expect pass**, plus ruff and pyright clean.
- [ ] **Step 5: Commit** — `git commit -m "Add database settings and SQLAlchemy URL helper"`

---

### Task 2: Entity, ORM model, migration 0001 and migrate CLI

AC 5, 6, 7, 8; Review Focus 4.

**Files:**
- Create: `src/project_hub/users/__init__.py`, `users/entities.py`, `users/repository.py`, `users/models.py`
- Create: `src/project_hub/db/base.py`, `db/migrate.py`, `db/migrations/env.py`, `db/migrations/script.py.mako`, `db/migrations/versions/0001_create_users.py`
- Create: `alembic.ini` (repo root; `script_location = %(here)s/src/project_hub/db/migrations`, no URL in the file)
- Modify: `tests/conftest.py` (session fixture `migrated_database_url`)
- Modify: `tests/support/database.py` (add `truncate_tables`)
- Test: `tests/db/test_migrations.py`, `tests/support/test_database.py` (add a test for `truncate_tables`)

**Interfaces:**
- Consumes: `sqlalchemy_url`, `Settings` (Task 1).
- Produces:
  - `project_hub.users.entities`: `@dataclass(frozen=True, slots=True) class NewUser(login: str, password_hash: str)`; `@dataclass(frozen=True, slots=True) class User(id: UUID, login: str, password_hash: str, created_at: datetime)`.
  - `project_hub.users.repository.UserRepository(Protocol)`: `async add(user: NewUser) -> User`, `async get_by_id(user_id: UUID) -> User | None`, `async get_by_login(login: str) -> User | None`. Docstring: `add` raises `ConflictError` on a taken login.
  - `project_hub.db.base.Base(DeclarativeBase)` — imports nothing from features.
  - `project_hub.users.models.UserModel(Base)`, `__tablename__ = "users"`, types `Uuid`, `Text`, `DateTime(timezone=True)`, `server_default`s matching the migration, `UniqueConstraint("login", name="uq_users_login")`, `__mapper_args__ = {"eager_defaults": True}` so an insert returns `id` and `created_at`.
  - `project_hub.db.migrate`: `upgrade(database_url: str, revision: str = "head") -> None`, `downgrade(database_url: str, revision: str = "base") -> None`, `main() -> int`; `if __name__ == "__main__": raise SystemExit(main())`.
  - Fixture `migrated_database_url(database_url: str) -> str` (session scope, calls `upgrade` once).
  - `tests.support.database.truncate_tables(database_url: str) -> None` — truncates every table in schema `public` except `alembic_version` (identifiers via `psycopg.sql.Identifier`).

`migrate` builds `alembic.config.Config()` in code with `script_location = "project_hub.db:migrations"` and `sqlalchemy.url = sqlalchemy_url(database_url)`. `env.py` has `target_metadata = None`, reads `sqlalchemy.url` from the config, falls back to `Settings().database_url`, and runs online with a sync engine (`NullPool`). The migration uses `op.create_table` / `op.drop_table` (no autogenerate).

- [ ] **Step 1: Write failing tests** in `tests/db/test_migrations.py`. Each test creates its own database with `create_test_database(admin_url)` and drops it in `finally` (use a small fixture `fresh_database_url`), so the shared session DB is untouched.
  - `test_upgrade_creates_users_table`: after `upgrade(url)`, `information_schema.columns` for `users` gives exactly `{("id","uuid","NO"), ("login","text","NO"), ("password_hash","text","NO"), ("created_at","timestamp with time zone","NO")}`; `pg_constraint` has a unique constraint `uq_users_login`; inserting a row with only `login` and `password_hash` fills `id` and `created_at`.
  - `test_downgrade_then_upgrade_round_trip`: `upgrade` → `downgrade(url)` → `to_regclass('public.users') IS NULL` → `upgrade` → table exists.
  - `test_upgrade_twice_is_noop`: `upgrade(url)` twice raises nothing, `alembic_version` has one row `0001`.
  - `test_orm_metadata_matches_migrated_schema`: on the migrated DB, `alembic.autogenerate.compare_metadata(MigrationContext.configure(conn), Base.metadata) == []` (import `project_hub.users.models` so the table is registered).
  - `test_migrate_cli_applies_migrations`: `subprocess.run([sys.executable, "-m", "project_hub.db.migrate"], cwd=tmp_path, env={**os.environ, "APP_DATABASE_URL": url})` → returncode 0 and `users` exists. `cwd=tmp_path` so a developer's `.env` is not read.
  - `test_migrate_cli_without_url_fails`: same with `APP_DATABASE_URL` removed from env → returncode 1, `"APP_DATABASE_URL is not set"` in stderr.
  - `tests/support/test_database.py::test_truncate_tables_keeps_alembic_version` (uses `migrated_database_url`): insert a user, `truncate_tables` → `users` empty, `alembic_version` still has its row.
- [ ] **Step 2: Run, expect failures** — `poetry run pytest tests/db/test_migrations.py tests/support/test_database.py -v` → FAIL (import errors).
- [ ] **Step 3: Implement** the files above.
- [ ] **Step 4: Run, expect pass**; also `poetry run alembic upgrade head` with `APP_DATABASE_URL` pointing at a scratch DB works from the repo root (manual check, note the output in the report). Ruff and pyright clean (migrations are under `src/`, so they are type-checked too).
- [ ] **Step 5: Commit** — `git commit -m "Add users entity, ORM model and first migration"`

---

### Task 3: Protocols, ORM backend and contract tests

AC 9–15 for `orm`; Review Focus 2, 3.

**Files:**
- Create: `src/project_hub/db/uow.py`, `db/database.py`, `db/orm.py`, `src/project_hub/users/repository_orm.py`
- Modify: `tests/conftest.py` (fixture `database`)
- Test: `tests/users/test_repository_contract.py`, `tests/db/test_unit_of_work_contract.py`

**Interfaces:**
- Consumes: Task 2 entities, `UserRepository`, `UserModel`, `migrated_database_url`, `truncate_tables`.
- Produces:
  - `project_hub.db.uow.UnitOfWork(Protocol)`: attribute `users: UserRepository`; `async commit() -> None`; `async rollback() -> None`; `async __aenter__() -> Self`; `async __aexit__(exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None) -> None`.
  - `project_hub.db.database.Database(Protocol)`: `unit_of_work() -> UnitOfWork`; `async open() -> None`; `async close() -> None`.
  - `project_hub.db.orm.OrmDatabase(url: str)` (plain URL; converts with `sqlalchemy_url`), `OrmUnitOfWork`.
  - `project_hub.users.repository_orm.OrmUserRepository(session: AsyncSession)`.
  - Fixture `database` (async, params `["orm"]` in this task; Task 4 adds `"sql"`): builds the backend for `migrated_database_url`, `await open()`, yields, `await close()`, then `truncate_tables(migrated_database_url)`. Test ids are the backend names.

Behavior: `OrmDatabase.open()` creates the engine and runs `SELECT 1` so a bad URL fails at startup; `close()` disposes the engine. One `OrmUnitOfWork` = one `AsyncSession` (`expire_on_commit=False`); `__aexit__` rolls back anything not committed and closes the session; exceptions propagate. `OrmUserRepository.add` runs inside `session.begin_nested()`, flushes, maps `UserModel` → `User`; an `IntegrityError` whose `orig.diag.constraint_name == "uq_users_login"` becomes `ConflictError(f"Login {login!r} is already taken")`, anything else is re-raised.

- [ ] **Step 1: Write failing contract tests** (module-level `pytestmark = pytest.mark.anyio`; all take `database: Database`).

`tests/users/test_repository_contract.py`:
- `test_add_returns_user_with_generated_fields`: `add(NewUser("mila", "hash"))` → `type(u) is User`, `isinstance(u.id, UUID)`, `u.created_at.tzinfo is not None`, login and hash equal.
- `test_get_by_id_and_login_return_added_user`: after add + commit, in a new UoW both getters return a `User` equal to the added one, `type(...) is User`.
- `test_unknown_id_and_login_return_none`: `get_by_id(uuid4())` and `get_by_login("nobody")` are `None`.
- `test_duplicate_login_raises_conflict_and_uow_stays_usable`: add `mila`, commit; in a new UoW add `mila` → `pytest.raises(ConflictError)`; then add `anna`, commit; a new UoW finds `anna`.
- `test_login_is_case_sensitive`: add `mila` and `Mila` in one UoW, commit → both found, different ids.

`tests/db/test_unit_of_work_contract.py`:
- `test_commit_persists`: add in UoW A + commit; UoW B finds it.
- `test_exit_without_commit_persists_nothing`: the add is the **first** statement in the UoW, no commit → a new UoW finds nothing.
- `test_exception_rolls_back_and_propagates`: inside the block add, then `raise RuntimeError("boom")` → `pytest.raises(RuntimeError, match="boom")`; a new UoW finds nothing.
- `test_explicit_rollback_discards_changes`: add, `await uow.rollback()`, commit → nothing persisted.
- `test_concurrent_units_are_isolated`: open UoW A, add `mila` without commit; while A is still open, UoW B `get_by_login("mila")` is `None`; then A commits and a new UoW C finds it.

- [ ] **Step 2: Run, expect failures** — `poetry run pytest tests/users tests/db/test_unit_of_work_contract.py -v` → FAIL (import errors).
- [ ] **Step 3: Implement** the protocols, `OrmDatabase`, `OrmUnitOfWork`, `OrmUserRepository`.
- [ ] **Step 4: Run, expect pass** for `[orm]`; ruff and pyright clean.
- [ ] **Step 5: Commit** — `git commit -m "Add Unit of Work protocol and SQLAlchemy backend"`

---

### Task 4: SQL backend and backend factory

AC 4, AC 9–15 for `sql`; Review Focus 5.

**Files:**
- Create: `src/project_hub/db/sql.py`, `src/project_hub/users/repository_sql.py`
- Modify: `src/project_hub/db/database.py` (add `create_database`)
- Modify: `tests/conftest.py` (`database` params become `["orm", "sql"]`)
- Test: `tests/db/test_database_factory.py`, `tests/db/test_database_contract.py`

**Interfaces:**
- Consumes: Task 3 protocols and fixture.
- Produces: `project_hub.db.sql.SqlDatabase(url: str)`, `SqlUnitOfWork`; `project_hub.users.repository_sql.SqlUserRepository(conn: psycopg.AsyncConnection[Any])`; `project_hub.db.database.create_database(settings: Settings) -> Database`.

Behavior and pitfalls:
- `SqlDatabase` owns `psycopg_pool.AsyncConnectionPool(url, open=False)`; `open()` calls `await pool.open(wait=True, timeout=10)`; `close()` closes the pool.
- `SqlUnitOfWork` takes a connection with `await pool.getconn()` and returns it with `putconn` in `__aexit__` after `await conn.rollback()`. **Do not use `async with pool.connection()`**: it commits an open transaction when the block ends, which breaks AC 14.
- The connection is non-autocommit: the first statement opens a transaction implicitly; `commit()` / `rollback()` call the connection's.
- `SqlUserRepository.add` must protect the UoW with an explicit savepoint: `SAVEPOINT add_user` → `INSERT … RETURNING id, login, password_hash, created_at` → `RELEASE SAVEPOINT add_user`; on `psycopg.errors.UniqueViolation` with `diag.constraint_name == "uq_users_login"`: `ROLLBACK TO SAVEPOINT add_user`, raise `ConflictError` with the same message as the ORM. **Do not use `conn.transaction()` here**: when no transaction is open yet it starts and *commits* an outer one, which breaks AC 14. All SQL uses parameters (`%s`), never string formatting. Map rows with `psycopg.rows.class_row(User)`.
- `create_database`: `ValueError("database_url is not set")` without a URL; `"orm"` → `OrmDatabase`, `"sql"` → `SqlDatabase`, both get `database_url.get_secret_value()`.

- [ ] **Step 1: Write failing tests**
  - `tests/db/test_database_factory.py`: `test_create_database_picks_backend` (parametrize `("orm", OrmDatabase)`, `("sql", SqlDatabase)`; settings built with `IsolatedSettings(db_backend=..., database_url=SecretStr("postgresql://u:p@localhost:1/d"))`; no connection is made); `test_create_database_requires_url` → `ValueError`.
  - `tests/db/test_database_contract.py`: `test_open_fails_fast_when_database_is_unreachable`, parametrized over `orm`/`sql`, builds the backend for `postgresql://project_hub:project_hub@127.0.0.1:1/x` (closed port), asserts `await db.open()` raises within 15 s (`with anyio.fail_after(15), pytest.raises(Exception)`), then `await db.close()`.
  - Change the `database` fixture params to `["orm", "sql"]` — the Task 3 contract tests now also run for `sql` and fail.
- [ ] **Step 2: Run, expect failures** — `poetry run pytest tests/db tests/users -v` → `[sql]` cases and factory tests FAIL.
- [ ] **Step 3: Implement** `SqlDatabase`, `SqlUnitOfWork`, `SqlUserRepository`, `create_database`.
- [ ] **Step 4: Run, expect pass** for both backends; ruff and pyright clean.
- [ ] **Step 5: Commit** — `git commit -m "Add psycopg SQL backend and backend factory"`

---

### Task 5: App wiring

AC 16, 17.

**Files:**
- Modify: `src/project_hub/main.py` (lifespan)
- Create: `src/project_hub/db/dependencies.py`
- Test: `tests/db/test_dependencies.py`, `tests/test_main.py` (add tests)

**Interfaces:**
- Consumes: `create_database`, `Database`, `UnitOfWork`.
- Produces: `project_hub.db.dependencies.get_uow(request: Request) -> AsyncIterator[UnitOfWork]` (async generator dependency). `create_app` keeps its signature.

Lifespan: when `settings.database_url` is set → `database = create_database(settings)`, `await database.open()`, `app.state.database = database`, on shutdown `await database.close()`; otherwise `app.state.database = None`. `get_uow` raises `RuntimeError("Database is not configured: set APP_DATABASE_URL")` when it is `None`, else `async with database.unit_of_work() as uow: yield uow`. It never commits.

- [ ] **Step 1: Write failing tests**
  - `tests/test_main.py::test_app_without_database_url_serves_health`: `TestClient(create_app(IsolatedSettings()))` in `with` → `/health` 200, `app.state.database is None`.
  - `tests/test_main.py::test_lifespan_opens_and_closes_database`: monkeypatch `project_hub.main.create_database` with a fake recording `open`/`close`; settings with a dummy `database_url`; inside `with TestClient` → opened, not closed; after exit → closed.
  - `tests/db/test_dependencies.py::test_get_uow_gives_working_unit_of_work` (parametrize `orm`/`sql`, uses `migrated_database_url`; truncate in teardown): app from `create_app(IsolatedSettings(db_backend=b, database_url=SecretStr(url)))`, plus a test-only route `POST /_test/users` that does `await uow.users.add(NewUser("mila","h"))`, `await uow.commit()` and returns `{"uow": type(uow).__name__}`; response 200 with `OrmUnitOfWork` / `SqlUnitOfWork`; a direct psycopg query finds `mila`.
  - `tests/db/test_dependencies.py::test_get_uow_without_database_returns_500`: app without URL + a route depending on `get_uow` → 500 `{"detail": "Internal Server Error"}` (use `TestClient(app, raise_server_exceptions=False)`).
- [ ] **Step 2: Run, expect failures.**
- [ ] **Step 3: Implement** the lifespan and `get_uow`.
- [ ] **Step 4: Run the full suite**, expect pass; ruff and pyright clean.
- [ ] **Step 5: Commit** — `git commit -m "Wire the database into the app lifespan"`

---

### Task 6: Docker `migrate` service and docs

AC 18.

**Files:**
- Modify: `docker-compose.yml`, `README.md`
- Test: `tests/test_docker_files.py` (add a test), `tests/test_docker_smoke.py` (add a test)

**Interfaces:**
- Consumes: `python -m project_hub.db.migrate` (Task 2).

Compose: service `migrate` — `build: .`, the same `APP_DATABASE_URL` as `api`, `command: ["python", "-m", "project_hub.db.migrate"]`, `depends_on: db: condition: service_healthy`. `api` adds `migrate: condition: service_completed_successfully` to `depends_on`. README: a "Database" section (`APP_DB_BACKEND`, `APP_DATABASE_URL`, `poetry run alembic upgrade head`, how to add a migration by hand: `poetry run alembic revision -m "..."`, no autogenerate), the `migrate` service in the Docker section, and `db/` and the new `users/` files in Layout.

- [ ] **Step 1: Write failing tests**
  - `tests/test_docker_files.py::test_compose_runs_migrations_before_api` (parse YAML the way the existing tests in that file do): `migrate.command == ["python", "-m", "project_hub.db.migrate"]`, `migrate.depends_on.db.condition == "service_healthy"`, `api.depends_on.migrate.condition == "service_completed_successfully"`, `migrate.environment.APP_DATABASE_URL == api.environment.APP_DATABASE_URL`.
  - `tests/test_docker_smoke.py::test_compose_stack_migrates_database` (marker `docker`, same isolated-project pattern as `test_compose_stack_serves_health`): after `up -d --build --wait`, `ps -a --format json` shows `migrate` exited with code 0; `compose exec -T db psql -U project_hub -d project_hub -tAc "select to_regclass('public.users')"` prints `users`; `/health` is 200. If `up --wait` rejects the exited one-shot service, debug with `superpowers:systematic-debugging` and report the compose version.
- [ ] **Step 2: Run, expect failures** — `poetry run pytest tests/test_docker_files.py -v` and `poetry run pytest -m docker tests/test_docker_smoke.py -v`.
- [ ] **Step 3: Implement** compose and README changes.
- [ ] **Step 4: Run both commands, expect pass**; then the full default suite.
- [ ] **Step 5: Commit** — `git commit -m "Run migrations in a compose migrate service"`

---

## Acceptance criteria → tasks

| AC | Task | Test |
|---|---|---|
| 1, 2, 3 | 1 | `tests/test_config.py` new tests |
| 4 | 4 | `tests/db/test_database_factory.py` |
| 5, 6, 7, 8 | 2 | `tests/db/test_migrations.py` |
| 9, 10, 11, 12 | 3, 4 | `tests/users/test_repository_contract.py` `[orm]`, `[sql]` |
| 13, 14, 15 | 3, 4 | `tests/db/test_unit_of_work_contract.py` `[orm]`, `[sql]` |
| 16, 17 | 5 | `tests/test_main.py`, `tests/db/test_dependencies.py` |
| 18 | 6 | `tests/test_docker_smoke.py::test_compose_stack_migrates_database` |
