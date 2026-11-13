# FinalPythonProject

## Required plugins

This project depends on these Claude Code plugins (declared in `.claude/settings.json`):

- **superpowers** — process skills (brainstorming, planning, TDD, debugging, verification)
- **code-review** — `/code-review` for PRs
- **security-guidance** — security warnings while editing
- **python-development** — Python agents (`python-pro`, `fastapi-pro`, `django-pro`) and Python skills

If any of them is missing in the session, say so before doing any work and ask the user to install it. Do not silently continue without it.

## Mandatory workflow

These rules are not optional. Do not skip them because a task "looks simple".

1. **New feature / new behavior** → invoke the project skill `add-feature` (`.claude/skills/add-feature/SKILL.md`) and follow every phase. Do not implement features outside it.
2. **Bug, failing test, unexpected behavior** → `superpowers:systematic-debugging` before proposing any fix.
3. **Any code change** → `superpowers:test-driven-development`: failing test first, then code (for behaviour; see "What to test" for tooling and configuration).
4. **Before saying "done", "fixed" or "passing"** → `superpowers:verification-before-completion`: run the checks and quote the real output.
5. **Before merge / PR** → code review: `/code-review` if a PR exists, otherwise `superpowers:requesting-code-review`; handle findings with `superpowers:receiving-code-review`.
6. **Finishing a branch** → `superpowers:finishing-a-development-branch`.

## Python

- Delegate Python implementation to the matching `python-development` agent: `python-development:python-development-fastapi-pro` for FastAPI, `python-development:python-development-django-pro` for Django, otherwise `python-development:python-pro`.
- Use the relevant `python-development:*` skills (testing patterns, type safety, code style, error handling, project structure, packaging) when the task touches that area.
- Tooling: `poetry`, `ruff`, `pyright`, `pytest`.

## What to test

- **Tests prove behaviour**: endpoints through `TestClient`, domain logic, repositories against real Postgres on both backends, migrations, Docker smoke tests that really build and run the stack.
- **No tests that only re-read a config or tooling file** (`pyproject.toml`, `poetry.lock`, `Dockerfile`, `docker-compose.yml`, `.github/workflows/*`, `.env.example`) to assert what was just written there. Such criteria are proven by a command that really runs the thing (`poetry check --lock`, `docker compose config`, an image build, the CI run), in the verification phase or as a CI step.
- **No tests for test helpers** in `tests/support/`, except a guard against something dangerous (for example, dropping a database the tests did not create).
- A config test is allowed only when it guards a security property that nothing else would catch (for example, compose ports bound to `127.0.0.1` only).

## Security

Treat every Security Guidance warning as a blocker: fix it, or explain to the user why it is a false positive. Never ignore one silently.
