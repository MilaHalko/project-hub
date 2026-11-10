# Base project skeleton — design

Date: 2026-11-10
Status: approved in chat, pending written-spec review

## Goal

Create the minimal, runnable FastAPI skeleton that every later feature from
[`specs/initial-spec.md`](../../../specs/initial-spec.md) (auth, projects,
documents, sharing) is built on. The skeleton contains **no business endpoints**.
It is done when the app starts, answers a health check, and lint, type check and
tests are all clean.

## Decisions

| Topic | Decision | Reason |
|---|---|---|
| Scope | Minimal app only: FastAPI + settings + health check + tests + tooling | Database, Docker, CI, S3 are added by the first feature that needs them (YAGNI) |
| Code layout | Modules by feature, layers inside each module, shared `core/` | One feature = one folder, which keeps per-feature PRs small; layers still separate HTTP, logic and data access |
| Package name | `project_hub` (src layout) | Short and descriptive |
| Python | 3.13 (`requires-python = ">=3.13"`) | Current stable; satisfies the spec's 3.12+ |
| Tooling | uv, ruff, pyright (strict), pytest | Required by `CLAUDE.md` |

## Layout

```
pyproject.toml          # project metadata, uv_build backend, ruff/pyright/pytest config
uv.lock
.python-version         # 3.13
.env.example            # documents APP_NAME, APP_DEBUG
.gitignore              # Python, venv, caches, .env
README.md               # install, run, check commands
src/project_hub/
├── __init__.py
├── py.typed
├── main.py             # create_app(settings=None) -> FastAPI; module-level `app = create_app()`
├── core/
│   ├── __init__.py
│   └── config.py       # Settings(BaseSettings)
└── health/
    ├── __init__.py
    └── router.py       # APIRouter with GET /health
tests/
├── __init__.py
├── conftest.py         # `client` fixture: TestClient(create_app(Settings(...)))
├── test_config.py
├── test_main.py
└── health/
    ├── __init__.py
    └── test_router.py
```

### Conventions for future features

Each feature gets its own package under `src/project_hub/<feature>/` with, as
needed: `router.py` (HTTP layer), `schemas.py` (Pydantic request/response
models), `service.py` (business logic, no HTTP knowledge), `repository.py`
(data access), `models.py` (ORM models), `dependencies.py` (FastAPI
dependencies). Shared code lives in `core/`. Modules depend on `core/`; `core/`
never imports from feature modules. A module that needs another module calls
that module's `service`, never its repository. Tests mirror this layout under
`tests/<feature>/`.

## Components

### `core/config.py`

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", env_file=".env", extra="ignore")
    name: str = "Project Hub"
    debug: bool = False
```

- Reads `APP_NAME` and `APP_DEBUG` from the environment, then from `.env`.
- Every field has a default, so the app starts without a `.env` file.
- No module-level `settings` singleton; `create_app` instantiates `Settings()`
  when none is passed.

### `main.py`

```python
def create_app(settings: Settings | None = None) -> FastAPI: ...
app = create_app()
```

- Builds `FastAPI(title=settings.name, debug=settings.debug)` and includes the
  health router.
- The factory lets tests inject their own `Settings` without touching the
  environment.

### `health/router.py`

- `GET /health` → `200`, body `{"status": "ok"}`.
- The response model is a Pydantic model `HealthResponse(status: Literal["ok"])`,
  so the OpenAPI schema is typed.

## Dependencies

- Runtime: `fastapi`, `uvicorn[standard]`, `pydantic-settings`.
- Dev group: `pytest`, `httpx` (required by `TestClient`), `ruff`, `pyright`.

## Tooling configuration

- ruff: `line-length = 100`, `target-version = "py313"`, lint rules
  `E, F, I, UP, B, SIM, RUF`; `ruff format` for formatting.
- pyright: `typeCheckingMode = "strict"`, `include = ["src", "tests"]`,
  `pythonVersion = "3.13"`, venv `.venv`.
- pytest: `testpaths = ["tests"]`, `addopts = "-ra --strict-markers"`.

## Error handling

None in the skeleton. `core/exceptions.py` (domain errors → JSON responses with
proper status codes) is added by the first feature that raises a domain error.

## Testing

Tests do not depend on the developer's environment: settings tests use
`monkeypatch` to clear `APP_*` variables and pass `_env_file=None`.

## Acceptance criteria

1. Given the app, when a client calls `GET /health`, then the response is `200`
   with body `{"status": "ok"}`. *(test)*
2. Given no `APP_*` variables and no env file, when `Settings` is created, then
   `name == "Project Hub"` and `debug is False`. *(test)*
3. Given `APP_NAME=x` and `APP_DEBUG=true` in the environment, when `Settings`
   is created, then `name == "x"` and `debug is True`. *(test)*
4. Given `Settings(name="x")`, when `create_app` is called with it, then the app
   has `title == "x"`. *(test)*
5. `uv run ruff check` and `uv run ruff format --check` report no issues.
   *(command)*
6. `uv run pyright` reports 0 errors. *(command)*
7. `uv run pytest` passes. *(command)*
8. `uv run uvicorn project_hub.main:app` starts and `curl localhost:8000/health`
   returns `200`. *(manual smoke check)*

## Out of scope

PostgreSQL, SQLAlchemy, Alembic, Docker, CI/CD, S3/Lambda, auth, middleware,
logging setup — each arrives with the feature that needs it.
