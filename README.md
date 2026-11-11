# Project Hub

Project Hub is a FastAPI service for managing projects. This repository holds the base
skeleton: an app factory, typed settings and a health endpoint. See
[`docs/initial-spec.md`](docs/initial-spec.md) for the product spec.

## Requirements

- Python 3.13 and [Poetry](https://python-poetry.org/) 2.2+.
- If your default `python3` is older than 3.13, run `poetry env use python3.13` before `poetry install` (Poetry does not download Python for you).
- The virtualenv is created in `.venv/` (configured in `poetry.toml`).

## Setup

```bash
poetry install
cp .env.example .env
```

## Run

```bash
poetry run uvicorn project_hub.main:app --reload
```

Interactive API docs are served at <http://localhost:8000/docs>.

## Checks

```bash
poetry run ruff check
poetry run ruff format --check
poetry run pyright
poetry run pytest
```

## Layout

Each feature gets its own package under `src/project_hub/<feature>/` with, as needed:
`router.py` (HTTP layer), `schemas.py` (request/response models), `service.py` (business
logic, no HTTP knowledge), `repository.py` (data access), `models.py` (ORM models) and
`dependencies.py` (FastAPI dependencies).

- Shared code lives in `core/`.
- Feature modules depend on `core/`; `core/` never imports from feature modules.
- A module that needs another module calls that module's `service`, never its repository.
- Tests mirror this layout under `tests/<feature>/`.
