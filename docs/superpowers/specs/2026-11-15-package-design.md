# Epic 9: Package

Date: 2026-11-15
Status: approved (by the coordinator on Mila's behalf, she chose "approve for me" for the night)
Roadmap: [`docs/PRDs/roadmap.md`](../../PRDs/roadmap.md), epic 9

## Goal

The backend is a real Python package: `poetry build` makes a wheel and an sdist of
`project_hub`, CI builds them on every pull request, uploads them as an artifact and proves that the
wheel works when installed on its own. Spec: "package creation, CI&CD bindings, implementation of
related tools (pyproject.toml, tox || poetry)". We use Poetry, so no tox.

## Findings

- `poetry build` already works. The wheel holds all `.py` files, the four migrations,
  `script.py.mako` and `py.typed`.
- `alembic.ini` stays out of the wheel and is not needed: `project_hub.db.migrate` finds the
  migrations as package data (`project_hub.db:migrations`).
- The Dockerfile installs the project in editable mode and does not use the wheel. It stays as it is.

## Non-goals

- No publishing to PyPI, no GitHub Release, no `tox`.
- No console command that starts the server (extra C, not recommended).
- No change to the Dockerfile (extra F, not recommended).
- No license field: only Mila can choose it. Left out on purpose.

## Approaches

1. **A new CI job `package` plus an opt-in pytest marker `package` (chosen).** The job builds the
   files, uploads them, then `pytest -m package` installs the uploaded wheel into a clean virtualenv
   and runs it. The same test runs locally with `poetry run pytest -m package`.
2. Plain shell steps in the workflow. Cannot be run locally, invisible to pytest. Rejected.
3. Extra steps inside `checks`. `checks` is a required check; mixing a slow install into it makes
   every failure there harder to read. Rejected.

## Design

- **Test** `tests/test_package_smoke.py`, marker `package`, excluded by default through
  `addopts` (`-m "not docker and not package"`), like `docker`.
  - Wheel source: `PACKAGE_DIST_DIR` if set (CI passes the folder it uploaded), otherwise the test
    runs `poetry build` into a temporary folder.
  - One session-wide clean virtualenv in a temporary folder; the wheel is installed with `pip`
    (dependencies come from PyPI by the ranges in the metadata, not from `poetry.lock`).
  - Every command runs with the venv's Python, `-I` (isolated mode) and a temporary working folder,
    so nothing from `src/` or `.env` leaks in.
- **CI job `package`** in `ci.yml`: Postgres service (same as `checks`), checkout, Poetry,
  `poetry install`, `poetry build`, `actions/upload-artifact` (name `project-hub-dist`, 14 days),
  `PACKAGE_DIST_DIR=dist poetry run pytest -m package -v`. `checks` and `docker` are untouched.
- **README:** section "Build the package".

## Acceptance criteria

| # | Criterion | Proof |
|---|---|---|
| 1 | `poetry build` creates `project_hub-<version>-py3-none-any.whl` and `project_hub-<version>.tar.gz` | `poetry build` and the package test (it looks for both files) |
| 2 | The wheel installed into a clean venv, run from another folder, imports `project_hub` from `site-packages`, not from `src/` | `test_package_smoke.py` |
| 3 | The installed app started with uvicorn answers `GET /health` with 200 and `{"status": "ok"}` | `test_package_smoke.py` |
| 4 | The installed `python -m project_hub.db.migrate` applies every migration of the source tree to a real Postgres (the `alembic_version` equals the head of the source tree) | `test_package_smoke.py` |
| 5 | The sdist builds a wheel with the same list of files as the built wheel | `test_package_smoke.py` |
| 6 | The command `project-hub-migrate` exists after install and applies the migrations (extra B) | `test_package_smoke.py` |
| 7 | The package has authors, repository link and keywords; `poetry check` is clean (extra A) | `poetry check --lock`, `poetry build` |
| 8 | CI job `package` runs on every PR, uploads `dist/` as artifact `project-hub-dist` and passes criteria 2-6 on the uploaded files; `checks` and `docker` are unchanged | CI run on the PR |
| 9 | The default `pytest` does not run the package tests | `poetry run pytest` shows them deselected |
| 10 | The README explains how to build and install | review |

## Extras

Taken: A (metadata without a license), B (`project-hub-migrate` command), D (sdist check).
Not taken: C (serve command: needs new code, not needed), E (release on tag: needs the
`contents: write` permission), F (Dockerfile from wheel: conflicts with epics 8a and 10), G (tox).

## Decisions made without Mila (for the report)

- Package job is a new job, not part of `checks`/`docker`. It should become a required check after
  its first green run; the ruleset is not changed here.
- The wheel is installed by version ranges, not by `poetry.lock`: the test shows what a user of
  `pip install` gets. A broken new release of a dependency can turn the job red.
- Authors: name only, no e-mail.
