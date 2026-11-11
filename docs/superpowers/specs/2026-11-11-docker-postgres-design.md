# Epic 1a: Docker, Postgres and domain errors

Date: 2026-11-11
Status: approved design
Roadmap: [`docs/PRDs/roadmap.md`](../../PRDs/roadmap.md), epic 1a

## Goal

Run the API and PostgreSQL locally with Docker, give the test suite a real
Postgres database, and turn domain errors into JSON responses with proper HTTP
status codes (spec, implementation note 1: "All the returned data must be in
JSON format + proper http status codes").

## Decisions

| Area | Decision | Why |
|---|---|---|
| Test database | Postgres from `docker-compose`; each pytest session creates its own database and drops it at the end | One Postgres setup for dev and tests; parallel worktrees do not collide |
| Postgres unreachable | DB tests fail with a hint, never skip | Skipped DB tests hide untested code |
| Error body | `{"detail": "<message>"}`, same shape as FastAPI's built-in errors | Clients deal with one shape |
| Docker tests | Fast file checks always run; image and compose smoke tests are opt-in with marker `docker` | A full build takes about a minute |
| `Settings.database_url` | Not added in 1a | The app does not use the database until epic 1b |
| Driver | `psycopg[binary]` as a main dependency | Both 1b backends need it (plain SQL and SQLAlchemy's `postgresql+psycopg`) |

## 1. Docker image

`Dockerfile`, two stages, both `FROM python:3.13-slim`.

**Build stage**

- `pip install poetry==2.5.1` (the version that generated `poetry.lock`).
- Copy `pyproject.toml`, `poetry.lock`, `poetry.toml`, `README.md`, then
  `poetry install --only main --no-root --no-interaction` (dependency layer
  cached separately from the code).
- Copy `src/`, then `poetry install --only main --no-interaction` to install the
  package itself into `/app/.venv` (`poetry.toml` keeps the venv in the
  project).

**Runtime stage**

- Copy `/app/.venv` and `/app/src` from the build stage to the same paths. The
  editable install points at `/app/src`, so the paths must match.
- No Poetry and no dev tools in the runtime image.
- Non-root user `app`; `PATH` starts with `/app/.venv/bin`.
- `EXPOSE 8000`;
  `CMD ["uvicorn", "project_hub.main:app", "--host", "0.0.0.0", "--port", "8000"]`.
- `HEALTHCHECK` calls `/health` with Python's `urllib` (the slim image has no
  curl).

`.dockerignore`: `.venv/`, `.git`, `__pycache__/`, `.pytest_cache/`,
`.ruff_cache/`, `tests/`, `docs/`, `.env`, `.claude/`, `dist/`.

## 2. docker-compose

`docker-compose.yml` with two services. No top-level `name:`: the project name
comes from the directory, so it cannot clash with other stacks on the machine.

**`db`**

- Image `postgres:18-alpine`.
- `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` default to `project_hub`
  and can be overridden from `.env`. These are local development credentials
  only; real environments get theirs from SSM (epic 8a).
- Healthcheck: `pg_isready`.
- Named volume mounted at `/var/lib/postgresql` (the Postgres 18 image keeps
  its data under a versioned subdirectory there).
- Host port `127.0.0.1:${APP_DB_PORT:-55433}` → 5432, bound to loopback only (the
  superuser password is in the repo). The default avoids local Postgres servers
  on 5432 and 5433.

**`api`**

- `build: .`
- Host port `127.0.0.1:${APP_PORT:-8000}` → 8000, bound to loopback only.
- `depends_on: db` with `condition: service_healthy`.
- `APP_DATABASE_URL=postgresql://<user>:<password>@db:5432/<db>`. Settings ignore
  it until epic 1b adds the field; it is wired now so 1b only reads it.

`.env.example` documents `APP_DB_PORT`, `APP_PORT` and the `POSTGRES_*`
variables.

## 3. Test database

`tests/support/database.py`:

- `create_test_database(admin_url: str) -> str` connects to `admin_url` (a
  maintenance database such as `postgres`) with autocommit, runs
  `CREATE DATABASE project_hub_test_<uuid4 hex>`, and returns the URL of the new
  database (`postgresql://…/project_hub_test_<hex>`).
- `drop_test_database(admin_url: str, database_url: str) -> None` runs
  `DROP DATABASE IF EXISTS … WITH (FORCE)`.
- Identifiers go through `psycopg.sql.Identifier`, never string formatting.
- `drop_test_database` refuses (`ValueError`, before connecting) any database whose
  name does not start with `project_hub_test_`.
- If the server cannot be reached or refuses the connection (wrong password,
  missing database), both raise `TestDatabaseUnavailableError`. Line 1 of the
  message is
  `Postgres is not reachable at <host>:<port>. Start it with: docker compose up -d db`,
  followed by `Reason: <driver error>` (whitespace stripped). The URL's password
  is replaced with `***` everywhere in the reason, so the message never contains
  it. `unavailable_message(admin_url, reason=None)` builds it; without a reason
  only line 1 is produced.

`tests/conftest.py`:

- Session fixture `database_url` reads `TEST_DATABASE_URL`, default
  `postgresql://project_hub:project_hub@localhost:55433/postgres` (the compose
  defaults; local credentials only). It calls `create_test_database`, yields the
  URL, and calls `drop_test_database` at teardown. On
  `TestDatabaseUnavailableError` it calls `pytest.fail` with the error message,
  so the test errors out instead of skipping.
- The fixture is lazy: only tests that request it need Postgres.
- The URL is a plain `postgresql://` URL. Epic 1b converts it to
  `postgresql+psycopg://` for SQLAlchemy and applies migrations in its own
  fixtures.

## 4. Domain errors

`src/project_hub/core/exceptions.py`, pure Python with no FastAPI or Starlette
import, so services can raise errors without knowing about HTTP:

| Class | Status | Example use |
|---|---|---|
| `DomainError(message: str)` | 400 | Base class; unmapped subclasses fall back to it |
| `NotFoundError` | 404 | Project or document does not exist or is not visible |
| `PermissionDeniedError` | 403 | Participant deletes a project; non-owner invites |
| `ConflictError` | 409 | Login already taken; user is already a participant |
| `AuthenticationError` | 401 | Wrong password, missing or expired JWT |

Errors needed only by later epics (for example the 7a quota) are added there.

`src/project_hub/core/error_handlers.py`:

- A mapping from error class to status code. The lookup walks the exception's
  MRO, so a subclass of `NotFoundError` gets 404.
- The domain error handler returns `JSONResponse({"detail": exc.message}, status)`.
  For `AuthenticationError` it adds the header `WWW-Authenticate: Bearer`.
- The `Exception` handler logs the traceback with `logger.exception` and returns
  500 `{"detail": "Internal Server Error"}`. The exception text is never sent to
  the client.
- `register_error_handlers(app: FastAPI) -> None` is called from `create_app`.

FastAPI's own handlers for `HTTPException` (404 for unknown paths) and
validation errors (422) stay unchanged; they already return `{"detail": …}`.

## 5. Tests and markers

- `pyproject.toml` registers the marker `docker`, and `addopts` gains
  `-m "not docker"`, so `poetry run pytest` skips the smoke tests and
  `poetry run pytest -m docker` runs only them.
- Smoke tests use their own compose project name and free host ports, and tear
  everything down at the end (`docker compose down -v`, `docker rm -f`), so they
  never touch a developer's running stack.
- `poetry` stays on `PATH` wherever pytest runs, because
  `tests/test_packaging.py` calls `poetry check --lock`. Tests run on the host,
  not in the runtime image.

## Acceptance criteria

1. Given a route that raises `NotFoundError`, `PermissionDeniedError`,
   `ConflictError` or `AuthenticationError`, when it is called, then the response
   has status 404, 403, 409 or 401 and body `{"detail": "<message>"}`.
2. Given a subclass of `NotFoundError`, when a route raises it, then the status
   is 404; given a plain `DomainError`, then the status is 400.
3. Given a route that raises `AuthenticationError`, then the response has the
   header `WWW-Authenticate: Bearer`.
4. Given a route that raises an unhandled exception, then the response is 500,
   JSON `{"detail": "Internal Server Error"}`, and the body does not contain the
   exception text.
5. `project_hub.core.exceptions` imports nothing from `fastapi` or `starlette`.
6. Given the compose Postgres is running, when `create_test_database` is called,
   then a database named `project_hub_test_*` exists, accepts connections and
   has no tables in the `public` schema; after `drop_test_database` it no longer
   exists.
7. Given nothing listens at the admin URL, when `create_test_database` is
   called, then `TestDatabaseUnavailableError` is raised, its first line is the
   hint containing `docker compose up -d db`, a `Reason:` line shows the driver
   error (for example `password authentication failed` when the server is up but
   the password is wrong), and the message does not contain the password.
   `drop_test_database` behaves the same and refuses non-`project_hub_test_*`
   databases with `ValueError`.
8. The `Dockerfile` installs `poetry==2.5.1` and runs
   `poetry install … --no-interaction`; `.dockerignore` lists `.venv/`.
9. `docker compose config` succeeds; `db` has a healthcheck; `api` depends on
   `db` with `condition: service_healthy`.
10. Smoke (`-m docker`): the image builds; a container started from it answers
    `GET /health` with 200 `{"status": "ok"}`; its process does not run as root.
11. Smoke (`-m docker`): `docker compose up` starts `db` and `api`; `/health`
    through compose answers 200.
12. `poetry run ruff check`, `poetry run ruff format --check`,
    `poetry run pyright` and `poetry run pytest` (with `db` running) all pass.

## Out of scope

- `Settings.database_url`, connection pools, migrations, repositories (epic 1b).
- CI workflows (epic 2).
- LocalStack for S3 and Lambda (epic 6).
- Any change to FastAPI's built-in 404 and 422 bodies.
