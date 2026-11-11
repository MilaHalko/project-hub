# Poetry Migration (Epic 0.5) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace uv with Poetry as the project's packaging and dependency tool, with no change to app behaviour.

**Architecture:** Keep the PEP 621 `[project]` table and the PEP 735 `[dependency-groups]` table (Poetry 2.5 reads both); switch only the build backend to `poetry-core`, add a `poetry.toml` that keeps the virtualenv in `.venv`, replace `uv.lock` with `poetry.lock`, and update the docs. A small pytest module pins the packaging facts.

**Tech Stack:** Python 3.13, Poetry 2.5 (`poetry-core` backend), FastAPI, pytest, ruff, pyright (strict).

**Spec:** Bounded path — the approved in-chat design for epic 0.5 in `docs/PRDs/roadmap.md`. Acceptance criteria:

1. `pyproject.toml` has `build-system.build-backend == "poetry.core.masonry.api"` and `requires` contains `poetry-core`.
2. `poetry.lock` exists at the repo root; `uv.lock` does not.
3. `poetry check --lock`, run from a test, exits 0.
4. `poetry.toml` sets `virtualenvs.in-project = true`.
5. `poetry build` produces a wheel and an sdist for `project_hub` (verification command).
6. `poetry run ruff check`, `ruff format --check`, `pyright`, `pytest` are green; existing tests pass unchanged (verification command).

## Global Constraints

- Do not change `[project]` metadata, dependency versions, `[dependency-groups]`, or any `[tool.*]` table in `pyproject.toml` — only `[build-system]`.
- `[build-system]`: `requires = ["poetry-core>=2.0,<3.0"]`, `build-backend = "poetry.core.masonry.api"`.
- Lock with `poetry lock` (Poetry 2.5.1 is at `/opt/homebrew/bin/poetry`); never hand-edit `poetry.lock`.
- No tox. ruff, pyright, pytest stay.
- Do not modify, weaken or delete existing tests.
- Do not edit historical docs in `docs/superpowers/specs/` and `docs/superpowers/plans/2026-11-10-*`.
- Commit messages must NOT contain a `Co-Authored-By: Claude` line.

## Review Focus

1. Fresh clone: `rm -rf .venv && poetry install` must create `.venv/` in the repo (pyright reads `venv = ".venv"`) and install the dev group — covered by `test_virtualenv_is_in_project` plus the Task 1 fresh-install verification step.
2. src layout: `poetry install` must install `project_hub` from `src/` so `import project_hub` works without `PYTHONPATH` — covered by the full suite passing under `poetry run pytest` after the fresh install.
3. Built wheel must contain `project_hub/py.typed` — covered by the Task 1 `poetry build` + `unzip -l` step.
4. Tests run from a directory other than the repo root (`cd tests && poetry run pytest`) — the packaging tests resolve the root from `__file__`, never from the cwd.
5. `poetry` missing from `PATH` in the test run must fail loudly, not skip — `test_poetry_lock_matches_pyproject` asserts `shutil.which("poetry") is not None`.

---

### Task 1: Switch packaging to Poetry

Covers AC1–AC5.

**Files:**
- Create: `tests/test_packaging.py`
- Create: `poetry.toml`
- Create: `poetry.lock` (generated)
- Modify: `pyproject.toml` (`[build-system]` only)
- Delete: `uv.lock`

**Interfaces:**
- Consumes: nothing.
- Produces: `poetry.lock`, `poetry.toml`; commands `poetry install` / `poetry run …` used by Task 2's docs.

- [ ] **Step 1: Write the failing tests** in `tests/test_packaging.py`

`ROOT = Path(__file__).resolve().parents[1]`; read TOML with `tomllib`.

