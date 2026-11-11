# Epic 1a: Docker, Postgres and Domain Errors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the API and Postgres with Docker, give tests a real throwaway Postgres database, and map domain errors to JSON responses with proper status codes.

**Architecture:** Pure-Python domain errors in `core/exceptions.py`; an HTTP mapping layer in `core/error_handlers.py` registered by `create_app`. A two-stage Poetry-based `Dockerfile` and a `docker-compose.yml` with `db` (Postgres 18) and `api`. Test helpers create and drop a uniquely named database per pytest session on the compose Postgres. Docker smoke tests are opt-in via the `docker` marker.

**Tech Stack:** Python 3.13, FastAPI, Poetry 2.5.1, psycopg 3, Postgres 18, Docker Compose, pytest, ruff, pyright (strict).

**Spec:** [`docs/superpowers/specs/2026-11-11-docker-postgres-design.md`](../specs/2026-11-11-docker-postgres-design.md)

## Global Constraints

- Python 3.13; pyright strict must report 0 errors over `src` and `tests`.
- Tooling: `poetry run ruff check`, `poetry run ruff format --check`, `poetry run pyright`, `poetry run pytest`. No tox, no uv.
- Poetry in the image is pinned to exactly `2.5.1`; every `poetry install` in the image uses `--no-interaction`.
- `core/` never imports from feature modules; `core/exceptions.py` imports nothing from `fastapi` or `starlette`.
- Error bodies are always `{"detail": "<message>"}`; the 500 body is exactly `{"detail": "Internal Server Error"}`.
- Compose defaults: user, password and database `project_hub`; host ports `${APP_DB_PORT:-55433}` (db) and `${APP_PORT:-8000}` (api); no top-level `name:`.
- `TEST_DATABASE_URL` default: `postgresql://project_hub:project_hub@localhost:55433/postgres`.
- Test database names: `project_hub_test_<uuid4 hex>`.
- Unreachable-Postgres message: `Postgres is not reachable at <host>:<port>. Start it with: docker compose up -d db` — never the password.
- Commits: no `Co-Authored-By` lines.
- Never modify, weaken or delete existing tests.

## Review Focus

1. **Async and sync routes** raising domain errors must both map correctly — Task 1 tests both.
2. **FastAPI's built-in errors must not change** after adding the catch-all handler: unknown path stays 404 `{"detail": "Not Found"}` (existing test) and a bad request body stays 422 with a list `detail` — Task 1 adds the 422 test.
3. **Dropping a test database while a connection to it is still open** (a test that forgot to close) must still drop it — Task 3 tests this (`WITH (FORCE)`).
4. **`TEST_DATABASE_URL` without an explicit port** must report `<host>:5432` in the unreachable message, and the password must not leak through it — Task 3 tests this.
5. **Smoke tests run while a developer's stack is up** must not touch it — Task 4 uses its own compose project name, random free ports and full teardown.

Known and intended: with `APP_DEBUG=true`, Starlette's debug traceback page takes precedence over the 500 handler (dev only). Tests pin the JSON 500 with `debug=False`.

---

### Task 1: Domain errors mapped to JSON

**Files:**
- Create: `src/project_hub/core/exceptions.py`
- Create: `src/project_hub/core/error_handlers.py`
- Modify: `src/project_hub/main.py` (call `register_error_handlers(app)` in `create_app`)
- Create: `tests/core/__init__.py`, `tests/core/test_exceptions.py`, `tests/core/test_error_handlers.py`

**Interfaces:**
- Produces:
  - `class DomainError(Exception)`: `__init__(self, message: str) -> None`, attribute `message: str`.
  - Subclasses of `DomainError`: `NotFoundError`, `PermissionDeniedError`, `ConflictError`, `AuthenticationError`.
  - `register_error_handlers(app: FastAPI) -> None` in `project_hub.core.error_handlers`.
  - Status mapping: `DomainError` 400, `NotFoundError` 404, `PermissionDeniedError` 403, `ConflictError` 409, `AuthenticationError` 401 (+ header `WWW-Authenticate: Bearer`); lookup walks `type(exc).__mro__`.
  - Logger: `logging.getLogger("project_hub.core.error_handlers")`; unhandled errors logged with `logger.exception`.

