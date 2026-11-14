---
name: "add-feature"
description: "Implement a new feature end-to-end with Superpowers (brainstorm, plan, TDD via subagents, verification) and finish with code review as the final QA gate. Use when asked to add, implement or build a feature."
---

# Add Feature

End-to-end workflow for implementing a feature. Every phase below names a Superpowers skill: invoke that skill with the Skill tool and follow it — do not paraphrase it from memory. Do not skip or reorder phases. Track the phases in a todo list so progress is visible.

**Required plugins:** superpowers, code-review, security-guidance. For Python projects also python-development (agents python-pro / fastapi-pro / django-pro). If a required plugin is missing, say so and stop before Phase 1.

## Phase 1 — Clarify: `superpowers:brainstorming`
- Turn the request into a short design. Ask clarifying questions one at a time.
- Go beyond the minimum: the spec is the floor (see "The spec is the floor, not the ceiling" in `docs/PRDs/roadmap.md`). Propose additions that are necessary, convenient or expected in a real product and not hard to build or defend (for example logout, change password, a "who am I" endpoint). For each one give what it is, why it matters, what it costs and your recommendation, and ask the user. Build nothing beyond the spec without her explicit yes; record rejected or postponed additions with the reason in the design doc.
- Output **acceptance criteria**: a numbered list of testable statements ("Given X, when Y, then Z"). A criterion about behaviour is proven by an automated test; a criterion about tooling or configuration is proven by a command that really runs it, as described in "What to test" in `CLAUDE.md`.
- Get the user's explicit approval of the design and criteria before moving on.

## Phase 2 — Isolate: `superpowers:using-git-worktrees`
- Create a feature branch in a worktree.
- Run the existing test suite on the untouched baseline. If it is not green, report it and ask the user how to proceed — do not build on a red baseline.

## Phase 3 — Plan: `superpowers:writing-plans`
- Break the work into small tasks shaped as vertical slices (one micro-feature each: code + its tests + the config, migration and docs it needs), never by layer. Each task names the files it touches, the test to write first, and the acceptance criterion it covers.
- Every acceptance criterion maps to at least one task. Show the plan to the user before implementing.

## Phase 4 — Implement: `superpowers:subagent-driven-development`
- One fresh subagent per task. Each subagent follows `superpowers:test-driven-development`: write the failing test, run it and see it fail for the right reason, write the minimal code, see it pass, refactor.
- Python projects: use the python-development agent matching the stack (fastapi-pro, django-pro, otherwise python-pro) and the project's own tooling (poetry, ruff, pyright, pytest).
- Rules for every subagent:
  - Never modify, weaken or delete existing tests to make them pass without asking the user.
  - Prefer a real database (testcontainers / docker compose) over mocks for integration tests when the project supports it.
  - On an unexpected failure use `superpowers:systematic-debugging` — no guess-and-retry.
  - Commit per micro-feature as described in "Commits" in `CLAUDE.md`: one slice per commit with a plain-words subject; review and lint fixes are folded into the slice they belong to.
  - Comments and docstrings follow "Comments" in `CLAUDE.md`: none by default, only a hidden reason that makes the code unsafe to change; never delete an existing one without the user asking.

## Phase 5 — Verify: `superpowers:verification-before-completion`
- Run the full checks fresh: linter, type checker, full test suite. Report each command with its actual result (e.g. `poetry run pytest` → 48 passed).
- Build a table: acceptance criterion → test or command that proves it → status. Any criterion without a passing test or command means the feature is not done.
- Resolve every warning Security Guidance raised during the session, or explain to the user why it is a false positive.

## Phase 6 — Final Quality Assurance: Code Review
This is the last phase and it is mandatory, even for small changes.
1. If the branch has an open pull request: run `/code-review` (code-review plugin).
   Otherwise: use `superpowers:requesting-code-review` to dispatch the code-reviewer subagent on the diff from the base branch to HEAD.
2. Process findings with `superpowers:receiving-code-review`: check each finding against the code before acting; push back on incorrect ones with reasons.
3. Fix all Critical and Important findings. After fixes, re-run Phase 5 and get the changed parts reviewed again.
4. The feature is done only when the review has no open Critical/Important findings AND Phase 5 is green.

## Finish: `superpowers:finishing-a-development-branch`
Present the options (merge / open PR / keep branch) and give a short report:
- acceptance criteria → tests table
- verification commands and results
- review findings: fixed, rejected (with reason), deferred

## Small changes
For a trivial change (a few lines, one file) the plan in Phase 3 may be a few bullet points and Phase 4 may run without subagents — but TDD, Phase 5 and Phase 6 still apply.