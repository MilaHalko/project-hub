---
name: "add-frontend-feature"
description: "Use when asked to add, build or change anything in the web frontend: a page, screen, form, component or user flow, including small UI tweaks and changes made under time pressure (\"quick\", \"for the demo\"). Frontend counterpart of add-feature."
---

# Add Frontend Feature

End-to-end workflow for a frontend feature. It is `add-feature` with the frontend parts added: an agreed look before code, real-browser tests, an automated accessibility gate and a frontend security checklist. Every phase names a skill: invoke it with the Skill tool and follow it. Do not skip or reorder phases. Track the phases in a todo list.

**Required plugins:** superpowers, code-review, security-guidance, frontend-design, design, playwright. axe-accessibility is used when its server is connected (it needs the user's Deque login; agents never enter keys). If a required plugin is missing, say so and stop before Phase 1.

**Frontend space:** the frontend has its own plan in `docs/frontend/` (design doc, roadmap, decisions), kept apart from the backend roadmap `docs/PRDs/roadmap.md`. Read it first. Stack, style and folder layout come from there; do not re-ask what it already decides. If it does not exist yet, say so and ask before choosing a stack.

**Time pressure changes the size of each phase, never the list of phases.** "Quick", "for the demo", "just make it look decent" means fewer screens and less polish, not skipping tests, the browser run, the accessibility gate or the review.

## Phase 1 — Clarify: `superpowers:brainstorming`
- Turn the request into a short design: which screens, what the user does on each, which API endpoints they call.
- For every screen list its states: loading, empty, error (401, 403, 404, 422, network down), success.
- The spec is the floor (see "The spec is the floor, not the ceiling" in `docs/PRDs/roadmap.md`): propose useful extras with what, why, cost and a recommendation; build none without the user's yes; record rejected ones in the design doc.
- Output **acceptance criteria** ("Given X, when Y, then Z"). Behaviour is proven by a test (component or end-to-end); tooling by a command that runs it ("What to test" in `CLAUDE.md`).
- If the feature needs a backend change (new endpoint, CORS origin, a field), list it as its own criterion. It is built with the backend rules: `python-development:python-development-fastapi-pro`, pytest against real Postgres on both DB backends.
- Get the user's explicit approval before moving on.

## Phase 2 — Look: `frontend-design:frontend-design`
- Before any production code, show the look: a mockup or a throwaway prototype of each new screen in the project's style (from `docs/frontend/`). The user may also bring a design from Claude Design; then use that.
- Run `design:design-critique` on it and fix what it finds. Use `design:ux-copy` for buttons, errors and empty states.
- Get the user's yes on the look. The prototype is thrown away; production code is written test-first in Phase 5.

## Phase 3 — Isolate: `superpowers:using-git-worktrees`
- Feature branch in a worktree. Install dependencies from the lockfile (`npm ci` or the stack's equivalent) and run the existing frontend checks and tests on the untouched baseline. Not green: report and ask.
- No frontend yet (first frontend feature): the first slice of the plan is the scaffold from `docs/frontend/` with lint, type check, component tests, Playwright with axe-core, and a CI job that runs them, proven by running each command once.

## Phase 4 — Plan: `superpowers:writing-plans`
- Tasks are vertical slices: one screen or one user flow each, with its component tests, its end-to-end test and the config it needs. Never by layer ("components", "styles", "tests").
- Each task names files, the first failing test and the criteria it covers. Show the plan to the user.

## Phase 5 — Implement: `superpowers:subagent-driven-development`
- One fresh subagent per task, each following `superpowers:test-driven-development`: failing test first, see it fail for the right reason, minimal code, green, refactor.
- Test what the user sees and does (labels, roles, text, clicks), not component internals or markup snapshots.
- Every user flow gets an **end-to-end test with the Playwright test runner**, committed to the repo, run against the real API and Postgres from `docker compose`, not against mocks. Each test creates the data it needs through the API (for example its own user with a unique login via `POST /auth`), so tests do not depend on each other or on seed data.
- Every page visited by an end-to-end test gets an **automated accessibility check with axe-core** (`@axe-core/playwright` or the stack's equivalent): the test fails on any WCAG 2.1 AA violation. This needs no account and runs in CI.
- Rules for every subagent: never weaken or delete existing tests without asking; on an unexpected failure use `superpowers:systematic-debugging`; commit per micro-feature ("Commits" in `CLAUDE.md`), for example "Log in from the login page and land on the projects list".

## Phase 6 — Verify: `superpowers:verification-before-completion`
Run fresh and quote each command with its real result:
- lint, type check, component tests, production build;
- end-to-end tests (with the axe checks) against the running stack;
- backend checks too if the backend changed (`poetry run ruff check`, `pyright`, `pytest`).

Then look at it in a real browser with the playwright tools (`mcp__plugin_playwright_playwright__*`): walk each flow, take screenshots at desktop and phone width (about 1280 and 375 px), and check the browser console has no errors. Show the screenshots to the user.

Accessibility: run `design:accessibility-review` on the new screens. If the axe MCP server is connected, also run `axe-accessibility:mcp-audit`; if it is not, say so in one line. The axe-core tests from Phase 5 are the gate either way.

Security checklist (each item: done, or why it does not apply):
- the JWT lives in memory; `sessionStorage` only with the user's yes; never `localStorage`, never in a URL;
- no raw HTML from data (`innerHTML`, `dangerouslySetInnerHTML`, `v-html`) unless sanitized, and the user is told why it is needed;
- no secrets in frontend code or its env files: everything shipped to the browser is public;
- backend CORS allows only the known frontend origins, never `*` with credentials;
- a Content Security Policy is set where the app is served, without `unsafe-inline` scripts;
- dependency audit (`npm audit --audit-level=high` or the stack's equivalent) has no open high or critical issue; the lockfile is committed.

Resolve every Security Guidance warning, or explain to the user why it is a false positive.

Build the table: acceptance criterion → test or command → status. Any criterion without a passing test or command means not done.

## Phase 7 — Final Quality Assurance: Code Review
Mandatory, even for small changes.
1. Open PR: `/code-review`. No PR: `superpowers:requesting-code-review` on the diff from the base branch. Give the reviewer the screenshots too.
2. Handle findings with `superpowers:receiving-code-review`; fix all Critical and Important ones, re-run Phase 6, get the changes reviewed again.
3. Done only when the review has no open Critical/Important findings and Phase 6 is green.

## Finish: `superpowers:finishing-a-development-branch`
Present the options and a short report: criteria → tests table, verification commands and results, screenshots, security checklist, review findings (fixed, rejected with reason, deferred).

## Red flags

| Thought | Reality |
|---|---|
| "It's for tomorrow's demo, skip the browser test" | The demo is a browser run. Automate it once; it also proves the page works tomorrow. |
| "axe MCP is not connected, so skip accessibility" | The axe-core end-to-end check needs no account. It is the gate. |
| "Component tests pass, that's enough" | Component tests mock the API. Only the end-to-end test proves the page works with the real backend. |
| "I'll pick React, it's quick" | The stack is decided in `docs/frontend/`. Read it. |
| "localStorage is simpler for the token" | Any injected script can read it. Memory, or sessionStorage with the user's yes. |
| "I'll style it after it works" | The look is agreed in Phase 2, before code. |
| "One commit for the page, one for tests" | One commit is one slice: the screen, its tests and its config together. |

## Small changes
For a trivial change (text, colour, spacing on one screen) Phases 2 and 4 may be a sentence each and Phase 5 may run without subagents. The browser check with screenshots, the axe-core check on the touched page, Phase 6 and Phase 7 still apply.
