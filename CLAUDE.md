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
3. **Any code change** → `superpowers:test-driven-development`: failing test first, then code.
4. **Before saying "done", "fixed" or "passing"** → `superpowers:verification-before-completion`: run the checks and quote the real output.
5. **Before merge / PR** → code review: `/code-review` if a PR exists, otherwise `superpowers:requesting-code-review`; handle findings with `superpowers:receiving-code-review`.
6. **Finishing a branch** → `superpowers:finishing-a-development-branch`.

## Python

- Delegate Python implementation to the matching `python-development` agent: `python-development:python-development-fastapi-pro` for FastAPI, `python-development:python-development-django-pro` for Django, otherwise `python-development:python-pro`.
- Use the relevant `python-development:*` skills (testing patterns, type safety, code style, error handling, project structure, packaging) when the task touches that area.
- Tooling: `poetry`, `ruff`, `pyright`, `pytest`.

## Security

Treat every Security Guidance warning as a blocker: fix it, or explain to the user why it is a false positive. Never ignore one silently.
