# Epic 4: Projects and access

Date: 2026-11-14
Status: approved design (2026-11-14)
Roadmap: [`docs/PRDs/roadmap.md`](../../PRDs/roadmap.md), epic 4
Spec: [`docs/initial-spec.md`](../../initial-spec.md) — `POST /projects`, `GET /projects`,
`GET /project/<project_id>/info`, `PUT /project/<project_id>/info`,
`DELETE /project/<project_id>`; "2 types of access – owner … and participant"

## Intent

Let a logged-in user create projects, see every project they can access, edit a
project's name and description, and delete their own projects. This epic also
lays down the access model every later epic uses: an **owner** (the creator, can
do anything) and **participants** (invited users, can do everything except
delete the project). Invites themselves come in epic 5 and documents in epic 6,
so this epic must leave the response shape and the delete path ready for them
without breaking anything later.

The project is defended in front of a mentor, so the access rules must be easy to
explain and to show live in Swagger: create a project as Mila, see it in the list,
log in as Anna and get 404 for Mila's project.

## Goals

- `POST /projects` creates a project from `name` and `description`; the caller
  becomes its owner (spec).
- `GET /projects` lists every project the caller owns or participates in, each
  with a `documents` list (spec; the list is empty until epic 6).
- `GET /project/<id>/info` and `PUT /project/<id>/info` read and replace name and
  description, for the owner and for participants (spec, roadmap roles).