- `test_build_backend_is_poetry_core`: `data["build-system"]["build-backend"] == "poetry.core.masonry.api"` and `any(r.startswith("poetry-core") for r in data["build-system"]["requires"])`.
- `test_poetry_lock_replaces_uv_lock`: `(ROOT / "poetry.lock").is_file()` and `not (ROOT / "uv.lock").exists()`.
- `test_poetry_lock_matches_pyproject`: `poetry = shutil.which("poetry")`; `assert poetry is not None`; `subprocess.run([poetry, "check", "--lock"], cwd=ROOT, capture_output=True, text=True, check=False)`; assert `returncode == 0` with stdout+stderr as the message. No `shell=True`.
- `test_virtualenv_is_in_project`: `tomllib.loads((ROOT / "poetry.toml").read_text())["virtualenvs"]["in-project"] is True`.

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_packaging.py -v`
Expected: 4 FAIL (backend is `uv_build`, no `poetry.lock`, `poetry check --lock` fails without a lock, no `poetry.toml`).

- [ ] **Step 3: Implement**

- Edit `[build-system]` in `pyproject.toml` per Global Constraints.
- Create `poetry.toml` with `[virtualenvs]` / `in-project = true`.
- `git rm uv.lock`, then `poetry lock`.

- [ ] **Step 4: Fresh install and run the tests under Poetry**

Run: `rm -rf .venv && poetry install && poetry run pytest -v`
Expected: `.venv/` recreated in the repo; all tests pass (8 existing + 4 new = 12 passed).

- [ ] **Step 5: Lint, types, build**

Run: `poetry run ruff check && poetry run ruff format --check && poetry run pyright`
Expected: `All checks passed!`, files already formatted, `0 errors`.

Run: `poetry build && unzip -l dist/project_hub-0.1.0-py3-none-any.whl | grep py.typed && (cd tests && poetry run pytest -q ..)`
Expected: wheel and sdist in `dist/`, `project_hub/py.typed` listed, 12 passed. `dist/` is git-ignored.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml poetry.toml poetry.lock tests/test_packaging.py
git commit -m "Switch packaging from uv to Poetry"
```
(`uv.lock` removal is already staged by `git rm`.)

### Task 2: Switch docs and agent instructions to Poetry

Covers the documentation part of the design (not tested by pytest, by agreement). Also ignores `.claude/worktrees/` so feature worktrees never show up as untracked in the main checkout.

**Files:**
- Modify: `README.md` (Requirements, Setup, Run, Checks)
- Modify: `CLAUDE.md:28-29`
- Modify: `.claude/skills/add-feature/SKILL.md:27,34`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: Task 1's `poetry install` / `poetry run` commands.
- Produces: nothing.

- [ ] **Step 1: README.md**

- Requirements: Python 3.13 and [Poetry](https://python-poetry.org/) 2.x; note the virtualenv is created in `.venv/` (via `poetry.toml`).
- Setup: `poetry install` then `cp .env.example .env`.
- Run: `poetry run uvicorn project_hub.main:app --reload`.
- Checks: `poetry run ruff check`, `poetry run ruff format --check`, `poetry run pyright`, `poetry run pytest`.

- [ ] **Step 2: CLAUDE.md** — line 28: replace `uv` in the skills list with `poetry`; line 29: `Tooling: \`poetry\`, \`ruff\`, \`pyright\`, \`pytest\`.`

- [ ] **Step 3: add-feature skill** — line 27: `(poetry, ruff, pyright, pytest)`; line 34: example `` `poetry run pytest` → 48 passed ``.

- [ ] **Step 4: .gitignore** — add `.claude/worktrees/`.

- [ ] **Step 5: Verify no uv commands remain in live docs**

Run: `grep -nE '\buv (run|sync|add)\b|\buv\b' README.md CLAUDE.md .claude/skills/add-feature/SKILL.md`
Expected: no output.

- [ ] **Step 6: Commit**

```bash
git add README.md CLAUDE.md .claude/skills/add-feature/SKILL.md .gitignore
git commit -m "Document Poetry workflow instead of uv"
```