- [ ] **Step 1: Write the failing tests**

`tests/core/test_exceptions.py`:
- `test_domain_error_keeps_message`: `DomainError("boom").message == "boom"` and `str(DomainError("boom")) == "boom"`.
- `test_all_errors_subclass_domain_error`: each of the four subclasses is a subclass of `DomainError`.
- `test_exceptions_module_does_not_import_web_framework` (AC 5): parse `src/project_hub/core/exceptions.py` with `ast`; no `Import`/`ImportFrom` names start with `fastapi` or `starlette`.

`tests/core/test_error_handlers.py` — build a test app with `create_app(IsolatedSettings())` plus routes added in a fixture, and use `TestClient(app, raise_server_exceptions=False)`:
- Parametrized `test_domain_error_maps_to_status` (AC 1) over `(NotFoundError, 404)`, `(PermissionDeniedError, 403)`, `(ConflictError, 409)`, `(AuthenticationError, 401)`, each raised from an **async** route with message `"nope"`: `status_code` matches, `json() == {"detail": "nope"}`, `content-type` is `application/json`.
- `test_domain_error_from_sync_route` : sync route raising `NotFoundError("x")` → 404 `{"detail": "x"}`.
- `test_subclass_gets_parent_status` (AC 2): `class ProjectNotFound(NotFoundError)` → 404.
- `test_plain_domain_error_is_400` (AC 2): `DomainError("bad")` → 400 `{"detail": "bad"}`.
- `test_authentication_error_sets_www_authenticate` (AC 3): header `www-authenticate == "Bearer"`.
- `test_unhandled_error_is_json_500` (AC 4): route raises `RuntimeError("secret-internal-detail")` → 500, `json() == {"detail": "Internal Server Error"}`, `"secret-internal-detail" not in r.text`.
- `test_unhandled_error_is_logged` (AC 4): with `caplog`, the same route logs a record at `ERROR` from logger `project_hub.core.error_handlers` with `exc_info` set.
- `test_validation_error_unchanged` (Review Focus 2): route `def echo(n: int)` called with `?n=abc` → 422 and `isinstance(r.json()["detail"], list)`.

- [ ] **Step 2: Run the tests and see them fail**

Run: `poetry run pytest tests/core -v`
Expected: collection errors / FAIL with `ModuleNotFoundError: No module named 'project_hub.core.exceptions'`.

- [ ] **Step 3: Implement `core/exceptions.py`**

Plain classes with one-line docstrings saying when to raise each. No imports from FastAPI.

- [ ] **Step 4: Implement `core/error_handlers.py` and register it in `create_app`**

Two handlers registered with `app.add_exception_handler`: one for `DomainError`, one for `Exception`. Handlers take `(request: Request, exc: Exception)` and narrow with `isinstance` to satisfy pyright strict. Call `register_error_handlers(app)` in `create_app` right after the app is created.

- [ ] **Step 5: Run the tests and see them pass**

Run: `poetry run pytest -v && poetry run ruff check && poetry run ruff format --check && poetry run pyright`
Expected: all tests pass (13 existing + new), ruff clean, pyright 0 errors.

- [ ] **Step 6: Commit**

```bash
git add src/project_hub/core tests/core src/project_hub/main.py
git commit -m "Map domain errors to JSON responses"
```

---

### Task 2: Dockerfile, compose and fast file checks

**Files:**
- Create: `Dockerfile`, `.dockerignore`, `docker-compose.yml`
- Modify: `.env.example` (add `APP_PORT=8000`, `APP_DB_PORT=55433`, `POSTGRES_USER=project_hub`, `POSTGRES_PASSWORD=project_hub`, `POSTGRES_DB=project_hub`, `TEST_DATABASE_URL=postgresql://project_hub:project_hub@localhost:55433/postgres`)
- Modify: `pyproject.toml` (`[tool.pytest.ini_options]`: `addopts = '-ra --strict-markers -m "not docker"'`, `markers = ["docker: builds and runs Docker images; opt-in with pytest -m docker"]`)
- Modify: `README.md` (new "Docker" section: `docker compose up --build`, ports and their env overrides, `docker compose up -d db` for tests)
- Create: `tests/test_docker_files.py`

