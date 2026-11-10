# Base Project Skeleton Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A minimal runnable FastAPI app (`project_hub`) with typed settings, a `GET /health` endpoint, tests and clean lint/type checks.

**Architecture:** src-layout package organized by feature module with a shared `core/`. `create_app(settings)` factory builds the app; tests inject their own `Settings`. No database, Docker or CI.

**Tech Stack:** Python 3.13, uv 0.13 (`uv_build` backend), FastAPI, uvicorn, pydantic-settings, pytest, httpx2, ruff, pyright (strict).

**Spec:** `docs/superpowers/specs/2026-11-10-base-project-design.md`

## Global Constraints

- `requires-python = ">=3.13"`, `.python-version` = `3.13`.
- Package import name `project_hub`, distribution name `project-hub`, src layout.
- Runtime deps only: `fastapi`, `uvicorn[standard]`, `pydantic-settings`. Dev group only: `pytest`, `httpx2`, `ruff`, `pyright`. Add them with `uv add` / `uv add --dev` so versions are locked in `uv.lock`.
- Settings: `env_prefix="APP_"`, `env_file=".env"`, `extra="ignore"`; fields `name: str = "Project Hub"`, `debug: bool = False`.
- ruff: `line-length = 100`, `target-version = "py313"`, `select = ["E", "F", "I", "UP", "B", "SIM", "RUF"]`.
- pyright: `typeCheckingMode = "strict"`, `include = ["src", "tests"]`, `pythonVersion = "3.13"`, `venvPath = "."`, `venv = ".venv"`.
- pytest: `testpaths = ["tests"]`, `addopts = "-ra --strict-markers"`.
- Tests never depend on the developer's environment: any `Settings` built in tests passes `_env_file=None` (or an explicit tmp file) and clears `APP_*` variables with `monkeypatch`.
- Commit messages must NOT contain a `Co-Authored-By: Claude` line.

## Review Focus

1. Invalid `APP_DEBUG` value (e.g. `maybe`) → `Settings()` raises `pydantic.ValidationError` instead of silently defaulting. Test in Task 1.
2. A `.env` file containing unrelated keys (future `DATABASE_URL` etc.) → settings still load and still read `APP_*` keys from that file. Test in Task 1.
3. A developer's local `.env` leaking into the test client → `client` fixture builds `Settings(_env_file=None, ...)`. Enforced in Task 2 conftest.
4. Unknown path → `404` with a JSON body (spec: all returned data is JSON). Test in Task 2.
5. The import path uvicorn uses (`project_hub.main:app`) exposes `/health` without any `.env`. Test in Task 2.

---

### Task 1: Project setup and settings

**Files:**
- Create: `pyproject.toml`, `.python-version`, `.gitignore`, `.env.example`
- Create: `src/project_hub/__init__.py`, `src/project_hub/py.typed`, `src/project_hub/core/__init__.py`, `src/project_hub/core/config.py`
- Test: `tests/__init__.py`, `tests/test_config.py`

**Interfaces:**
- Produces: `project_hub.core.config.Settings(BaseSettings)` with `name: str`, `debug: bool`.

- [ ] **Step 1: Create project files**

`pyproject.toml`: `[project]` name `project-hub`, version `0.1.0`, `requires-python = ">=3.13"`, `readme = "README.md"`; `[build-system] requires = ["uv_build>=0.13,<0.14"]`, `build-backend = "uv_build"`; `[tool.ruff]`, `[tool.ruff.lint]`, `[tool.pyright]`, `[tool.pytest.ini_options]` with the values from Global Constraints. Create an empty `README.md` placeholder (filled in Task 2) so the build backend finds it.
`.python-version`: `3.13`. `.gitignore`: `.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.ruff_cache/`, `.env`, `dist/`. `.env.example`: `APP_NAME=Project Hub` and `APP_DEBUG=false`.
Empty `src/project_hub/__init__.py`, `src/project_hub/py.typed`, `src/project_hub/core/__init__.py`, `tests/__init__.py`.

- [ ] **Step 2: Add dependencies**

Run: `uv add fastapi "uvicorn[standard]" pydantic-settings && uv add --dev pytest httpx2 ruff pyright`
Expected: `uv.lock` created, `.venv` created with Python 3.13 (`uv run python --version` → `Python 3.13.x`).

- [ ] **Step 3: Write the failing tests** in `tests/test_config.py`

```python
@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("APP_NAME", "APP_DEBUG"):
        monkeypatch.delenv(key, raising=False)

def test_defaults_without_env() -> None:
    s = Settings(_env_file=None)
    assert s.name == "Project Hub"
    assert s.debug is False

def test_env_vars_override_defaults(monkeypatch) -> None:
    monkeypatch.setenv("APP_NAME", "x"); monkeypatch.setenv("APP_DEBUG", "true")
    s = Settings(_env_file=None)
    assert s.name == "x" and s.debug is True

def test_invalid_debug_value_raises(monkeypatch) -> None:
    monkeypatch.setenv("APP_DEBUG", "maybe")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)

def test_env_file_with_unrelated_keys_is_accepted(tmp_path) -> None:
    env = tmp_path / ".env"
    env.write_text("DATABASE_URL=postgres://x\nAPP_NAME=from-file\n")
    s = Settings(_env_file=env)
    assert s.name == "from-file"
```

