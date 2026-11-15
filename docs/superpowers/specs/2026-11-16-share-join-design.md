# Epic 10: Email share and join

Date: 2026-11-16
Status: draft for approval (builder check done)
Roadmap: [`docs/PRDs/roadmap.md`](../../PRDs/roadmap.md), epic 10 and the "Deferred to
implementation" questions "Email share details" and "How a browser user authenticates on
`GET /join`"
Spec: [`docs/initial-spec.md`](../../initial-spec.md), optional API (mandatory for us):
`GET /project/<project_id>/share?with=<email>` sends a `GET /join` link with a correct hashed
token for the requested project to the given email, and a different user can open that link in a
browser.

## Intent

A project owner can bring someone into a project without knowing their login: type an email
address, and Project Hub mails a link. Whoever opens the link and signs in becomes a participant.
Epic 5 gave the owner the invite by login. This epic adds the email path from the spec and closes
the last deferred questions in the roadmap.

The project is defended in front of a mentor, so the demo must work live:

1. Mila shares her project with `anna@example.com`.
2. The mail shows up in the Mailpit inbox.
3. Anna opens the link in a browser and signs in.
4. Anna sees the project.
5. The same link fails the second time.

## Goals

- `GET /project/{project_id}/share?with=<email>` and `GET /join?token=<token>`, with the spec's
  names and parameters.
- A single-use link that lasts 7 days. The database stores only its SHA-256 hash.
- Sending mail goes through a small `Mailer` interface with one SMTP implementation. Locally, in
  tests and in CI, a Mailpit container catches the mail. Tests read the real message from Mailpit.
- A browser that opens the link without a JWT is sent to the web app's join page (`303`). Without
  a configured web app, the browser gets a plain `401`.
- Security log events `project shared` and `project joined`.
- Both database backends (`orm`, `sql`) behind one repository `Protocol`, with shared contract
  tests.

## Non-goals