**Interfaces:**
- Produces: compose services `db` and `api`; image serves on container port 8000 as a non-root user; `/app/.venv/bin` first on `PATH`; `HEALTHCHECK` hitting `http://127.0.0.1:8000/health`. Task 3 and 4 rely on `db` listening on host port `${APP_DB_PORT:-55433}`; Task 4 relies on `APP_PORT` and `APP_DB_PORT` overriding host ports.

Dockerfile shape is fixed by spec section 1 (two stages on `python:3.13-slim`, deps layer before `COPY src`, copy `.venv` and `src` to the same paths). Set `PYTHONDONTWRITEBYTECODE=1`, `PYTHONUNBUFFERED=1`. `db` volume mounts `pgdata:/var/lib/postgresql`. `db` healthcheck: `pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}`, interval 2s, retries 15. `api` environment `APP_DATABASE_URL: postgresql://${POSTGRES_USER:-project_hub}:${POSTGRES_PASSWORD:-project_hub}@db:5432/${POSTGRES_DB:-project_hub}`.

- [ ] **Step 1: Write the failing tests** (`tests/test_docker_files.py`, ROOT as in `tests/test_packaging.py`)

- `test_dockerfile_pins_poetry` (AC 8): `"poetry==2.5.1"` in Dockerfile text.
- `test_dockerfile_poetry_install_is_non_interactive` (AC 8): every line matching `poetry install` also contains `--no-interaction`, and there is at least one.
- `test_dockerignore_excludes_venv_and_env` (AC 8): stripped lines of `.dockerignore` include `.venv/` and `.env`.
- `test_compose_config_is_valid` (AC 9): `docker compose config --format json` (via `shutil.which("docker")`, `cwd=ROOT`, `check=False`) returns 0; parse JSON.
- `test_compose_db_has_healthcheck` (AC 9): `services.db.healthcheck.test` mentions `pg_isready`.
- `test_compose_api_waits_for_healthy_db` (AC 9): `services.api.depends_on.db.condition == "service_healthy"`.
- `test_compose_db_default_host_port_is_55433`: with `APP_DB_PORT` removed from the subprocess env, `services.db.ports[0].published == "55433"`.
- `test_compose_has_no_fixed_project_name`: `"name:"` does not appear at column 0 of `docker-compose.yml`.
- `test_docker_marker_is_opt_in`: `pyproject` `addopts` contains `-m "not docker"` and `markers` has an entry starting with `docker:`.

Use a helper `_compose_config(env: dict[str, str] | None = None) -> dict[str, Any]` shared by the compose tests.

- [ ] **Step 2: Run them and see them fail**

Run: `poetry run pytest tests/test_docker_files.py -v`
Expected: FAIL (`FileNotFoundError` for `Dockerfile` / non-zero `docker compose config`).

- [ ] **Step 3: Write `Dockerfile`, `.dockerignore`, `docker-compose.yml`, update `.env.example`, `pyproject.toml`, `README.md`**

- [ ] **Step 4: Run the tests and the real stack**

Run: `poetry run pytest -v`, then `docker compose up -d --build --wait && curl -fsS localhost:8000/health; docker compose down`
Expected: tests pass; curl prints `{"status":"ok"}`. If host port 8000 is taken locally, use `APP_PORT=8010`.

- [ ] **Step 5: Commit**

```bash
git add Dockerfile .dockerignore docker-compose.yml .env.example pyproject.toml README.md tests/test_docker_files.py
git commit -m "Add Dockerfile and docker-compose with Postgres"
```

---

### Task 3: Throwaway test database per pytest session