(Type every parameter for pyright strict: `monkeypatch: pytest.MonkeyPatch`, `tmp_path: Path`.)

- [ ] **Step 4: Run tests to verify they fail**

Run: `uv run pytest tests/test_config.py -v`
Expected: collection error `ModuleNotFoundError: No module named 'project_hub.core.config'`.

- [ ] **Step 5: Implement `Settings` in `src/project_hub/core/config.py`**

`class Settings(BaseSettings)` with `model_config = SettingsConfigDict(env_prefix="APP_", env_file=".env", extra="ignore")` and the two fields from Global Constraints. No module-level instance.

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_config.py -v`
Expected: `4 passed`.

- [ ] **Step 7: Lint and type check**

Run: `uv run ruff check && uv run ruff format --check && uv run pyright`
Expected: `All checks passed!`, all files already formatted, `0 errors, 0 warnings`.

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml uv.lock .python-version .gitignore .env.example README.md src tests
git commit -m "Set up project_hub package with typed settings"
```

### Task 2: App factory, health endpoint, README

**Files:**
- Create: `src/project_hub/main.py`, `src/project_hub/health/__init__.py`, `src/project_hub/health/router.py`
- Modify: `README.md`
- Test: `tests/conftest.py`, `tests/test_main.py`, `tests/health/__init__.py`, `tests/health/test_router.py`

**Interfaces:**
- Consumes: `Settings` from Task 1.
- Produces: `project_hub.main.create_app(settings: Settings | None = None) -> FastAPI`; module-level `project_hub.main.app: FastAPI`; `project_hub.health.router.router: APIRouter`; `HealthResponse(BaseModel)` with `status: Literal["ok"]`.

- [ ] **Step 1: Write the failing tests**

`tests/conftest.py` — fixture `client() -> Iterator[TestClient]` yielding `TestClient(create_app(Settings(_env_file=None, name="Test Hub")))` inside a `with` block.

`tests/health/test_router.py`:
```python
def test_health_returns_ok(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
```

`tests/test_main.py`:
```python
def test_create_app_uses_settings_name() -> None:
    assert create_app(Settings(_env_file=None, name="x")).title == "x"

def test_unknown_path_returns_json_404(client: TestClient) -> None:
    r = client.get("/does-not-exist")
    assert r.status_code == 404
    assert r.headers["content-type"] == "application/json"
    assert r.json() == {"detail": "Not Found"}

def test_module_app_exposes_health() -> None:
    from project_hub.main import app
    assert TestClient(app).get("/health").status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest -v`
Expected: conftest import error `No module named 'project_hub.main'`.

- [ ] **Step 3: Implement**

`health/router.py`: `router = APIRouter(tags=["health"])`; `HealthResponse`; `@router.get("/health", response_model=HealthResponse)` handler `health() -> HealthResponse` returning `HealthResponse(status="ok")`.
`main.py`: `create_app` builds `FastAPI(title=settings.name, debug=settings.debug)` (instantiating `Settings()` when `None`) and calls `app.include_router(health_router)`; then `app = create_app()`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest -v`
Expected: `8 passed`.

- [ ] **Step 5: Fill in `README.md`**

Sections: one-paragraph description (link `docs/initial-spec.md`); Requirements (uv; Python 3.13 is fetched by uv); Setup (`uv sync`, `cp .env.example .env`); Run (`uv run uvicorn project_hub.main:app --reload`, docs at `/docs`); Checks (`uv run ruff check`, `uv run ruff format --check`, `uv run pyright`, `uv run pytest`); Layout (feature modules + `core/` rules from the spec's "Conventions for future features").

- [ ] **Step 6: Lint and type check**

Run: `uv run ruff check && uv run ruff format --check && uv run pyright`
Expected: `All checks passed!`, all files formatted, `0 errors, 0 warnings`.

- [ ] **Step 7: Smoke run (acceptance criterion 8)**

Run in background: `uv run uvicorn project_hub.main:app --port 8000`, then `curl -s -w ' %{http_code}' localhost:8000/health`
Expected: `{"status":"ok"} 200`. Stop the server.

- [ ] **Step 8: Commit**

```bash
git add src tests README.md
git commit -m "Add app factory and health endpoint"
```

---

## Acceptance criteria → coverage

| # | Criterion | Proven by |
|---|---|---|
| 1 | `GET /health` → 200 `{"status": "ok"}` | `tests/health/test_router.py::test_health_returns_ok` |
| 2 | Defaults without env | `tests/test_config.py::test_defaults_without_env` |
| 3 | `APP_NAME` / `APP_DEBUG` override | `tests/test_config.py::test_env_vars_override_defaults` |
| 4 | `create_app` uses `settings.name` as title | `tests/test_main.py::test_create_app_uses_settings_name` |
| 5 | ruff clean | Task 2 Step 6 |
| 6 | pyright 0 errors | Task 2 Step 6 |
| 7 | pytest passes | Task 2 Step 4 |
| 8 | uvicorn starts, `/health` 200 | Task 2 Step 7 |