- Real delivery through AWS (SES), SMTP TLS and SMTP login. They belong to epics 8a and 8b and are
  recorded in the roadmap (see [For the AWS epics](#for-the-aws-epics-8a-8b)).
- The frontend join page and share form. That is F5, which only uses this API.
- Anything in [Future improvements](#future-improvements).

## Anti-goals (a failure even if it "works")

- The plain token is stored anywhere on the server: database, security log, or access log.
- A participant or an outsider can send share mail for a project. An outsider learns from any
  answer that a project exists.
- A link works twice, works after 7 days, or works after a newer link to the same address replaced
  it.
- Someone can tell apart "unknown link", "expired link" and "used link".
- A mail scanner or a browser prefetch that opens the link changes anything. Only a request with a
  valid JWT can join.
- A failed mail send leaves a stored link nobody received, or answers 500.
- A corporate email address, or the course provider's company name, appears anywhere: sender,
  recipients, examples, tests, docs.

## Constraints

- Endpoint names and parameters exactly as in the spec (roadmap ground rule).
- Users have no email address. Registration (`POST /auth`) takes only login, password and repeat
  password. So a link cannot be bound to its recipient: it works like a key, and whoever uses it
  first while signed in joins. Mila chose this (2026-11-16) over adding verified emails to users,
  which would change the spec's registration and be an epic of its own.
- Swappable data layer: a `ShareRepository` `Protocol` with an ORM and a psycopg implementation,
  shared contract tests on both, exposed on the Unit of Work as `uow.shares`.
- The schema comes from a hand-written Alembic migration, `0005` (head is `0004`).
- Epic 9 (package build) runs in parallel and may touch `pyproject.toml`, `poetry.lock` and
  `.github/workflows/ci.yml`. This epic changes them minimally:
  - one dependency, `email-validator`, which `pydantic`'s `EmailStr` needs;
  - one Mailpit service and two env lines in the `checks` job.

  Whoever merges second rebases and resolves the conflicts.
- "What to test" in `CLAUDE.md`: endpoints through `TestClient` on real Postgres, both backends, and
  real mail through Mailpit. No tests that only re-read compose or workflow files.
- Error mapping already exists: `NotFoundError` → 404, `PermissionDeniedError` → 403,
  `AuthenticationError` → 401 with `WWW-Authenticate: Bearer`, `ServiceUnavailableError` → 503.
  This epic adds `TooManyRequestsError` → 429.

## Decisions with Mila (2026-11-16)

| Question | Decision |
|---|---|
| What the link means without user emails | A key: single use, 7 days, the first signed-in user who opens it joins |
| How a browser authenticates on `GET /join` | The mail holds the spec's API link. With a JWT, `GET /join` joins and answers JSON. Without a JWT, a browser asking for HTML gets `303` to the web app's `/join?token=…` page. With no web app configured, the answer is `401` JSON, and in the demo the token goes into Swagger |
| Who may share | Owner only, like invite. Participant → 403, outsider → 404 |
| Repeat share to the same address | The new link replaces the old one, and the old one stops working |
| What a joined user becomes | Participant |
| Already has access when opening a link | `200`, and the link is **not** used up. It stays for the real recipient |
| Mail cannot be sent | `503`, and the link is not stored |
| Mail library | Python's own `smtplib`, run in a worker thread (`asyncio.to_thread`) |

## Approaches considered

### Browser authentication on `GET /join`

| | **A. Spec link + `303` to the web app** | B. Mail links straight to the web app |
|---|---|---|
| Link in the mail | `<API>/join?token=…`, as in the spec | `<web>/join?token=…` |
| Without the frontend | `401` JSON; the token can be used in Swagger | the link does not open at all |
| Cost | one setting and one branch in the route | slightly less backend |

**Chosen: A** (Mila). It keeps the spec's link, and the backend works and can be shown on its
own.

### Sending mail

| | **1. `smtplib` in a thread** | 2. `aiosmtplib` | 3. Background task after the response |
|---|---|---|---|
| New dependency | none | yes (`poetry.lock` conflict with epic 9) | none |
| Knows if the send failed | yes | yes | no, so the promised `503` is impossible |

**Chosen: 1** (Mila). The thread keeps the event loop free while the mail goes out.

### Token hash

The token is 32 random bytes from `secrets.token_urlsafe(32)` (43 URL-safe characters). Guessing
it is hopeless, so a slow password hash such as argon2 adds nothing. SHA-256 is deterministic, so
the server finds the link by the hash of what it received (an indexed equality lookup). The hash
is stored as 64 lowercase hex characters.

## Beyond the spec

Proposed to Mila with what, why and cost. Decisions of 2026-11-16.

| # | Addition | Decision |
|---|---|---|
| 1 | At most 10 pending (unused, unexpired) links per project, otherwise `429`, so nobody can use the server to send spam | **accepted** |
| 2 | List the pending links of a project and revoke one (two endpoints) | **postponed**: "a repeat share replaces the old link" covers the main case (wrong or lost mail) at a third of the cost |
| 3 | Bind the link to the recipient through verified user emails | **rejected**: changes the spec's `POST /auth` and needs email verification, an epic of its own |
| — | `Cache-Control: no-store` on every `GET /join` response, and the joiner's login in the join response, for shared computers | part of the design (raised by Mila's question about two people on one laptop) |

## Design

### API

Both routes need `Authorization: Bearer <JWT>`, except for the `303` case of `GET /join`.

#### `GET /project/{project_id}/share?with=<email>`

No body. Checks in this order. The first one that fails decides the answer. As on every existing
route, FastAPI resolves dependencies (`CurrentUser`, then the mail settings) before it validates
query and path parameters. So a request without a valid JWT gets 401, and a signed-in caller gets
503 when mail is not configured, whatever the parameters are. The 422 row is for a signed-in
caller with mail configured.

| # | Check | Answer |
|---|---|---|
| 1 | no valid JWT | 401 |
| 2 | mail is not configured (`APP_SMTP_HOST` or `APP_PUBLIC_URL` unset) | 503 `Email sharing is not configured` |
| 3 | `project_id` not a UUID; `with` missing or not a valid address (`EmailStr`, at most 254 characters) | 422 |
| 4 | caller has no access, or the project does not exist | 404 `Project not found` |
| 5 | caller is a participant | 403 `Only the project owner can share the project` |
| 6 | the project already has 10 pending links to other addresses | 429 `Too many pending share links for this project` |
| 7 | the mail cannot be handed to the SMTP server | 503 `Email could not be sent`; nothing stored |
| — | otherwise | **200** `{"email": "<address>", "expires_at": "<UTC time>"}` |

- The address is stored and compared in lower case. So `Anna@Example.com` and `anna@example.com`
  are the same recipient, and the second share replaces the first.
- Pending links to the same address don't count toward the limit, because they get replaced.
  Expired links never count. After storing the new link, the share deletes this project's expired
  links (housekeeping). Deleting them before the insert could deadlock with a project delete: the
  delete would lock link rows, then the insert's foreign key check would wait on the project row.
- The token never appears in the response.
- Steps: store the link (upsert), send the mail, then commit. If sending fails, the transaction is
  rolled back. If the commit fails after a successful send, the mail holds a dead link. That is
  rare, and the next share fixes it.
- The project's `updated_at` does not change.

#### `GET /join?token=<token>`

Every response from this route carries `Cache-Control: no-store`, errors included.

| # | Check | Answer |
|---|---|---|
| 1 | `token` missing, empty or longer than 128 characters | 422 |
| 2 | no `Authorization` header at all, `APP_WEB_URL` set, and `Accept` contains `text/html` | **303**, `Location: <APP_WEB_URL>/join?token=<token, URL-encoded>` |
| 3 | no `Authorization` header (otherwise), or an invalid or expired JWT | 401 |
| 4 | no pending link with this token's hash (unknown, expired, used, replaced, or its project deleted) | 404 `Invite link is invalid or expired` |
| 5 | the caller already has access (owner or participant) | **200**, `already_member: true`; the link stays pending |
| 6 | the caller is added as a participant, and the link is claimed: deleted in the same transaction | **200**, `already_member: false` |

Success body:

```json
{
  "login": "anna",
  "already_member": false,
  "project": { "...": "the same object as GET /project/<id>/info, with my_role" }
}
```

- `login` is the caller's login, so a shared computer shows who joined (F5 shows "You joined as
  @anna").
- The route reads credentials through an optional dependency that never raises, so check 1 (422)
  comes first. Check 2 looks at whether the raw `Authorization` header is present, not at what
  `HTTPBearer` parsed. So any header that is present but not a valid Bearer JWT (a broken token,
  `Basic …`) gets `401`, never `303`. A clicked link carries no
  header, so the `303` only ever happens for a browser click.
- The `303` target is a fixed origin from the settings, so it is not an open redirect.
- **Single use under concurrency.** The link is claimed by `DELETE … WHERE id = …` and the result
  tells whether this request deleted it. Two people using the same link at once: Postgres lets only
  one delete succeed. The other gets `404` and its transaction is rolled back.
- The participant is added before the link is claimed. The other order deadlocks with a project
  delete: the claim locks the link row, the delete locks the project row and cascades to the link,
  and the insert's foreign key check waits on the project row. If the claim then fails, the unit
  of work exits without commit, so the added participant is rolled back.
- If the owner invites the same user between the access check and `add_member`, `add_member`
  raises `ConflictError`. Its savepoint undoes the failed insert and nothing has been claimed, so
  the link stays pending, and the join answers 200 with `already_member: true`, the same as
  check 5.
- If the project is deleted between the lookup and the insert, `add_member` raises `NotFoundError`
  (epic 5), and the join answers the same `404 Invite link is invalid or expired` as check 4,
  never 500. Deleting a project cascades to its links.
- The project's `updated_at` does not change. As with invite, membership is not an edit of the
  project.

### Mail

`project_hub/mail/`:

```python
@dataclass(frozen=True)
class OutgoingMail:
    to: str
    subject: str
    text: str

class Mailer(Protocol):
    async def send(self, mail: OutgoingMail) -> None: ...  # raises MailDeliveryError

class SmtpMailer:  # smtplib.SMTP(host, port, timeout=10) inside asyncio.to_thread
```

- `SmtpMailer` builds an `email.message.EmailMessage` with `From` set to `APP_MAIL_FROM`.
  `smtplib.SMTPException` and `OSError` become `MailDeliveryError`. The service turns that into
  `ServiceUnavailableError("Email could not be sent")` and logs a WARNING without the token.
- Plain text only, no HTML.
- The subject is fixed: `You are invited to a project on Project Hub`. Header values never carry
  user input, so CR/LF header injection is impossible by construction.
- The body names the sharer (`@login`) and the project name, gives the link
  `<APP_PUBLIC_URL>/join?token=<token>`, and says that the link works once and expires at
  `<expires_at>` UTC.
- The `Mailer` lives on `app.state.mailer` (`None` when `APP_SMTP_HOST` is unset), like
  `app.state.storage`. A dependency returns it or raises `ServiceUnavailableError` (check 3).

### Settings

| Setting | Default | Meaning |
|---|---|---|
| `APP_SMTP_HOST` | unset | SMTP server. Unset disables sharing (503) |
| `APP_SMTP_PORT` | `25` | SMTP port (1–65535) |
| `APP_MAIL_FROM` | `noreply@project-hub.test` | Sender address (`.test` is a reserved domain that belongs to nobody). A plain string with a simple `x@y` check, not `EmailStr`: `email-validator` rejects special-use domains such as `.test` |
| `APP_PUBLIC_URL` | unset | Public base URL of the API, used in the mail link (`http`/`https`, no query, trailing `/` dropped). Unset disables sharing (503) |
| `APP_WEB_URL` | unset | Base URL of the web app for the `303`. Unset means a browser click gets `401` |

Blank values count as unset, like the existing settings. The share lifetime (7 days) and the limit
(10) are constants in the service, not settings.

### Database: migration `0005`, table `project_shares`

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid` PK, `gen_random_uuid()` | |
| `project_id` | `uuid` not null | FK `projects.id` `ON DELETE CASCADE` |
| `email` | `text` not null | lower case, check `char_length BETWEEN 3 AND 254` |
| `token_hash` | `text` not null | unique; check `~ '^[0-9a-f]{64}$'` |
| `expires_at` | `timestamptz` not null | |
| `created_at` | `timestamptz` not null, `now()` | |

Plus a unique constraint on `(project_id, email)`. It makes "a new link replaces the old one" a
single upsert (`INSERT … ON CONFLICT (project_id, email) DO UPDATE`), and its leading column
serves lookups by project.

### Repository

`project_hub/shares/` holds `entities.py`, `repository.py` (the Protocol), `repository_orm.py` and
`repository_sql.py`. Time is passed in by the caller, so tests control it.

```python
@dataclass(frozen=True)
class ShareLink:
    id: UUID
    project_id: UUID
    email: str
    expires_at: datetime

class ShareRepository(Protocol):
    async def delete_expired(self, project_id: UUID, now: datetime) -> None: ...
    async def count_pending(self, project_id: UUID, now: datetime, *, except_email: str) -> int: ...
    async def put(self, project_id: UUID, email: str, token_hash: str, expires_at: datetime) -> None: ...
    async def find_pending(self, token_hash: str, now: datetime) -> ShareLink | None: ...
    async def claim(self, share_id: UUID) -> bool: ...
```

- `put` upserts on `(project_id, email)` and replaces `token_hash`, `expires_at` and `created_at`.
  A foreign-key failure (project deleted in the meantime) raises `NotFoundError("Project not
  found")`. The Unit of Work stays usable (the savepoint pattern of epics 4 and 5).
- `find_pending` returns the link only when `expires_at > now`.
- `claim` deletes the row and reports whether it existed.

### Service

`project_hub/shares/service.py`, with a clock passed in like `TokenService`'s:

- `share(uow, mailer, settings, user, project_id, email) -> ShareLink` runs the share table above
  and logs `project shared`.
- `join(uow, user, token) -> JoinResult` runs the join table above and logs `project joined` when
  the user was added. Nothing is logged for `already_member`.

### Security log

Same style as epics 4 and 5, logger `project_hub.shares.service`, INFO, only after the commit:

- `project shared`: `login`, `user_id` (the owner), `project_id`, `email` (the recipient).
- `project joined`: `login`, `user_id` (the new participant), `project_id`, `email` (the address
  the link was sent to).

Refused attempts (401, 403, 404, 422, 429, 503) are not logged, as in epics 4 and 5. The token
and its hash are never logged.

### Access log: hide the token

uvicorn's access log prints the request line, `GET /join?token=… HTTP/1.1`. A browser's first
click (the `303`) would write a still-valid token to stderr, and in the cloud to CloudWatch. That
breaks "store only the hash". `configure_logging` therefore adds a filter to the `uvicorn.access`
logger: it replaces the value of a `token` query parameter with `***` and leaves the rest of the
line as it was. uvicorn puts the path into the record's `args`, not into `msg`, so the filter
rewrites the path argument. uvicorn configures its loggers before it imports the app, so a filter
added by `configure_logging` stays in place.

### Compose, CI, docs

- `docker-compose.yml` gets a `mail` service: Mailpit (`axllent/mailpit`, pinned to an exact
  release at least two weeks old) with a healthcheck.
  - Ports, bound to `127.0.0.1` only: SMTP `${APP_MAIL_PORT:-55436}` → 1025, web inbox
    `${APP_MAIL_UI_PORT:-8025}` → 8025.
  - The `api` gets `APP_SMTP_HOST=mail`, `APP_SMTP_PORT=1025`,
    `APP_PUBLIC_URL=${APP_PUBLIC_URL:-http://localhost:${APP_PORT:-8000}}`, `APP_WEB_URL=${APP_WEB_URL:-}`, and
    depends on `mail` being healthy.
- CI `checks` job: one `mailpit` service (ports 1025 and 8025) and `TEST_SMTP_PORT=1025`,
  `TEST_MAILPIT_URL=http://localhost:8025`. The tests default to `localhost:55436` and
  `http://localhost:8025`, matching compose.
- The test fixture fails with a clear "start it with `docker compose up -d --wait mail`" message
  when Mailpit is unreachable, as the S3 fixture does. Each test uses its own random recipient
  (`<uuid>@example.com`) and finds its mail through Mailpit's search API, so tests never see each
  other's mail.
- `.env.example`: the new settings and ports, with comments.
- README: a "Share by email" section (both routes, order of checks, the inbox at
  `http://localhost:8025`, demo steps with Swagger). The log events go in the security log list.
  `project_shares` goes in the migration list.
- Roadmap: row 10 decisions, the two deferred questions marked decided, the F5 frontend request
  marked accepted with the final shape, and [For the AWS epics](#for-the-aws-epics-8a-8b).

### Existing tests that change

Mila agrees to these edits when she approves this design:

- `tests/test_docker_smoke.py`: the compose tests pass `APP_MAIL_PORT=0` and `APP_MAIL_UI_PORT=0`,
  like the other ports, so parallel stacks don't clash. `test_compose_stack_serves_health` expects
  the running services `{db, s3, mail, api}`.
- `tests/conftest.py` `_clean_env` also clears the new `APP_*` variables.
- The parametrized 401 test for project routes gains the share route.

### For the AWS epics (8a, 8b)

These go into the roadmap. Nothing is built for them here.

- SES SMTP needs STARTTLS on port 587 and SMTP credentials. Add settings
  `APP_SMTP_STARTTLS`, `APP_SMTP_USERNAME`, `APP_SMTP_PASSWORD` (`SecretStr`, from SSM) and use
  them in `SmtpMailer`.
- A verified SES identity for `APP_MAIL_FROM`: the personal address or an own domain, never a
  corporate one.
- An SES account in the sandbox can only send to verified addresses. Every demo recipient must be
  verified, or production access requested.
- The app security group needs egress to SES SMTP (587).
- SSM: the SMTP password; `APP_PUBLIC_URL` = the ALB's HTTPS URL; `APP_WEB_URL` once the frontend
  is hosted.
- When nginx (frontend) is hosted, its access log must hide `token` too (a note for F5).
- The share keeps its database transaction open while the SMTP send runs (timeout 10 s), so a slow
  SES SMTP holds a pooled connection that long. Keep the timeout short and watch the send latency.

## Acceptance criteria

API tests go through `TestClient` against `create_app` on the real test Postgres and the real
Mailpit, once per backend (`orm`, `sql`). Mila owns the project, Anna and Zoe are registered
users. "Outsider" means a signed-in user without access. "The mail" means the message Mailpit
received for that test's random address.

Share: `GET /project/<id>/share?with=<email>`

1. When Mila shares her project with an address, she gets 200 with
   `{email (lower case), expires_at ≈ now + 7 days}`, and no token in the body.
   - Exactly one mail arrives at that address: sender `APP_MAIL_FROM`, the fixed subject, Mila's
     login and the project name in the body.
   - The body has a link `<APP_PUBLIC_URL>/join?token=<43 characters>`.
2. After a share, the database row for it holds the SHA-256 hex of the mailed token and never the
   token itself. No record in the captured logs contains the token.
3. When Anna (a participant) shares, she gets 403 `Only the project owner can share the project`,
   and no mail is sent.
4. When an outsider shares Mila's project, or anyone shares an unknown project id, the answer is
   404 `Project not found` with identical bodies, and no mail is sent.
5. A share with `with` missing, empty, not an address, or longer than 254 characters, or with a
   project id that is not a UUID, gets 422 (never 500), and no mail is sent.
6. A share without a token, or with a broken one, gets 401 (whatever the parameters) with `WWW-Authenticate: Bearer` (in the
   parametrized auth test).
7. With `APP_SMTP_HOST` or `APP_PUBLIC_URL` unset, an owner's share gets 503
   `Email sharing is not configured`.
8. When the SMTP server refuses the connection, the share gets 503 `Email could not be sent`, and
   no link is stored (the next share to another address is not blocked by the limit, and nothing
   to that address can be joined).
9. Given 10 pending links to different addresses, an 11th address gets 429
   `Too many pending share links for this project`, and no mail is sent. Sharing again with one of
   the 10 addresses still works. An expired link does not count.
10. Sharing twice with `anna@example.com` (the second time as `Anna@Example.com`) sends two mails.
    The first mail's link answers 404 and the second one's joins.
11. A successful share writes one INFO record `project shared` with Mila's login and id, the
    project id and the address. The refused shares of criteria 3–9 write none.
12. A share does not change the project's `updated_at`.

Join: `GET /join?token=<token>`

13. When Anna opens the mailed link with her JWT, she gets 200 with `login: "anna"`,
    `already_member: false` and the project with `my_role: "participant"`. Afterwards she has
    access (`GET …/info` 200), and the members list shows her.
14. When Zoe opens the same link afterwards, she gets 404 `Invite link is invalid or expired`, and
    Zoe has no access.
15. The answer is the same 404 body (identical to criterion 14) for:
    - a token that was never issued;
    - a link past its `expires_at` (stored through the repository with a past time);
    - a link replaced by a newer share;
    - the link of a deleted project.
16. When Mila (the owner), or an existing participant, opens a pending link, they get 200 with
    `already_member: true` and their own role. The link is still pending: Anna can join with it
    afterwards.
17. Without an `Authorization` header, with `Accept: text/html` and `APP_WEB_URL` set, the answer
    is 303 with `Location: <APP_WEB_URL>/join?token=<token>`, and the link is still pending.
18. Without an `Authorization` header and without `APP_WEB_URL` (or without `text/html` in
    `Accept`), the answer is 401 with `WWW-Authenticate: Bearer`. With a broken JWT the answer is
    401 even with `Accept: text/html` and `APP_WEB_URL` set, and so does a `Basic` header.
19. `token` missing, empty or of 129 characters gets 422.
20. Every answer of criteria 13–19 carries `Cache-Control: no-store`.
21. A successful join writes one INFO record `project joined` with Anna's login and id, the project
    id and the link's address. Criteria 14–19 write none, and neither does `already_member`.
22. The join does not change the project's `updated_at`.
23. An access-log record for `GET /join?token=<token>` written through the `uvicorn.access` logger
    shows `token=***` and not the token.

Repository contract (both backends)

24. `put` then `find_pending` with the same hash returns the link, and `find_pending` at a time
    after `expires_at` returns `None`.
25. A second `put` for the same project and address replaces the hash and expiry, and the old hash
    is no longer found. The same address on another project is a separate link.
26. `count_pending` counts only unexpired links of that project and leaves out `except_email`.
    `delete_expired` removes only that project's expired links.
27. `claim` returns `True` once and `False` after that. A claimed link is not found any more. A
    claim without `commit` is lost.
28. `put` for an unknown project raises `NotFoundError`, and the Unit of Work stays usable.
    Deleting the project removes its links.

Migrations and Docker

29. The migration tests apply `0005` and roll it back cleanly.
30. A docker test brings up the compose stack:
    - Mila registers, logs in, creates a project and shares it.
    - The mail is read from the stack's Mailpit through its published inbox port, and the link in
      it points at `APP_PUBLIC_URL`.
    - Anna registers, logs in, opens the link's path with her JWT, and gets 200 with
      `already_member: false`.

Checks

31. `poetry check --lock`, `ruff check`, `ruff format --check`, `pyright` (strict) and the full
    `pytest` (both backends, `backend_coverage` OK) and `pytest -m docker` are green locally. The
    CI `checks` and `docker` jobs pass once the branch is pushed.

## Future improvements

Recorded so they are not proposed again by accident.

| Improvement | Why not now |
|---|---|
| List and revoke pending links (addition 2) | Postponed by Mila; a repeat share already replaces a link |
| Links bound to verified user emails (addition 3) | Changes the spec's registration; an epic of its own |
| Configurable lifetime and limit | Constants are enough for a course project; trivial to move into settings later |
| HTML mail with a button | Plain text is enough and avoids HTML escaping questions |
| A per-owner limit across projects | The per-project limit stops the obvious abuse |
| Mask a percent-encoded `token` key in the access log (parse-based filter) | Only a hand-encoded link produces it; its sender already holds the token |

## Calls made while writing this design

These were settled without changing what gets built. They are listed so Mila can check them.

- `200` for share (the mail is sent before the answer, nothing is "accepted for later"), with
  `email` and `expires_at` so the frontend can show "Link sent to … until …".
- Addresses in lower case for storage and "same address". In practice, mail providers ignore case.
- A token longer than 128 characters is a 422. Any other wrong value is a plain 404, the same as an
  unknown link. NUL needs no special check, because the token is only hashed and never stored.
- The subject is fixed and has no user input (no header injection).
- The `token` filter on the access log (see above). It is needed for "never store the token".
- When `APP_WEB_URL` is unset, a browser click gets 401, not an error page. The demo without the
  frontend uses Swagger.
- `already_member` is not logged, because nothing changed.
- The 10-link limit is checked with a count before the insert. Two shares at the very same moment
  could make it 11. That is harmless for a spam guard.
- Mailpit ports: SMTP 55436 (the next free one after S3's 55435), inbox 8025 (Mailpit's usual
  port, easy to remember for the demo).
- 401 comes before 422 on the share route, as on every existing route: FastAPI checks the JWT
  dependency before the parameters.
- On `GET /join` the `303` depends on the raw `Authorization` header being absent, so `Basic …` or
  a broken Bearer token gets 401.
- An invite that races a join (`ConflictError`) answers `already_member: true` and leaves the link
  pending.
- `APP_MAIL_FROM` is a plain string, not `EmailStr`, because `email-validator` rejects `.test`.
- The compose default for `APP_PUBLIC_URL` follows `APP_PORT`.