**Files:**
- Modify: `pyproject.toml`, `poetry.lock` (`poetry add "psycopg[binary]>=3.2"` — main dependency)
- Create: `tests/support/__init__.py`, `tests/support/database.py`
- Modify: `tests/conftest.py` (session fixture `database_url`)
- Create: `tests/support/test_database.py`
- Modify: `README.md` ("Checks": start `docker compose up -d db` before `poetry run pytest`; `TEST_DATABASE_URL` override)

**Interfaces:**
- Consumes: compose `db` on host port 55433 (Task 2).
- Produces (in `tests.support.database`):
  - `DEFAULT_ADMIN_URL: Final = "postgresql://project_hub:project_hub@localhost:55433/postgres"`
  - `class TestDatabaseUnavailableError(Exception)` (set `__test__ = False` so pytest does not collect it)
  - `create_test_database(admin_url: str) -> str` → URL of the new database (same scheme, credentials, host and port as `admin_url`, path `/project_hub_test_<uuid4 hex>`)
  - `drop_test_database(admin_url: str, database_url: str) -> None`
  - `_unavailable_message(admin_url: str) -> str` (module-private, tested directly)
- Produces (in `tests/conftest.py`): session-scoped fixture `database_url() -> Iterator[str]`, reading `os.environ.get("TEST_DATABASE_URL", DEFAULT_ADMIN_URL)`; `pytest.fail(str(err), pytrace=False)` on `TestDatabaseUnavailableError`. Epic 1b builds on this fixture.

Connect with `psycopg.connect(admin_url, autocommit=True, connect_timeout=3)`. Build SQL with `psycopg.sql.SQL(...).format(sql.Identifier(name))`. Read host/port for the message from `psycopg.conninfo.conninfo_to_dict(admin_url)` (port defaults to `5432` when absent). Swap the database name with `urllib.parse.urlsplit(...)._replace(path=...)`. Raise `TestDatabaseUnavailableError(...) from None` so the original error text cannot leak into the message.

- [ ] **Step 1: Start Postgres and write the failing tests**

Run `docker compose up -d --wait db` first.

`tests/support/test_database.py` (uses `DEFAULT_ADMIN_URL` or `TEST_DATABASE_URL` for a live server):
- `test_creates_empty_connectable_database` (AC 6): `url = create_test_database(admin)`; the name from the URL path starts with `project_hub_test_`; `psycopg.connect(url)` returns `current_database()` equal to that name; `select count(*) from information_schema.tables where table_schema = 'public'` is 0; finally `drop_test_database`.
- `test_drop_removes_database` (AC 6): after drop, `select 1 from pg_database where datname = %s` on the admin connection returns no row.
- `test_drop_with_open_connection` (Review Focus 3): keep a connection to the test database open, call `drop_test_database`, database is gone; close the stale connection without asserting on it.
- `test_two_databases_have_distinct_names`: two `create_test_database` calls return different URLs (drop both).
- `test_unreachable_server_raises_with_hint` (AC 7): admin URL `postgresql://u:s3cret-pw@127.0.0.1:<free port>/postgres` (free port: bind a socket to port 0, read it, close) → `TestDatabaseUnavailableError`; message contains `127.0.0.1:<port>` and `docker compose up -d db`; `"s3cret-pw" not in str(err)`.
- `test_unreachable_message_defaults_port_5432` (Review Focus 4): call the message-building helper `_unavailable_message(admin_url: str) -> str` with `postgresql://u:pw@db.invalid/postgres` → contains `db.invalid:5432`, not `pw`.
- `test_database_url_fixture_gives_test_database(database_url: str)`: connected `current_database()` starts with `project_hub_test_`.

- [ ] **Step 2: Run them and see them fail**

Run: `poetry run pytest tests/support -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'psycopg'` / `tests.support.database`.

- [ ] **Step 3: Add psycopg, implement `tests/support/database.py` and the fixture, update README**

- [ ] **Step 4: Run all checks**

