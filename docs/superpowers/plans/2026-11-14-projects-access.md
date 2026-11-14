# Projects and Access (Epic 4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create (`POST /projects`), list (`GET /projects`), read and edit (`GET`/`PUT /project/{id}/info`), delete (`DELETE /project/{id}`) projects and list their members (`GET /project/{id}/members`), with owner/participant access checked on every request.

**Architecture:** New feature package `projects/` shaped like `users/`: entities, a `ProjectRepository` Protocol with an SQLAlchemy and a psycopg implementation on both Units of Work, a service holding the access rules (404 for outsiders, 403 for a participant's delete) and the security log, and a router. Schema from the hand-written migration `0003` (`projects.owner_id` + `project_members` for participants only, two indexes).

**Tech Stack:** FastAPI, pydantic 2, SQLAlchemy 2 async + psycopg 3, Alembic, pytest + anyio, Poetry, ruff, pyright strict.

**Spec:** [`docs/superpowers/specs/2026-11-14-projects-access-design.md`](../specs/2026-11-14-projects-access-design.md). AC numbers below refer to its acceptance criteria.

## Global Constraints

- Endpoint names verbatim: `POST /projects`, `GET /projects`, `GET /project/{project_id}/info`, `PUT /project/{project_id}/info`, `DELETE /project/{project_id}`; addition `GET /project/{project_id}/members`. `project_id: UUID`.
- Every route takes `user: CurrentUser` (`from project_hub.auth.dependencies import CurrentUser`).
- No access (or unknown id) → `NotFoundError("Project not found")` (404). Participant deleting → `PermissionDeniedError("Only the project owner can delete the project")` (403).
- `name`: stripped, then 1–100 chars, no Unicode `Cc` character anywhere. `description`: 0–2000 chars, not stripped, default `""`, no `"\x00"`. Both bad cases → 422, never 500.
- `GET /projects`: `limit` 1–100 (default 50), `offset` 0–100000 (default 0), `role` `owner`|`participant`|absent; order `updated_at DESC, id DESC`.
- Constraint and index names exactly as in the spec's "Database — migration `0003`" section.
- Every repository change in BOTH `OrmProjectRepository` and `SqlProjectRepository`, proven by `tests/projects/test_repository_contract.py` (fixture `database`, params `orm`/`sql`; the file name must end in `_contract.py`).
- SQL backend: explicit `SAVEPOINT` / `ROLLBACK TO SAVEPOINT` around writes that can fail; never `conn.transaction()` or `pool.connection()` inside a UoW. All SQL parameterized (`%s`), never string-formatted.
- ORM `UPDATE … RETURNING` uses `.execution_options(populate_existing=True)` (pattern in `users/repository_orm.py`).
- Services call `await uow.commit()`; `get_uow` never commits. `projects/service.py` calls `uow.projects`; it never touches `uow.users` (it already has the `User` from `CurrentUser`).
- Comments (`CLAUDE.md` "Comments"): no comments or docstrings by default; write one only when code looks safe to change but is not (hidden reason). Never delete an existing comment or docstring. Before each commit check the diff for new `#` and `"""` lines.
- Tests prove behaviour only (`CLAUDE.md` "What to test"): endpoints through `TestClient`; no test that re-reads config files; no tests for `tests/support/` helpers. Never weaken or delete an existing test; the only existing test that changes is `test_upgrade_twice_is_noop` (head `0002` → `0003`, approved by the user).
- Commits (`CLAUDE.md` "Commits"): one slice per commit (code + tests + migration + README lines), plain-words subject on what one can now do, 1–3 line body. **No `Co-Authored-By` trailer.** Lint fixes go into the slice's own commit.
- Before each commit: `poetry run ruff check`, `poetry run ruff format --check`, `poetry run pyright`, `poetry run pytest` (Postgres up: `docker compose up -d --wait db`). If port 55433 is taken, use `APP_DB_PORT=55434` with `TEST_DATABASE_URL=postgresql://project_hub:project_hub@localhost:55434/postgres`.
- Do not touch `.github/workflows/`. Implementation agent: `python-development:python-development-fastapi-pro`.

## Review Focus

1. Wrong JSON types (`"name": 123`, `"description": null`) give 422, never 500. → Task 1 test `test_create_wrong_types_is_422`.
2. Non-ASCII names (`"Дипломный проект 🎓"`, 100 × `"я"`) are accepted and round-trip unchanged; the control-character check must not reject them, and the 100 limit counts characters (pydantic and `char_length` agree). → Task 1 test `test_create_accepts_unicode_name`.
3. A newline or tab at the **edge** of `name` is stripped and accepted (`"\tDiploma\n"` → `"Diploma"`); one **inside** (`"Dip\nloma"`) is 422. → Task 1 test `test_name_edge_whitespace_stripped_inner_control_rejected`.
4. A participant's `PUT` leaves `owner` unchanged and answers with `my_role == "participant"`. → Task 4 test `test_participant_update_keeps_owner_and_role`.
5. `offset` past the end of the list gives `200 []`, not an error. → Task 3 test `test_offset_past_end_is_empty`.

---

## File map

```
src/project_hub/
  projects/__init__.py
  projects/entities.py         ProjectRole, NewProject, Project, ProjectAccess (T1), ProjectMember (T6)
  projects/repository.py       ProjectRepository: add, get_for_user (T1), add_member (T2),
                               list_for_user (T3), update (T4), delete (T5), list_members (T6)
  projects/models.py           ProjectModel, ProjectMemberModel                                 (T1)
  projects/repository_orm.py   OrmProjectRepository                                             (T1–T5)
  projects/repository_sql.py   SqlProjectRepository                                             (T1–T5)
  projects/schemas.py          ProjectIn, OwnerResponse, ProjectResponse (T1), ProjectListItem (T3), MemberResponse (T6)
  projects/service.py          create_project, get_project (T1), list_projects (T3),
                               update_project (T4), delete_project (T5), list_members (T6), _log_event (T1)
  projects/router.py           routes                                                           (T1, T3–T5)
  db/uow.py, db/orm.py, db/sql.py   projects repository on both UoWs                            (T1)
  db/migrations/versions/0003_create_projects.py                                                (T1)
  main.py                      include projects router                                          (T1)
tests/
  support/auth.py              + signed_in(client, login) -> tuple[str, str]                    (T1)
  support/projects.py          create_project(...), add_participant(...)                        (T1, T2)
  db/test_migrations.py        new 0003 tests, head 0003, ORM metadata imports                  (T1)
  projects/__init__.py
  projects/test_repository_contract.py                                                          (T1–T5)
  projects/test_repository_orm.py   populate_existing guard for update                          (T4)
  projects/test_create_api.py, test_info_api.py (T1–T2), test_list_api.py (T3),
  test_update_api.py (T4), test_delete_api.py (T5), test_members_api.py (T6), test_projects_auth_api.py (T1, extended T3–T6),
  test_projects_log.py (T1, extended T5)
README.md                      "Projects" section, migration row 0003, future improvements      (T1–T5)
```

---

### Task 1: Create a project and read it back

Covers AC 1–7, 9, 10, 26 (for its two routes), 27, 28 (first half), 33, 34, 35, 36; Review Focus 1–3.

**Files:**
- Create: `src/project_hub/projects/{__init__,entities,repository,models,repository_orm,repository_sql,schemas,service,router}.py`, `src/project_hub/db/migrations/versions/0003_create_projects.py`, `tests/support/projects.py`, `tests/projects/__init__.py`, `tests/projects/test_repository_contract.py`, `tests/projects/test_create_api.py`, `tests/projects/test_info_api.py`, `tests/projects/test_projects_auth_api.py`, `tests/projects/test_projects_log.py`
- Modify: `src/project_hub/db/uow.py`, `src/project_hub/db/orm.py`, `src/project_hub/db/sql.py`, `src/project_hub/main.py`, `tests/support/auth.py`, `tests/db/test_migrations.py`, `README.md`

**Interfaces:**
- Produces:
  - `projects/entities.py`: `class ProjectRole(StrEnum)` with `OWNER = "owner"`, `PARTICIPANT = "participant"`; frozen slotted dataclasses `NewProject(owner_id: UUID, name: str, description: str)`, `Project(id: UUID, owner_id: UUID, name: str, description: str, created_at: datetime, updated_at: datetime)`, `ProjectAccess(project: Project, owner_login: str, role: ProjectRole)`.
  - `ProjectRepository.add(project: NewProject) -> Project`; `ProjectRepository.get_for_user(project_id: UUID, user_id: UUID) -> ProjectAccess | None`.
  - `UnitOfWork.projects: ProjectRepository` (both `OrmUnitOfWork` and `SqlUnitOfWork`).
  - `projects/schemas.py`: `ProjectIn(name, description="")`; `OwnerResponse(id: UUID, login: str)`; `ProjectResponse(id, name, description, owner: OwnerResponse, my_role: ProjectRole, created_at, updated_at)` with `@classmethod from_access(cls, access: ProjectAccess) -> Self`.
  - `projects/service.py`: `async def create_project(uow: UnitOfWork, user: User, data: ProjectIn) -> ProjectAccess`; `async def get_project(uow: UnitOfWork, user: User, project_id: UUID) -> ProjectAccess` (raises `NotFoundError("Project not found")`); `_log_event(event: str, user: User, project_id: UUID) -> None`, logger `project_hub.projects.service`, INFO, `extra={"event", "login", "user_id", "project_id"}`, message `"%s login=%r user_id=%s project_id=%s"`.
  - `projects/router.py`: `router = APIRouter(tags=["projects"])`; `POST /projects` (201) and `GET /project/{project_id}/info`, both `-> ProjectResponse`.
  - `tests/support/auth.py`: `signed_in(client: TestClient, login: str = "mila") -> tuple[str, str]` returns `(user_id, token)` (register + login).
  - `tests/support/projects.py`: `create_project(client: TestClient, token: str, name: str = "Diploma", description: str = "") -> dict[str, Any]` (asserts 201, returns the JSON).

- [ ] **Step 1: Write the failing migration tests** in `tests/db/test_migrations.py`
  - `test_upgrade_creates_projects_tables`: after `upgrade`, `information_schema.columns` for `projects` is `{("id","uuid","NO"), ("owner_id","uuid","NO"), ("name","text","NO"), ("description","text","NO"), ("created_at","timestamp with time zone","NO"), ("updated_at","timestamp with time zone","NO")}` and for `project_members` `{("project_id","uuid","NO"), ("user_id","uuid","NO"), ("created_at","timestamp with time zone","NO")}`; `pg_indexes` has `ix_projects_owner_id` and `ix_project_members_user_id`; `pg_constraint` names include all six from the spec.
  - `test_projects_constraints_reject_bad_rows`: plain-SQL inserts of a 101-char name and of `''` each raise `psycopg.errors.CheckViolation`; `DELETE FROM users` for a user who owns a project raises `psycopg.errors.ForeignKeyViolation`; deleting a project removes its `project_members` row.
  - `test_downgrade_to_0002_drops_projects`: `downgrade(url, "0002")` → `to_regclass('public.projects')` and `…project_members` are null, `users` still exists.
  - Change `test_upgrade_twice_is_noop` to expect `[("0003",)]`. In `test_orm_metadata_matches_migrated_schema` import `ProjectModel`, `ProjectMemberModel` and assert both table names are in `Base.metadata.tables`.

- [ ] **Step 2: Write the failing contract tests** in `tests/projects/test_repository_contract.py` (module docstring like `tests/users/test_repository_contract.py`; users created with `uow.users.add(NewUser(...))`)
  - `test_add_returns_project_with_generated_fields`: `type(p) is Project`, `isinstance(p.id, UUID)`, `p.created_at.tzinfo is not None`, `p.created_at == p.updated_at`, fields as given.
  - `test_get_for_user_owner_sees_role_owner`: after commit, `get_for_user(p.id, owner.id) == ProjectAccess(project=p, owner_login="mila", role=ProjectRole.OWNER)`.
  - `test_get_for_user_none_for_unknown_and_outsider`: `get_for_user(uuid4(), owner.id) is None`; `get_for_user(p.id, outsider.id) is None`.
  - `test_add_project_needs_commit`: add without commit → a new UoW's `get_for_user` is `None`.

- [ ] **Step 3: Write the failing API tests** (fixture `api_client`; helpers `signed_in`, `create_project`, `bearer`)
  - `test_create_api.py`: `test_create_returns_project_owned_by_caller` (201; `owner == {"id": user_id, "login": "mila"}`, `my_role == "owner"`, `created_at == updated_at`); `test_create_without_description_defaults_to_empty`; `test_create_strips_name` (`"  Diploma  "` → `"Diploma"`); `test_create_invalid_body_is_422` parametrized over `{"name": ""}`, `{"name": "   "}`, `{"name": "x"*101}`, `{"name": "Dip\x00loma"}`, `{"name": "Dip\nloma"}`, `{"name": "Dip\tloma"}`, `{"name": "Dip\x7floma"}`, `{"name": "ok", "description": "x"*2001}`, `{"name": "ok", "description": "a\x00b"}`, `{}` — each 422 (never 500), and `SELECT count(*) FROM projects` through `migrated_database_url` is 0 afterwards; `test_create_keeps_description_newlines_and_tabs` (`"line 1\n\tline 2"` round-trips, AC 4a); `test_duplicate_names_allowed`; `test_create_wrong_types_is_422` (`{"name": 123}`, `{"name": "ok", "description": None}`); `test_create_accepts_unicode_name` (`"Дипломный проект 🎓"` and `"я"*100` → 201, returned unchanged); `test_name_edge_whitespace_stripped_inner_control_rejected` (`"\tDiploma\n"` → 201 `"Diploma"`; `"Dip\nloma"` → 422).
  - `test_info_api.py`: `test_owner_reads_info` (200, equal to the create response); `test_outsider_gets_same_404_as_unknown_id` (Anna's GET on Mila's project and a GET on `uuid4()` both give 404 with identical bodies `{"detail": "Project not found"}`); `test_non_uuid_id_is_422`.
  - `test_projects_auth_api.py`: `test_routes_require_token` parametrized over `("POST", "/projects")`, `("GET", f"/project/{uuid4()}/info")` × headers `{}` and `bearer("garbage")` → 401 with `www-authenticate == "Bearer"`. Later tasks append their routes to the parameter list.
  - `test_projects_log.py`: `test_create_is_logged_without_name` (caplog on `project_hub.projects.service`: exactly one record, `event == "project created"`, `login == "mila"`, `user_id`/`project_id` match the response as `UUID`, and the project name is not in `record.getMessage()`).

- [ ] **Step 4: Run them to verify they fail**

Run: `poetry run pytest tests/projects tests/db/test_migrations.py -q`
Expected: FAIL (import errors for `project_hub.projects…`, 404 for `/projects`, head is `0002`).

- [ ] **Step 5: Write migration `0003_create_projects.py`** (`revision = "0003"`, `down_revision = "0002"`) creating both tables, constraints and indexes exactly as in the spec; `downgrade()` drops `project_members` then `projects`.

- [ ] **Step 6: Implement entities, Protocol (`add`, `get_for_user`), models, both repositories, UoW wiring**
  - Models mirror the migration (constraint and index names, `ondelete`, server defaults) so `compare_metadata` is empty; `eager_defaults` like `UserModel`.
  - `get_for_user`: one query joining `users` on `owner_id` for `owner_login`; access when `owner_id = :user_id OR EXISTS (SELECT 1 FROM project_members WHERE project_id = p.id AND user_id = :user_id)`; role `owner` when `owner_id = :user_id`, else `participant`.

- [ ] **Step 7: Implement schemas, service (`create_project`, `get_project`, `_log_event`), router; include the router in `main.py`**
  - `ProjectIn.name`: `StringConstraints(strip_whitespace=True, min_length=1, max_length=100)` plus an `AfterValidator` rejecting any `unicodedata.category(ch) == "Cc"`; `description`: `max_length=2000` plus a validator rejecting `"\x00"`.
  - `create_project` builds `ProjectAccess(project, owner_login=user.login, role=ProjectRole.OWNER)` from `add`'s result, commits, then logs `project created`.

- [ ] **Step 8: Run the tests to verify they pass**

Run: `poetry run pytest tests/projects tests/db/test_migrations.py -q`
Expected: PASS for both `[orm]` and `[sql]` params.

- [ ] **Step 9: README** — add a "Projects" section (create and info routes, request rules, 404 rule, log event), the migration row `0003 | creates projects (owner_id → users, RESTRICT) and project_members (participants), indexes on owner_id and user_id`.

- [ ] **Step 10: Full checks and commit**

Run: `poetry run ruff check && poetry run ruff format --check && poetry run pyright && poetry run pytest -q`
Expected: all green.
```bash
git commit -m "Create a project with POST /projects and read it back" -m "Migration 0003 adds projects and project_members; both repositories,
GET /project/{id}/info for the owner, 404 for everyone else, creation logged."
```

---

### Task 2: Let participants open a shared project

Covers AC 8, 28 (second half), 29.

**Files:**
- Modify: `src/project_hub/projects/repository.py`, `repository_orm.py`, `repository_sql.py`, `tests/support/projects.py`, `tests/projects/test_repository_contract.py`, `tests/projects/test_info_api.py`

**Interfaces:**
- Consumes: Task 1 entities and repository.
- Produces: `ProjectRepository.add_member(project_id: UUID, user_id: UUID) -> None` (raises `ConflictError("User is already a participant of this project")` on `pk_project_members`); `tests/support/projects.py`: `add_participant(database_url: str, project_id: str, user_id: str) -> None` (plain psycopg `INSERT INTO project_members … ` with `%s`, committed).

- [ ] **Step 1: Write the failing tests**
  - Contract: `test_add_member_gives_participant_access` (`get_for_user(p.id, anna.id)` → `ProjectAccess(project=p, owner_login="mila", role=ProjectRole.PARTICIPANT)`); `test_add_member_twice_conflicts_and_uow_stays_usable` (second call raises `ConflictError`; a following `add` in the same UoW commits fine); `test_add_member_unknown_ids_raise_and_uow_stays_usable` (`uuid4()` as project and as user each raise a non-`ConflictError` exception; the UoW then still commits a new project).
  - API (`test_info_api.py`): `test_participant_reads_info` (Anna, added with `add_participant(migrated_database_url, …)`, gets 200 with `my_role == "participant"` and `owner == {"id": mila_id, "login": "mila"}`).
- [ ] **Step 2: Run them** — `poetry run pytest tests/projects -q` → FAIL (`add_member` missing).
- [ ] **Step 3: Implement `add_member`** in both repositories (savepoint pattern of `SqlUserRepository.add` / `begin_nested` of `OrmUserRepository.add`; map only `pk_project_members` to `ConflictError`).
- [ ] **Step 4: Run** `poetry run pytest tests/projects -q` → PASS.
- [ ] **Step 5: README** — one line: participants (added by invites in epic 5) read and edit like the owner.
- [ ] **Step 6: Full checks and commit**
```bash
git commit -m "Let participants open a project shared with them" -m "add_member on both repositories records a participant; info answers them
with my_role participant. Invites that call it come in epic 5."
```

---

### Task 3: List my projects with GET /projects

Covers AC 11, 12, 13 (order), 14, 15, 16, 26 (route), 30; Review Focus 5.

**Files:**
- Modify: `src/project_hub/projects/repository.py`, `repository_orm.py`, `repository_sql.py`, `schemas.py`, `service.py`, `router.py`, `tests/projects/test_repository_contract.py`, `tests/projects/test_projects_auth_api.py`, `README.md`
- Create: `tests/projects/test_list_api.py`

**Interfaces:**
- Consumes: Tasks 1–2.
- Produces: `ProjectRepository.list_for_user(user_id: UUID, *, role: ProjectRole | None, limit: int, offset: int) -> list[ProjectAccess]`; `ProjectListItem(ProjectResponse)` adding `documents` (a list type of the implementer's choice that serializes to `[]`, always empty in this epic) with `from_access`; `service.list_projects(uow: UnitOfWork, user: User, *, role: ProjectRole | None, limit: int, offset: int) -> list[ProjectAccess]`; route `GET /projects -> list[ProjectListItem]` with `Query` bounds from Global Constraints.

- [ ] **Step 1: Write the failing tests**
  - Contract: `test_list_for_user_returns_owned_and_shared_newest_first` (three projects whose `updated_at` is set apart with plain SQL `UPDATE projects SET updated_at = now() - interval '…'` through `migrated_database_url`, one of them shared; a fourth project of another user is absent; order `updated_at DESC`); `test_list_for_user_ties_ordered_by_id_desc` (three projects with the same `updated_at`, set by SQL → order is `id DESC`); `test_list_for_user_filters_by_role`; `test_list_for_user_pages_with_limit_and_offset` (5 projects, `limit=2` at offsets 0, 2, 4 → 2, 2, 1 items, concatenated equal to the full list); `test_list_for_user_owner_listed_once_even_if_member` (an `add_member(p.id, owner.id)` row → the project appears once, role `owner`).
  - API (`test_list_api.py`): `test_empty_list`; `test_lists_owned_and_shared_with_roles_and_documents` (AC 12: exactly three items, right `my_role`, each `documents == []`); `test_role_filter`; `test_paging_has_no_overlap_or_gap`; `test_offset_past_end_is_empty` (`offset=50` with 2 projects → `200 []`); `test_invalid_query_is_422` parametrized over `limit=0`, `limit=101`, `offset=-1`, `offset=100001`, `role=admin`.
  - Auth: append `("GET", "/projects")`.
- [ ] **Step 2: Run** `poetry run pytest tests/projects -q` → FAIL.
- [ ] **Step 3: Implement `list_for_user`** in both repositories (same access condition and role expression as `get_for_user`; `role` filter: `owner_id = :user_id` or the `EXISTS` branch with `owner_id <> :user_id`; `ORDER BY updated_at DESC, id DESC LIMIT … OFFSET …`), then `list_projects`, `ProjectListItem`, the route.
- [ ] **Step 4: Run** `poetry run pytest tests/projects -q` → PASS.
- [ ] **Step 5: README** — the list route, order, paging bounds, role filter, `documents` filled in epic 6, no total count (ask for `limit + 1`).
- [ ] **Step 6: Full checks and commit**
```bash
git commit -m "List my projects with GET /projects, newest first" -m "Owned and shared projects with my_role and an empty documents list;
limit/offset paging and a role filter."
```

---

### Task 4: Edit a project's name and description with PUT /project/{id}/info

Covers AC 13 (update moves to top), 17–21, 26 (route), 31; Review Focus 4.

**Files:**
- Modify: `src/project_hub/projects/repository.py`, `repository_orm.py`, `repository_sql.py`, `service.py`, `router.py`, `tests/projects/test_repository_contract.py`, `tests/projects/test_list_api.py`, `tests/projects/test_projects_auth_api.py`, `README.md`
- Create: `tests/projects/test_update_api.py`, `tests/projects/test_repository_orm.py`

**Interfaces:**
- Consumes: Tasks 1–3.
- Produces: `ProjectRepository.update(project_id: UUID, name: str, description: str) -> Project | None` (sets `updated_at = now()`); `service.update_project(uow: UnitOfWork, user: User, project_id: UUID, data: ProjectIn) -> ProjectAccess`; route `PUT /project/{project_id}/info -> ProjectResponse`.

- [ ] **Step 1: Write the failing tests**
  - Contract: `test_update_changes_fields_and_updated_at` (create and commit in one UoW, update in a second: new name/description, `updated_at > created_at`); `test_update_unknown_id_returns_none`; `test_update_is_fresh_after_earlier_read` (`get_for_user`, `update`, `get_for_user` in one UoW → the second read shows new values); `test_update_needs_commit`.
  - ORM guard (`test_repository_orm.py`, pattern of `tests/users/test_repository_orm.py`): `test_update_refreshes_a_stale_model_held_in_the_session`.
  - API (`test_update_api.py`): `test_owner_updates_info` (200, new values, `updated_at` later, following GET shows them); `test_participant_updates_info`; `test_participant_update_keeps_owner_and_role`; `test_outsider_and_unknown_id_get_404_and_nothing_changes`; `test_invalid_body_is_422_and_nothing_changes` (reuse the invalid bodies of Task 1 with `{"name": "ok", …}` adjusted); `test_omitted_description_becomes_empty`.
  - List (`test_list_api.py`): `test_update_moves_project_to_top`.
  - Auth: append `("PUT", f"/project/{uuid4()}/info")` (send a valid body so the 401 is about the token).
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement `update`** in both repositories (`UPDATE … SET name, description, updated_at = now() … RETURNING`, ORM with `populate_existing=True`), then `update_project` (`get_project` first; `None` from `update` → `NotFoundError("Project not found")`; returns `ProjectAccess(updated, access.owner_login, access.role)`; commit) and the route.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: README** — PUT route: replaces both fields, owner and participants, omitted description becomes `""`.
- [ ] **Step 6: Full checks and commit**
```bash
git commit -m "Edit a project's name and description with PUT /project/{id}/info" -m "Owner and participants replace both fields; updated_at moves the project
to the top of the list; outsiders get 404."
```

---

### Task 5: Delete a project with DELETE /project/{id} (owner only)

Covers AC 22–25, 26 (route), 32.

**Files:**
- Modify: `src/project_hub/projects/repository.py`, `repository_orm.py`, `repository_sql.py`, `service.py`, `router.py`, `tests/projects/test_repository_contract.py`, `tests/projects/test_projects_auth_api.py`, `tests/projects/test_projects_log.py`, `README.md`
- Create: `tests/projects/test_delete_api.py`

**Interfaces:**
- Consumes: Tasks 1–4.
- Produces: `ProjectRepository.delete(project_id: UUID) -> bool`; `service.delete_project(uow: UnitOfWork, user: User, project_id: UUID) -> None`; route `DELETE /project/{project_id}`, `status_code=204`, `response_class=Response`.

- [ ] **Step 1: Write the failing tests**
  - Contract: `test_delete_removes_project_and_members` (`True`; afterwards `get_for_user` is `None` for owner and participant and a plain-SQL count of `project_members` for it is 0); `test_delete_unknown_id_returns_false`; `test_delete_needs_commit`.
  - API (`test_delete_api.py`): `test_owner_deletes_project` (204, empty body; then GET info is 404 for owner and former participant; it is gone from both lists); `test_participant_cannot_delete` (403 `{"detail": "Only the project owner can delete the project"}`; owner still reads it); `test_outsider_and_unknown_id_get_404`.
  - Log: `test_delete_is_logged` (one `project deleted` record with login, user id, project id; none for the 403 and 404 attempts).
  - Auth: append `("DELETE", f"/project/{uuid4()}")`.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement `delete`** in both repositories, then `delete_project` (`get_project` first; role `participant` → `PermissionDeniedError`; `delete` returning `False` → `NotFoundError("Project not found")` without a log record; commit; log `project deleted`) and the route.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: README** — delete route and the 404/403 rule; "Known limitations and future improvements" gets the spec's Future improvements list, and the `DELETE /users/me` line is updated: a user who owns projects cannot be deleted (`RESTRICT`); the planned endpoint answers a clear 409 and the frontend explains it.
- [ ] **Step 6: Full checks and commit**
```bash
git commit -m "Delete a project with DELETE /project/{id}, owner only" -m "Participants get 403, everyone else 404; project_members go with the
project; deletion is logged. Epic 6 adds document cleanup in delete_project."
```

---

### Task 6: See who has access with GET /project/{id}/members

Covers AC 37–40 and 26 (route). Addition 9 of the spec, requested by the frontend session.

**Files:**
- Modify: `src/project_hub/projects/entities.py`, `repository.py`, `repository_orm.py`, `repository_sql.py`, `schemas.py`, `service.py`, `router.py`, `tests/projects/test_repository_contract.py`, `tests/projects/test_projects_auth_api.py`, `README.md`
- Create: `tests/projects/test_members_api.py`

**Interfaces:**
- Consumes: Tasks 1–5 (`add_member`, `delete`, `add_participant`).
- Produces: `ProjectMember(user_id: UUID, login: str, role: ProjectRole, joined_at: datetime)` (frozen, slotted); `ProjectRepository.list_members(project_id: UUID) -> list[ProjectMember]`; `MemberResponse(id: UUID, login: str, role: ProjectRole, joined_at: datetime)` with `from_member`; `service.list_members(uow: UnitOfWork, user: User, project_id: UUID) -> list[ProjectMember]`; route `GET /project/{project_id}/members -> list[MemberResponse]`.

- [ ] **Step 1: Write the failing tests**
  - Contract: `test_list_members_owner_first_then_participants_by_join_time` (owner with `joined_at == project.created_at`, then two participants added in separate committed UoWs, in that order); `test_list_members_unknown_project_is_empty`; `test_list_members_empty_after_delete`.
  - API (`test_members_api.py`): `test_owner_sees_members` (AC 37: exact list `[{"id", "login", "role", "joined_at"}…]`, owner first, `joined_at` of the owner equals the project's `created_at`); `test_participant_sees_same_members`; `test_outsider_and_unknown_id_get_404`.
  - Auth: append `("GET", f"/project/{uuid4()}/members")`.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement `list_members`** in both repositories (owner row from `projects` joined with `users`, `UNION ALL` participant rows from `project_members` joined with `users`; order owner first, then `joined_at`, then `login`), then the service function (`get_project` first), schema and route.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: README** — the members route, its access rule, no paging, `avatar` comes with frontend epic F1.
- [ ] **Step 6: Full checks and commit**
```bash
git commit -m "See who has access to a project with GET /project/{id}/members" -m "Owner first, then participants in join order; same access rule as info.
Requested by the frontend for the project page's Members panel."
```

---

## Final verification (after Task 6)

- `poetry run ruff check`, `poetry run ruff format --check`, `poetry run pyright`, `poetry run pytest -v | tee pytest.log` and `poetry run python -m tests.support.backend_coverage pytest.log`, `poetry run pytest -m docker -q` — quote the real output.
- Build the AC → test table (AC 1–41) for the report; AC 41 is proven by these commands and by CI on the PR.
