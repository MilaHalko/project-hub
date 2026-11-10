# Project Hub

Project Hub is a FastAPI service for managing projects. This repository holds the base
skeleton: an app factory, typed settings and a health endpoint. See
[`docs/initial-spec.md`](docs/initial-spec.md) for the product spec.

## Requirements

- [uv](https://docs.astral.sh/uv/). Python 3.13 is fetched by uv automatically.

## Setup

```bash
uv sync
cp .env.example .env
```

## Run

```bash
uv run uvicorn project_hub.main:app --reload
```

Interactive API docs are served at <http://localhost:8000/docs>.

## Checks

```bash
uv run ruff check
uv run ruff format --check
uv run pyright
uv run pytest
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
