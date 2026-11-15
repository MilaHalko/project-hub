# Epic 5: Invites

Date: 2026-11-15
Status: approved design (2026-11-15)
Roadmap: [`docs/PRDs/roadmap.md`](../../PRDs/roadmap.md), epic 5
Spec: [`docs/initial-spec.md`](../../initial-spec.md) — `POST /project/<project_id>/invite?user=<login>`
("Grant access to the project for a specific user. If the request is not coming from the owner of
the project, results in error. Granting access gives participant permissions to receiving user");
implementation note 2 (owner and participant)

## Intent

Let a project owner give another registered user participant access by typing that user's login,
and take it back again: the owner removes a participant, or a participant leaves the project.
Epic 4 built the access model and the `project_members` table; until now a participant could only
be added straight in the database. This epic adds the way it happens through the API.

The project is defended in front of a mentor, so the rules must be short enough to say in one
breath and to show live in Swagger: Mila invites Anna, Anna sees the project; Anna tries to invite
Zoe and gets 403; Mila removes Anna, and Anna gets 404.

## Goals

- `POST /project/<id>/invite?user=<login>`, exactly as in the spec: owner only; the invited user
  becomes a participant at once (no accept step: the spec says "grant access").
- Additions accepted by the user (see [Beyond the spec](#beyond-the-spec)): the owner removes a
  participant, a participant leaves, and these three actions are written to the security log.

## Non-goals

- Email share links (`GET /project/<id>/share`, `GET /join`) — epic 10.
- Anything in [Future improvements](#future-improvements).

## Anti-goals (it would be a failure even if it "works")

- A participant or an outsider can add or remove anyone else.
- An outsider learns from any answer that a project exists, or which logins exist, through this
  endpoint (the project is checked before the login).
- A project ends up with no owner, or the owner also shows up as a participant.
- A race (the project deleted between the access check and the insert) answers 500.
- The endpoint path or its `user` parameter differs from the spec.

## Constraints

- Endpoint name and parameter exactly as in the spec (roadmap ground rule). The user considered
  inviting by user id (the mentor allows small API changes) and decided to keep the spec's login
  (2026-11-15): an owner knows the other person's login, not their UUID, and there is no user
  search to find one.
- Swappable data layer: every repository change goes into the `ProjectRepository` Protocol and both
  implementations, with shared contract tests on both backends.
- No migration: `project_members` from `0003` already holds everything needed. This also keeps the
  migration numbers clear of epic 6, which adds `0004` on its own branch.
- "What to test" in `CLAUDE.md`: endpoints through `TestClient` on real Postgres, both backends.
- Error mapping already exists: `NotFoundError` → 404, `PermissionDeniedError` → 403,
  `ConflictError` → 409, all `{"detail": str}`; request validation → 422.

## Approaches considered

### Invite

Only one sensible way: a service function that checks access like `delete_project` does, looks the
login up with `uow.users.get_by_login`, and calls the existing `uow.projects.add_member`.

### Removing and leaving

| | **A. One route `DELETE /project/<id>/members/<user_id>`** | B. That route for the owner + `POST /project/<id>/leave` | C. A plus the alias `…/members/me` |
|---|---|---|---|
| Routes | 1 | 2 | 1 (with a special path word) |
| Rule | owner removes others, participant removes only self | each route does one thing | as A |
| Cost | lowest | double the code, tests and docs for the same row delete | an extra case among UUIDs, little gain: the frontend knows its id from `GET /users/me` |

**Chosen: A** (user, 2026-11-15). The smallest API surface, and the rule fits in one sentence. The
log still tells removing from leaving apart (two event names).

## Beyond the spec

Proposed to the user with what, why and cost; decisions of 2026-11-15.

| # | Addition | Decision |
|---|---|---|
| 1 | The owner removes a participant (postponed to this epic by epic 4) | **accepted** |
| 2 | A participant leaves a project (same route as #1) | **accepted** |
| 3 | Security-log records `participant invited`, `participant removed`, `participant left` | **accepted** |
| 4 | Column "invited by" in `project_members` | **rejected**: only the owner can invite, so it would always be the owner; it would also need a migration |
| 5 | Pending invitations with accept / decline | **rejected**: the spec grants access at once; epic 10 brings the join link |
| 6 | User search by login prefix for the invite form | **rejected**: lets anyone list logins; the form takes the exact login |
| — | Invite by user id instead of login | **rejected** by the user (see Constraints) |

## Design

### API

All routes need `Authorization: Bearer <token>` (401 with `WWW-Authenticate: Bearer` otherwise).
Path ids are UUIDs (anything else is 422).

**`POST /project/{project_id}/invite?user=<login>`** — no request body. Checks in this order, and
the first one that fails decides the answer:

| # | Check | Answer |
|---|---|---|
| 1 | `user` missing, empty, longer than 32 characters, or containing NUL (U+0000) | 422 |
| 2 | caller has no access, or the project does not exist | 404 `Project not found` |
| 3 | caller is a participant | 403 `Only the project owner can invite users` |
| 4 | no user with exactly this login (case-sensitive, not stripped, as at `/login`) | 404 `User not found` |
| 5 | the login is the owner's own | 409 `You already own this project` |
| 6 | the user is already a participant | 409 `User is already a participant of this project` |
| — | otherwise | **201** with the new member |

Steps 1 and 2 come before anything about the login, so an outsider learns nothing about projects
or users. A logged-in owner can tell from step 4 whether a login exists; registration already says
`Login 'x' is already taken`, so this reveals nothing new.

Success body: the same shape as one item of `GET /project/<id>/members` (`MemberResponse`):

```json
{"id": "…", "login": "anna", "role": "participant", "joined_at": "2026-11-15T10:00:00Z"}
```

The frontend can add it to the members panel without reloading. `joined_at` is the stored
`project_members.created_at`, so it matches what the members list shows later.

**`DELETE /project/{project_id}/members/{user_id}`** → **204**, no body.

| # | Check | Answer |
|---|---|---|
| 1 | caller has no access, or the project does not exist | 404 `Project not found` |
| 2 | caller is a participant and `user_id` is not their own | 403 `Only the project owner can remove participants` |
| 3 | caller is the owner and `user_id` is their own | 409 `The owner cannot leave the project` |
| 4 | `user_id` is not a participant of this project | 404 `Participant not found` |
| — | otherwise the participant row is deleted | 204 |

A participant who left, or was removed, gets the normal 404 for the project afterwards, and the
project disappears from their `GET /projects`. They can be invited again; they get a new
`joined_at`.

Neither route changes the project's `updated_at`: name and description stay the same, so the
project does not jump to the top of everyone's list.

### Repository

```python
class ProjectRepository(Protocol):
    ...
    async def add_member(self, project_id: UUID, user_id: UUID) -> datetime: ...
    async def remove_member(self, project_id: UUID, user_id: UUID) -> bool: ...
```

- `add_member` now returns the stored `joined_at` (`created_at` of the new row) instead of `None`.
  A duplicate still raises `ConflictError`. A foreign-key failure on the project (deleted in the
  meantime) raises `NotFoundError("Project not found")`, so the race answers 404, not 500; the
  existing contract test only asserts it is not a `ConflictError`, so it stays as it is. The Unit
  of Work stays usable after any failure (the savepoint pattern already there).
- `remove_member` deletes the `(project_id, user_id)` row and returns whether one was deleted. It
  does not check roles; the service does (the owner's own id never reaches it: the service answers
  409 first).

### Service

`projects/service.py`:

| Function | Rule |
|---|---|
| `invite(uow, user, project_id, login) -> ProjectMember` | the invite table above; commit; log `participant invited` |
| `remove_member(uow, user, project_id, member_id) -> None` | the remove table above; commit; log `participant removed` (owner) or `participant left` (participant) |

Both start with `get_project`, the same as every other project function.

### Security log

Same logger as epic 4 (`project_hub.projects.service`, INFO), same fields `event`, `login`,
`user_id`, `project_id` for the caller, plus `member_id`, the user who was added or removed (for
`participant left` it equals `user_id`). Logged only after the commit. Refused attempts (403, 404,
409, 422) are not logged, as for `project deleted`.

### Docs

README "Projects" section: both routes, their order of checks and answers, the three log events.
In README "Future improvements", the line "an owner cannot remove a participant and a participant
cannot leave" goes. No migration row. The roadmap tick for epic 5 comes after the merge.

## Acceptance criteria

API tests go through `TestClient` against `create_app` on the real test Postgres and run once per
backend (`orm`, `sql`). Mila is the owner, Anna and Zoe are registered users; "outsider" is a
logged-in user with no access to the project.

Invite: `POST /project/<id>/invite?user=<login>`

1. Given Mila's project, when Mila invites `anna`, then 201 with
   `{id: anna's id, login: "anna", role: "participant", joined_at}`; afterwards Anna gets 200 on
   `GET …/info` with `my_role: "participant"`, the project is in Anna's
   `GET /projects?role=participant`, and `GET …/members` lists Anna with the same `joined_at`.
2. Given Anna is a participant, when Anna invites `zoe`, then 403
   `Only the project owner can invite users` and Zoe has no access.
3. Given an outsider, when they invite anyone (an existing login or an unknown one) to Mila's
   project, or anyone invites to an unknown project id, then 404 `Project not found` with identical
   bodies, and nothing changes.
4. When Mila invites a login that does not exist, then 404 `User not found`.
5. Given the user `anna`, when Mila invites `Anna` or `" anna"`, then 404 `User not found`.
6. When Mila invites `mila`, then 409 `You already own this project` and the members list still has
   Mila once, as owner.
7. Given Anna is a participant, when Mila invites `anna` again, then 409
   `User is already a participant of this project` and Anna's `joined_at` is unchanged.
8. Given no `user` parameter, an empty one, one of 33 characters or one containing NUL (`%00`), or
   a project id that is not a UUID, then 422 (never 500) and nothing changes.
9. Without a token or with a broken one, then 401 with `WWW-Authenticate: Bearer` (added to the
   existing parametrized auth test).
10. A successful invite writes one INFO record `participant invited` with Mila's login and id, the
    project id and Anna's id as `member_id`; the refused invites of criteria 2–8 write none.
11. The invite does not change the project's `updated_at`.

Remove and leave: `DELETE /project/<id>/members/<user_id>`

12. Given Anna and Zoe are participants, when Mila removes Anna, then 204; Anna gets 404 on
    `GET …/info`, the project is not in Anna's `GET /projects`, the members list is Mila and Zoe,
    and Zoe still has access.
13. Given Anna is a participant, when Anna removes her own id, then 204 with the same effect for
    her.
14. Given Anna and Zoe are participants, when Anna removes Zoe or Mila, then 403
    `Only the project owner can remove participants` and nothing changes.
15. When Mila removes her own id, then 409 `The owner cannot leave the project`.
16. When Mila removes an unknown UUID or the id of a registered user who is not a participant, then
    404 `Participant not found`.
17. Given an outsider or an unknown project id, then 404 `Project not found` with identical bodies.
18. Given a project id or user id that is not a UUID, then 422; without a valid token, then 401
    (added to the parametrized auth test).
19. Given Anna was removed, when Mila invites `anna` again, then 201 with a later `joined_at`.
20. Removing writes one INFO record `participant removed` (caller Mila, `member_id` Anna); leaving
    writes `participant left` (caller and `member_id` Anna); the refused removals of criteria 14–17
    write none.

Repository contract (both backends)

21. `add_member` returns the `joined_at` that `list_members` later shows for that user.
22. `add_member` for an unknown project id raises `NotFoundError` and the Unit of Work stays usable.
23. `remove_member` returns `True` and removes only that user's access to that project (other
    members, and the user's other projects, untouched); it returns `False` for a user who is not a
    participant and for an unknown project; the removal is lost without `commit`.

Checks

24. `ruff check`, `ruff format --check`, `pyright` (strict) and the full `pytest` (both backends,
    `backend_coverage` OK, and the `docker`-marked tests) are green locally and in CI.

## Overlap with epic 6

Epic 6 (documents) lives on the local branch `claude/documents-s3-792aa0`, not yet in `main`. This
epic needs no migration, so the numbers do not clash. Both change `projects/service.py`,
`projects/router.py`, both project repositories, `tests/projects/test_repository_contract.py`,
`tests/projects/test_projects_auth_api.py` and README, but in different functions and sections:
whichever merges second resolves small text conflicts (imports, list entries).

## Future improvements

Recorded so they are not proposed again by accident.

| Improvement | Why not now |
|---|---|
| Notify the invited user (email or an in-app list) | No notifications exist yet; epic 10 sends email for the share link |
| A limit on participants per project | A course-sized project has a handful of members |
| Transfer of ownership | Already postponed in epic 4: needs rules for the old owner |

## Calls made while writing this design

Settled without changing what gets built; listed so the user can check them.

- 201 (not 200 or 204) for an invite, with the member as body: something new was created, and the
  frontend gets what it needs to show it.
- 409 for inviting yourself, with its own message rather than "already a participant": the owner is
  in the project, but not as a participant.
- The `user` parameter has the same limits as the login field at `/login` (1–32 characters, no
  pattern): a login that cannot exist is a plain 404, not a 422. The one exception is NUL: Postgres
  `text` cannot hold it and psycopg would raise `DataError` (a 500), so it is rejected with 422, the
  same reason `ProjectDescription` rejects it.
- `remove_member` deletes exactly the `(project_id, user_id)` row with no role check; guarding the
  owner is the service's job (409).
- Found while checking this design, not fixed here: `POST /login` has no NUL check on `login`, so a
  login with `%00` most likely answers 500 today. It is a separate bug for its own task.
- `member_id` as the log field name for the affected user.
- `add_member` returns only `joined_at`; the service already has the user's id and login.