- `DELETE /project/<id>` deletes the project, owner only (spec).
- Access is checked on every request through `CurrentUser`.
- Additions accepted by the user (see [Beyond the spec](#beyond-the-spec)): a
  stable sort order, `limit`/`offset` paging and a `role` filter on
  `GET /projects`, and security-log records for project creation and deletion.

## Non-goals

- Inviting users (`POST /project/<id>/invite`) — epic 5. This epic only adds the
  repository method that records a participant, so participant access can be
  tested now and epic 5 can build on it.
- Documents and S3 — epic 6. `documents` is always `[]` here.
- Anything in [Future improvements](#future-improvements).

## Anti-goals (it would be a failure even if it "works")

- A user who is neither owner nor participant can read, change or delete a
  project, or can tell from the response that a project with that id exists.
- A participant can delete a project.
- A project ends up with no owner or with two owners.
- Epic 6 has to change the shape of `GET /projects` (rename or remove a field).
- Deleting a project leaves orphaned `project_members` rows.
- Any database query is built by string formatting with user input.

## Constraints

- Endpoint names exactly as in the spec (`/projects` plural for create and list,
  `/project/<id>` singular for one project).
- Swappable data layer (roadmap, epic 1b design): a `ProjectRepository` Protocol,
  an SQLAlchemy and a psycopg implementation, the repository on both Units of
  Work, ORM objects never leave the repository, the schema comes from a
  hand-written Alembic migration, and shared contract tests run on both backends.
- "What to test" in `CLAUDE.md`: endpoints through `TestClient`, repositories on
  real Postgres for both backends, migrations against a real database; no tests
  that re-read config files.
- Migration head is `0002`; this epic adds `0003` (`down_revision = "0002"`).
- Error mapping already exists: `NotFoundError` → 404, `PermissionDeniedError` →
  403, `ValidationFailedError` → 422, all with `{"detail": str}`.

## Approaches considered

### Where the owner is stored

| | A. `projects.owner_id` + `project_members` for participants only | B. Only `project_members(project_id, user_id, role)`, owner is a row | C. Both: `owner_id` and an owner row in `project_members` |
|---|---|---|---|
| "Exactly one owner" | guaranteed by `owner_id NOT NULL` | needs a partial unique index; "at least one" cannot be enforced | needs circular foreign keys with deferred checks |
| Listing "my projects" | owner OR participant (one `OR` with `EXISTS`) | one join | one join |
| Create | one insert | two inserts | two inserts |
| Roles stay clear | yes — `project_members` means "invited" | owner mixed with participants | owner mixed with participants; the same fact stored twice |

**Chosen: A** (user, 2026-11-14). It is the normalized form: each fact lives in
one place, and the database itself rules out an ownerless or two-owner project.
The `OR` costs nothing measurable with the indexes below. C was considered at the
user's request and rejected: it duplicates the ownership fact (denormalization)
without a real read gain, and it would make epic 5 remember everywhere that the
owner is "also a participant" (invite, participant list, member removal).

### Status code for someone else's project

| | 404 for everything | 403 for everything | **404 for outsiders, 403 for a participant's forbidden action** |
|---|---|---|---|
| Hides that the project exists | yes | no | yes, from people who have no access |
| Clear error for a participant | no | yes | yes |

**Chosen: the mixed rule, as GitHub does it** (user, 2026-11-14). A user with no
access gets 404 `Project not found` for every operation, exactly as for an id that
does not exist. A participant already knows the project exists, so trying to
delete it gives 403.

## Beyond the spec

Proposed to the user with what, why and cost; decisions of 2026-11-14.

| # | Addition | Decision |
|---|---|---|
| 1 | Sort `GET /projects` by most recently updated first | **accepted** |
| 2 | Paging `GET /projects?limit=&offset=`; the response stays a plain list | **accepted** |
| 3 | Filter `GET /projects?role=owner\|participant` (tabs "My projects" / "Shared with me") | **accepted** |
| 4 | Security-log records `project created` and `project deleted` | **accepted** |
| 5 | Participant list in project info | postponed → [Future improvements](#future-improvements) |
| 6 | Owner removes a participant; participant leaves a project | postponed → Future improvements |
| 7 | `DELETE /users/me` | postponed → Future improvements |
| 8 | Search by name `?q=` | rejected for now → Future improvements |

## Design

### Layout

New package `src/project_hub/projects/`, following `users/`:

| File | Holds |
|---|---|
| `entities.py` | `ProjectRole` (`StrEnum`: `owner`, `participant`), `NewProject`, `Project`, `ProjectAccess` (frozen, slotted dataclasses) |
| `repository.py` | `ProjectRepository` Protocol |
| `models.py` | `ProjectModel`, `ProjectMemberModel` (SQLAlchemy) |
| `repository_orm.py`, `repository_sql.py` | the two implementations |
| `schemas.py` | request and response models |
| `service.py` | access rules, logging; no HTTP |
| `router.py` | the five routes |

`db/uow.py` gets `projects: ProjectRepository`; `db/orm.py` and `db/sql.py` build
the matching repository; `main.py` includes the router.

### Entities

- `NewProject(owner_id: UUID, name: str, description: str)`
- `Project(id, owner_id, name, description, created_at, updated_at)`
- `ProjectAccess(project: Project, owner_login: str, role: ProjectRole)` — a project
  as seen by one user: what the API returns needs the owner's login and the
  caller's role, and both come from the same query that checks access.

### Database — migration `0003`

```
projects
  id           uuid        PK, default gen_random_uuid()
  owner_id     uuid        NOT NULL, FK → users(id) ON DELETE RESTRICT
  name         text        NOT NULL, CHECK (char_length(name) BETWEEN 1 AND 100)
  description  text        NOT NULL, default '', CHECK (char_length(description) <= 2000)
  created_at   timestamptz NOT NULL, default now()
  updated_at   timestamptz NOT NULL, default now()
  index ix_projects_owner_id (owner_id)

project_members
  project_id   uuid        FK → projects(id) ON DELETE CASCADE
  user_id      uuid        FK → users(id)    ON DELETE CASCADE
  created_at   timestamptz NOT NULL, default now()
  PK (project_id, user_id)
  index ix_project_members_user_id (user_id)
```

- Constraint names are explicit (`fk_projects_owner_id_users`,
  `ck_projects_name_length`, `ck_projects_description_length`,
  `fk_project_members_project_id_projects`, `fk_project_members_user_id_users`,
  `pk_project_members`) so error handling and the ORM models can refer to them.
- The `CHECK`s repeat the pydantic limits as a second line of defense; the API
  never reaches them with valid input.
- `owner_id … ON DELETE RESTRICT`: a user who owns projects cannot be deleted by
  accident. When `DELETE /users/me` comes, it has to delete the projects (and,
  after epic 6, their files) explicitly instead of a silent cascade that would
  leave files in S3.
- `project_members … ON DELETE CASCADE` on both sides: deleting a project removes
  its participants; deleting a user removes their memberships.
- `updated_at` is set to `now()` by the update statement itself (no trigger).
- `downgrade()` drops `project_members`, then `projects`.

**Indexes** (agreed with the user, 2026-11-14):

| Query | Served by |
|---|---|
| one project by id (info, update, delete) | `projects` primary key |
| "is this user a participant of this project?" | `project_members` primary key `(project_id, user_id)` |
| cascade delete of a project's participants | the same primary key (leads with `project_id`) |
| "projects I own" | `ix_projects_owner_id` |
| "projects I participate in" | `ix_project_members_user_id` |
| sort by `updated_at` | no index: one user's projects are few, found through the two indexes above, then sorted in memory; one index could not serve the order anyway because the list merges two sources |

### Repository Protocol

```python
class ProjectRepository(Protocol):
    async def add(self, project: NewProject) -> Project: ...
    async def get_for_user(self, project_id: UUID, user_id: UUID) -> ProjectAccess | None: ...
    async def list_for_user(
        self, user_id: UUID, *, role: ProjectRole | None, limit: int, offset: int
    ) -> list[ProjectAccess]: ...
    async def update(self, project_id: UUID, name: str, description: str) -> Project | None: ...
    async def delete(self, project_id: UUID) -> bool: ...
    async def add_member(self, project_id: UUID, user_id: UUID) -> None: ...
```

- `get_for_user` returns `None` both when the project does not exist and when the
  user has no access — the repository cannot tell them apart by design, so the
  404 rule cannot leak by mistake.
- `role` is `owner` when `owner_id = user_id`, otherwise `participant`.
- `list_for_user` orders by `updated_at DESC, id DESC` (the id breaks ties so pages
  never overlap or skip), filters by role when given, applies `LIMIT`/`OFFSET`.
- `update` sets `name`, `description` and `updated_at = now()` and returns the new
  row, or `None` for an unknown id. The ORM version uses
  `populate_existing=True`, like `users`.
- `delete` returns whether a row was deleted.
- `add_member` raises `ConflictError` when the user is already a participant;
  failures leave the Unit of Work usable (savepoint pattern from `users`). It does
  not check that the user is not the owner; that is the invite service's rule in
  epic 5.

### Service and access rules

`projects/service.py` takes the `UnitOfWork` and the current `User`:

| Function | Rule |
|---|---|
| `create_project` | owner = caller; commit; log `project created` |
| `list_projects` | `list_for_user(caller, …)` |
| `get_project` | `get_for_user`; `None` → `NotFoundError("Project not found")` |
| `update_project` | `get_project` first (404 for outsiders), then `update`, commit; `None` from `update` (deleted meanwhile) → 404 |
| `delete_project` | `get_project` first (404 for outsiders); role `participant` → `PermissionDeniedError("Only the project owner can delete the project")`; `delete`, commit; log `project deleted` |

**Seam for epic 6:** `delete_project` is the only way a project is deleted. Epic 6
adds the documents step there: document rows go with the project (a foreign key
with `ON DELETE CASCADE` from the documents table), and S3 objects are removed in
that function. This epic adds no placeholder code for it.

**Security log:** module logger `project_hub.projects.service`, INFO, one record
per event with `event`, `login`, `user_id` and `project_id` (as in
`auth.service`: message text and `extra`). The project name is not logged (user
content, not needed for an audit).

### API

All routes need `Authorization: Bearer <token>` (`CurrentUser`); without a valid
token they answer 401 as in epic 3. `project_id` is a UUID path parameter: a value
that is not a UUID gives 422.

| Route | Success | Errors |
|---|---|---|
| `POST /projects` | 201, project | 422 invalid body |
| `GET /projects?limit&offset&role` | 200, list of projects with `documents` | 422 invalid query |
| `GET /project/{id}/info` | 200, project | 404 |
| `PUT /project/{id}/info` | 200, updated project | 404, 422 |
| `DELETE /project/{id}` | 204, no body | 404 outsider, 403 participant |

**Project in a response** (`ProjectResponse`):

```json
{
  "id": "…",
  "name": "Diploma",
  "description": "Final project",
  "owner": {"id": "…", "login": "mila"},
  "my_role": "owner",
  "created_at": "2026-11-14T10:00:00Z",
  "updated_at": "2026-11-14T10:00:00Z"
}
```

`GET /projects` returns `list[ProjectListItem]`: the same fields plus
`"documents": []`. Epic 6 fills the list; its item shape is decided there.

**Request body** (`ProjectIn`, used by `POST /projects` and `PUT …/info`):

- `name`: string, leading and trailing whitespace stripped, then 1–100 characters
  (a blank name gives 422). It must not contain control characters (Unicode
  category `Cc`: U+0000–U+001F and U+007F–U+009F, so no newline, tab or NUL
  anywhere in it): it is a one-line title (user, 2026-11-14).
- `description`: string, 0–2000 characters, not stripped, default `""`. Newlines
  and tabs are allowed; only NUL (U+0000) is rejected, because Postgres `text`
  cannot store it and psycopg would raise `DataError`, which ends as a 500
  (user, 2026-11-14). Stripping does not help here: it only touches the edges, and
  Python does not count NUL as whitespace.
- `PUT` replaces both fields: an omitted `description` becomes `""`.
- Unknown fields are ignored (pydantic default, as in epic 3).
- Duplicate names are allowed, also for one owner.

**Query parameters of `GET /projects`:** `limit` 1–100, default 50; `offset`
0–100000, default 0 (the upper bound keeps the value inside Postgres `bigint`);
`role` `owner` or `participant`, default both. Anything else gives 422.

### Docs

README: a "Projects" section (routes, roles, the 404/403 rule, paging and filter,
log events), the `0003` row in the migrations table, and the future-improvements
list below.

## Acceptance criteria

API tests go through `TestClient` against `create_app` on the real test Postgres
and run once per backend (`orm`, `sql`). "Outsider" is a registered, logged-in
user who is neither owner nor participant. A participant is added through
`add_member` (directly in the test database), since invites come in epic 5.

Create — `POST /projects`

1. Given a logged-in user and a valid body, when posted, then 201 with the
   project: `owner` is the caller (`id`, `login`), `my_role` is `owner`,
   `created_at == updated_at`.
2. Given a body without `description`, then 201 and `description == ""`.
3. Given `name` with surrounding spaces, then it is stored and returned stripped.
4. Given `name` empty or only spaces, or longer than 100 characters, or
   containing a control character anywhere (NUL, newline, tab, U+007F), or
   `description` longer than 2000 or containing NUL, or `name` missing, then 422
   (never 500) and no project is created.
4a. Given a `description` with newlines and tabs, then 201 and it is returned
   unchanged.
5. Given two projects with the same name for one owner, then both are created.
6. Creating a project logs one INFO record `project created` with the login, user
   id and project id, and without the project name.

Read — `GET /project/{id}/info`

7. Given the owner, then 200 with the same project as returned by create.
8. Given a participant, then 200 with `my_role == "participant"` and `owner` being
   the real owner.
9. Given an outsider, then 404 `{"detail": "Project not found"}`, identical to the
   answer for a random UUID that does not exist.
10. Given a path id that is not a UUID, then 422.

List — `GET /projects`

11. Given a user with no projects, then 200 and `[]`.
12. Given a user who owns two projects and participates in one, and another user's
    project they have no access to, then the list holds exactly those three, each
    with the right `my_role` and `documents == []`.
13. The list is ordered by `updated_at` newest first; updating an older project
    moves it to the top.
14. `role=owner` returns only owned projects, `role=participant` only shared ones.
15. `limit` and `offset` page through the list without overlap or gaps, also when
    several projects have the same `updated_at`.
16. `limit` 0 or 101, a negative `offset`, `offset` above 100000, or an unknown
    `role` give 422.

Update — `PUT /project/{id}/info`

17. Given the owner and a valid body, then 200 with the new name and description,
    and `updated_at` later than before; a following `GET …/info` shows the change.
18. Given a participant, then the same as 17.
19. Given an outsider or an unknown id, then 404 and nothing changes.
20. Given an invalid body (rules of 4), then 422 and nothing changes.
21. Given a body without `description`, then `description` becomes `""`.

Delete — `DELETE /project/{id}`

22. Given the owner, then 204 with an empty body; afterwards `GET …/info` is 404
    for the owner and for the former participant, and the project is gone from
    both users' lists.
23. Given a participant, then 403
    `{"detail": "Only the project owner can delete the project"}` and the project
    still exists.
24. Given an outsider or an unknown id, then 404.
25. Deleting a project logs one INFO record `project deleted` with login, user id
    and project id.

Auth

26. Every route without a token, or with an invalid one, answers 401 with
    `WWW-Authenticate: Bearer`.

Repository contract (both backends, through the `database` fixture)

27. `add` returns a `Project` with generated `id`, timezone-aware `created_at`
    and `updated_at`; `get_for_user` for the owner returns it with role `owner`
    and the owner's login.
28. `get_for_user` returns `None` for an unknown project and for a user with no
    access; `add_member` then makes it return role `participant`.
29. `add_member` twice for the same pair raises `ConflictError` and the Unit of
    Work stays usable; an unknown project or user id raises and leaves it usable
    too.
30. `list_for_user` returns owned and shared projects in `updated_at DESC, id
    DESC` order, honors `role`, `limit` and `offset`.
31. `update` changes name, description and `updated_at`, returns `None` for an
    unknown id, and a read in the same Unit of Work afterwards sees the new values.
32. `delete` returns `True` and removes the project and its `project_members`
    rows; `False` for an unknown id.
33. Nothing is stored without `commit()`.

Migration

34. `upgrade` creates both tables with the columns, constraints and both indexes
    above; `downgrade` to `0002` removes them and keeps `users`; upgrade → downgrade
    → upgrade works; the head is `0003`.
35. The database rejects a project name of 101 characters and an empty name
    (`CHECK`), and deleting a user who owns a project fails (`RESTRICT`).
36. The ORM models match the migrated schema (`compare_metadata` is empty).

Checks

37. `ruff check`, `ruff format --check`, `pyright` (strict) and the full `pytest`
    (both backends and the `docker`-marked tests) are green locally and in CI.

## Future improvements

Recorded so they are not proposed again by accident.

| Improvement | Why not now |
|---|---|
| Participant list in project info (`GET /project/<id>/info` shows who has access, owner first) | Before invites (epic 5) the list could hold only the owner; build it with invites |
| Owner removes a participant; participant leaves a project | Needs invites (epic 5) to be meaningful |
| `DELETE /users/me` | Deleting a user must delete their projects and, after epic 6, their S3 files; build it after epic 6 (`owner_id … RESTRICT` prevents an accidental half-delete until then). Planned behavior while the user still owns projects (user, 2026-11-14): a clear `409` such as `{"detail": "Delete your projects first"}`, never a bare 500, and the frontend shows a dialog that explains why and links to "My projects" (`GET /projects?role=owner`). The frontend session was told about this |
| Search by name `GET /projects?q=` | Few projects per user; needs escaping of `%` and `_` in `ILIKE`; add when lists grow |
| A total count for paging (`X-Total-Count` header or an envelope) | The spec's response is a plain list; the frontend can ask for `limit + 1` items to know if there is a next page |
| Index on `updated_at` for sorting | Only pays off with thousands of projects per user |
| Transfer of ownership | Not in the spec; needs rules for the old owner |

## Calls made while writing this design

Settled without changing what gets built; listed so the user can check them.

- A delete that finds no row after the access check passed (a concurrent delete)
  answers 404 and writes no log record, like `update`.
- `now()` is the start time of the transaction, so a test that expects
  `updated_at` to change updates in a separate Unit of Work from the create.
- The existing test `test_upgrade_twice_is_noop` (`tests/db/test_migrations.py`)
  expects head `0002`; it is updated to `0003`, as epic 3 did for `0002`. This is
  the only existing test that changes. `test_orm_metadata_matches_migrated_schema`
  gets the new models imported so `compare_metadata` sees them.
- The repository contract test file ends in `_contract.py`, so the CI step
  `tests/support/backend_coverage.py` counts it.
- If the owner were ever also a `project_members` row (nothing in this epic can
  do that), the list still returns the project once, with role `owner`.

## Left to the builder

- Exact names of schema classes, service functions and test helpers.
- How the participant is put into the test database for API tests (a helper in
  `tests/support/` that calls `add_member` or inserts the row with psycopg).
- The SQL of `list_for_user` (`OR EXISTS` or `UNION ALL`), as long as the contract
  tests pass on both backends.
- How `add_member` maps the foreign-key violation for an unknown id (any
  exception is fine as long as the Unit of Work stays usable).
