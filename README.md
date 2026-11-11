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

## Docker

```bash
docker compose up --build
```

This starts PostgreSQL 18 (`db`) and the API (`api`). The API waits for the database to be
healthy and is served at <http://localhost:8000>.

| Service | Host port | Override with |
|---|---|---|
| `api` | 8000 | `APP_PORT` |
| `db` | 55433 | `APP_DB_PORT` |

The database uses 55433 so it does not clash with local Postgres servers on 5432 or 5433. Set the variables
in `.env` (see `.env.example`) or in the shell, for example `APP_PORT=8010 docker compose up`.
The `POSTGRES_*` values are local development credentials only; they take effect only when
the database volume is first created (run `docker compose down -v` to reset it).

Tests that need a database expect the `db` service to be running:

```bash
docker compose up -d --wait db
```

Stop everything with `docker compose down` (add `-v` to delete the database volume).

## Checks

```bash
poetry run ruff check
poetry run ruff format --check
poetry run pyright
docker compose up -d --wait db   # tests need Postgres
poetry run pytest
```

The tests create a throwaway database (`project_hub_test_<random>`) on the compose `db`
service and drop it when the session ends. Set `TEST_DATABASE_URL` (an admin URL such as
`postgresql://project_hub:project_hub@localhost:55433/postgres`) to use a different server.
pytest reads it only from the shell environment, not from `.env`, so use
`export TEST_DATABASE_URL=...`, and keep its port and credentials in step with `APP_DB_PORT`
and `POSTGRES_*` if you change them.

## Layout

Each feature gets its own package under `src/project_hub/<feature>/` with, as needed:
`router.py` (HTTP layer), `schemas.py` (request/response models), `service.py` (business
logic, no HTTP knowledge), `repository.py` (data access), `models.py` (ORM models) and
`dependencies.py` (FastAPI dependencies).

- Shared code lives in `core/`.
- Feature modules depend on `core/`; `core/` never imports from feature modules.
- A module that needs another module calls that module's `service`, never its repository.
- Tests mirror this layout under `tests/<feature>/`.