Run: `poetry run pytest -v && poetry run ruff check && poetry run ruff format --check && poetry run pyright`
Expected: all pass. Then `docker compose stop db && poetry run pytest tests/support/test_database.py::test_database_url_fixture_gives_test_database` → errors with the `docker compose up -d db` hint (manual check of the fixture path, AC 7); restart with `docker compose up -d --wait db`.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml poetry.lock tests/support tests/conftest.py README.md
git commit -m "Create a throwaway Postgres database per test session"
```

---

### Task 4: Opt-in Docker smoke tests

**Files:**
- Create: `tests/test_docker_smoke.py` (module-level `pytestmark = pytest.mark.docker`)

**Interfaces:**
- Consumes: `Dockerfile` and `docker-compose.yml` from Task 2 (`APP_PORT`, `APP_DB_PORT` host port overrides; image healthcheck).

Helpers in the test module: `_free_port() -> int`, `_wait_for_health(url: str, timeout: float = 60) -> tuple[int, str]` (polls with `urllib.request` until 200 or timeout), `_run(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]` (`check=True`, `capture_output=True`, `text=True`, `cwd=ROOT`).

- [ ] **Step 1: Write the tests**

- `test_image_serves_health_as_non_root` (AC 10): tag `project-hub-smoke:<uuid hex>`; `docker build -t <tag> .`; `docker run -d -p 127.0.0.1:<free port>:8000 <tag>`; `_wait_for_health` → 200 and `json.loads(body) == {"status": "ok"}`; `docker exec <id> id -u` output is not `"0"`. `finally`: `docker rm -f <id>`, `docker rmi -f <tag>`.
- `test_compose_stack_serves_health` (AC 11): project `project-hub-smoke-<uuid hex>`; env = `os.environ` + `APP_PORT`, `APP_DB_PORT` free ports; `docker compose -p <project> up -d --build --wait`; `_wait_for_health(f"http://127.0.0.1:{APP_PORT}/health")` → 200; `docker compose -p <project> ps --format json` shows both `db` and `api` running. `finally`: `docker compose -p <project> down -v --rmi local`.

- [ ] **Step 2: Run them**

Run: `poetry run pytest -m docker -v`
Expected: 2 passed. Then `poetry run pytest` shows them deselected (`2 deselected`).

These tests exercise files written in Task 2, so they pass on first run; to see them fail for the right reason, temporarily change `USER app` to `USER root` in the Dockerfile, run `test_image_serves_health_as_non_root`, see it fail on the uid assertion, and revert.

- [ ] **Step 3: Lint, types, commit**

Run: `poetry run ruff check && poetry run ruff format --check && poetry run pyright`
Expected: clean.

```bash
git add tests/test_docker_smoke.py
git commit -m "Add opt-in Docker smoke tests"
```

---

## Acceptance criteria → tasks

| AC | Task | Test |
|---|---|---|
| 1 | 1 | `test_domain_error_maps_to_status`, `test_domain_error_from_sync_route` |
| 2 | 1 | `test_subclass_gets_parent_status`, `test_plain_domain_error_is_400` |
| 3 | 1 | `test_authentication_error_sets_www_authenticate` |
| 4 | 1 | `test_unhandled_error_is_json_500`, `test_unhandled_error_is_logged` |
| 5 | 1 | `test_exceptions_module_does_not_import_web_framework` |
| 6 | 3 | `test_creates_empty_connectable_database`, `test_drop_removes_database` |
| 7 | 3 | `test_unreachable_server_raises_with_hint` (+ manual fixture check) |
| 8 | 2 | `test_dockerfile_pins_poetry`, `test_dockerfile_poetry_install_is_non_interactive`, `test_dockerignore_excludes_venv_and_env` |
| 9 | 2 | `test_compose_config_is_valid`, `test_compose_db_has_healthcheck`, `test_compose_api_waits_for_healthy_db` |
| 10 | 4 | `test_image_serves_health_as_non_root` |
| 11 | 4 | `test_compose_stack_serves_health` |
| 12 | all | Phase 5 verification commands |
