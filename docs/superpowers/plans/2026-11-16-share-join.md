# Email share and join — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** An owner shares a project by email (`GET /project/{id}/share?with=<email>`). The
recipient joins as a participant through the mailed single-use link (`GET /join?token=…`). A
browser that opens the link without a JWT is sent to the web app's join page.

**Architecture:** There are two new packages:
- `project_hub/mail/`: a `Mailer` Protocol and `SmtpMailer`, which runs stdlib `smtplib` in a
  worker thread.
- `project_hub/shares/`: tokens, entities, the `ShareRepository` Protocol with ORM and psycopg
  implementations, the service, the router, schemas, and a no-store middleware.

Links live in table `project_shares` (migration `0005`) and store only the SHA-256 hex of the
token. Mailpit catches the mail locally, in tests and in CI.

**Tech Stack:** FastAPI, pydantic v2 (`EmailStr` → `email-validator`), SQLAlchemy 2 async,
psycopg 3, Alembic, stdlib `smtplib`/`email`, Mailpit, pytest, Poetry, ruff, pyright strict.

**Spec:** [`docs/superpowers/specs/2026-11-16-share-join-design.md`](../specs/2026-11-16-share-join-design.md).
Read it first. Its tables of checks, its settings table and its acceptance criteria (AC) are
binding, and this plan points at them instead of copying them.

## Global Constraints

- Endpoint paths and parameters exactly: `GET /project/{project_id}/share?with=<email>` and
  `GET /join?token=<token>`.
- Error texts are verbatim:
  - `Email sharing is not configured`
  - `Project not found`
  - `Only the project owner can share the project`
  - `Too many pending share links for this project`
  - `Email could not be sent`
  - `Invite link is invalid or expired`
- `SHARE_TTL = timedelta(days=7)` and `MAX_PENDING_SHARES = 10` are constants in
  `project_hub/shares/service.py`.
- The token is `secrets.token_urlsafe(32)` (43 characters). Only `hashlib.sha256(token.encode()).hexdigest()` is
  stored. The token never goes into a response body (share), the database, or a log record.
- The mail subject is exactly `You are invited to a project on Project Hub`, plain text only, and
  no user input in any header.
- Default sender `noreply@project-hub.test`. Test recipients are `<uuid4 hex>@example.com`. No
  corporate address or company name anywhere: code, tests, docs, commit messages.
- Both backends: every repository method in `ShareRepository` and both implementations. The
  contract tests use the existing `database` fixture (runs `orm` and `sql`).
- No comments or docstrings unless the code looks safe to change but is not (see `CLAUDE.md`
  "Comments"). Never delete existing ones. Check `git diff` for new `#` and `"""` lines before
  each commit.
- One commit per task, with the subject given in the task. Body: 1–3 plain lines. No
  `Co-Authored-By` trailer, and no mention of Claude.
- Keep `pyproject.toml`, `poetry.lock` and `.github/workflows/ci.yml` changes minimal. Epic 9 edits
  them in parallel.
- Tools: `poetry run ruff check`, `poetry run ruff format --check`, `poetry run pyright`,
  `poetry run pytest`, `poetry run pytest -m docker`. The test stack is
  `docker compose up -d --wait db s3 mail`.
- Existing tests may change only as the design's "Existing tests that change" lists, plus the
  migration head assertion `0004` → `0005` and the model import in `tests/db/test_migrations.py`.
  Nothing else is weakened.

## Review Focus

These inputs are implied by the spec, but its AC don't pin them. The owning task adds a test for
each.

1. A project name in Cyrillic, such as `Дипломна робота`. The mail must still go out (UTF-8 body)
   and contain the name. Test in Task 2.
2. A recipient with a plus tag or mixed case, such as `Anna+Hub@Example.com`. It is accepted and
   answered and mailed in lower case. Test in Task 2.
3. A recipient with surrounding spaces or a CR/LF, such as `" anna@example.com"` or
   `"a@example.com\r\nBcc: x@example.com"`. The answer is 422, never 500, and never a second
   recipient. Test in Task 2.
4. A `token` with URL-special characters, such as `a b&next=//evil.example`. On the `303` it is
   percent-encoded into the `Location` query, and the target origin stays `APP_WEB_URL`. Test in
   Task 4.
5. A 128-character `token` that was never issued gets the plain 404, not 422 or 500. Test in
   Task 3.

---

### Task 1: Send mail through a Mailer, with Mailpit locally and in CI

Subject: `Send mail through SMTP, caught by Mailpit locally and in CI`

**Files:**
- Create: `src/project_hub/mail/__init__.py`, `src/project_hub/mail/mailer.py`
- Modify:
  - `src/project_hub/core/config.py`: add `smtp_host`, `smtp_port`, `mail_from`.
  - `src/project_hub/main.py`: add `app.state.mailer`.
  - `docker-compose.yml`: add the `mail` service; give the `api` the SMTP env and make it depend
    on `mail`.
  - `.github/workflows/ci.yml`: add the `mailpit` service and two env lines in `checks`.
  - `.env.example`
  - `README.md`: a short "Mail" section next to "File storage".
  - `tests/conftest.py`: `_clean_env` keys and the `mailpit_url` / `smtp_port` fixtures.
  - `tests/test_docker_smoke.py`: add `APP_MAIL_PORT`/`APP_MAIL_UI_PORT` = `"0"` to every compose
    env, and `mail` in the running set.
- Create: `tests/support/mail.py`, `tests/mail/__init__.py`, `tests/mail/test_smtp_mailer.py`.
- Test: `tests/test_config.py` (new settings).

**Interfaces:**
- Produces:
  - `OutgoingMail(to: str, subject: str, text: str)`: a frozen dataclass.
  - `class Mailer(Protocol): async def send(self, mail: OutgoingMail) -> None`.
  - `class MailDeliveryError(Exception)`.
  - `class SmtpMailer: __init__(self, host: str, port: int, sender: str, *, timeout: float = 10)`.
    `send` builds an `email.message.EmailMessage` (`From`, `To`, `Subject`, text body, utf-8) and
    sends it with `smtplib.SMTP(host, port, timeout=timeout)` inside `asyncio.to_thread`.
    `smtplib.SMTPException` and `OSError` → `MailDeliveryError` (`from None` is not needed; keep
    the cause).
  - `create_mailer(settings: Settings) -> Mailer | None`: `None` when `smtp_host` is unset.
  - `app.state.mailer: Mailer | None`.
  - Settings:
    - `smtp_host: str | None = None` (blank → None);
    - `smtp_port: int = Field(default=25, ge=1, le=65535)`;
    - `mail_from: str = "noreply@project-hub.test"`, validated by `^[^@\s]+@[^@\s]+$`, which also
      rejects CR/LF. Not `EmailStr`.
  - Test support (`tests/support/mail.py`):
    - `DEFAULT_MAILPIT_URL = "http://localhost:8025"` and `DEFAULT_SMTP_PORT = 55436`;
    - `random_address() -> str`, which returns `f"{uuid4().hex}@example.com"`;
    - `messages_to(mailpit_url: str, address: str, *, expect: int = 1, timeout: float = 5) -> list[dict[str, Any]]`.
      It polls `GET /api/v1/search?query=to:"<address>"` until `expect` messages are there, or the
      timeout passes, and returns each full message from `GET /api/v1/message/{ID}` (keys `From`,
      `To`, `Subject`, `Text`);
    - `mailpit_unreachable_reason(url) -> str | None`.
  - Fixtures in `tests/conftest.py`:
    - `smtp_port() -> int` reads env `TEST_SMTP_PORT` (default 55436);
    - `mailpit_url() -> str` reads `TEST_MAILPIT_URL` (default `http://localhost:8025`). It is
      session scoped and calls `pytest.fail` with "Start it with:
      docker compose up -d --wait mail (or set TEST_MAILPIT_URL)" when unreachable, as
      `s3_endpoint_url` does.

- [ ] **Step 1: Write the failing tests** in `tests/mail/test_smtp_mailer.py`:
  - `test_send_delivers_a_plain_text_mail`: `SmtpMailer("localhost", smtp_port, "noreply@project-hub.test")`
    sends `OutgoingMail(to=random_address(), subject="You are invited to a project on Project Hub", text="Привіт\nhttp://x/join?token=abc")`.
    Then `messages_to(...)` returns one message. Its `From["Address"]` is the sender, its `To` is
    exactly `[address]`, its `Subject` matches, and its `Text` contains `Привіт` and the URL.
  - `test_send_to_an_unreachable_server_raises_mail_delivery_error`: port of a freshly closed
    socket (bind `127.0.0.1:0`, read the port, close) → `pytest.raises(MailDeliveryError)`.
  - In `tests/test_config.py`: `mail_from` rejects `"noreply"`, `"a@b\r\nBcc: c@d"` and
    `"a b@c"`, and accepts the default. `smtp_port` rejects `0` and `65536`. A blank `smtp_host` is
    `None`.
- [ ] **Step 2: Run, expect FAIL** (import error):
  `poetry run pytest tests/mail tests/test_config.py -v`.
- [ ] **Step 3: Implement** the mail package, the settings, `main.py` (`app.state.mailer =
  create_mailer(settings)`), and the support module and fixtures.
- [ ] **Step 4: Compose and CI.**
  - `docker-compose.yml` `mail` service:
    - image `axllent/mailpit:<exact tag>`. Pick the newest release that is at least two weeks old
      and confirm it with `docker pull`;
    - ports `"127.0.0.1:${APP_MAIL_PORT:-55436}:1025"` and
      `"127.0.0.1:${APP_MAIL_UI_PORT:-8025}:8025"`;
    - a healthcheck (`["CMD", "/mailpit", "readyz"]`, interval 2s, retries 15; confirm the command
      exists in the image).
  - `api` env: `APP_SMTP_HOST: mail`, `APP_SMTP_PORT: "1025"`, and `depends_on: mail:
    condition: service_healthy`.
  - `ci.yml` `checks.services.mailpit`: image (same tag), ports `["1025:1025", "8025:8025"]`. In
    `checks.env`: `TEST_SMTP_PORT: "1025"` and `TEST_MAILPIT_URL: http://localhost:8025`. Nothing
    else in `ci.yml`.
  - `.env.example`: `APP_SMTP_HOST`/`APP_SMTP_PORT`/`APP_MAIL_FROM` (commented, like the S3
    block), `APP_MAIL_PORT=55436`, `APP_MAIL_UI_PORT=8025`, and the `TEST_SMTP_PORT`/
    `TEST_MAILPIT_URL` export lines next to the S3 one. Say that the inbox is at
    `http://localhost:8025`.
  - `tests/test_docker_smoke.py`: add `"APP_MAIL_PORT": "0", "APP_MAIL_UI_PORT": "0"` to every
    compose `env`. `test_compose_stack_serves_health` expects
    `{"db": "running", "s3": "running", "mail": "running", "api": "running"}`.
- [ ] **Step 5: Run**:
  - `docker compose up -d --wait db s3 mail`;
  - `poetry run pytest tests/mail tests/test_config.py -v`, expect PASS;
  - `docker compose config -q`, expect exit 0;
  - `poetry run pytest -m docker -v`, expect all PASS;
  - full `poetry run pytest`, expect PASS;
  - ruff and pyright clean.
- [ ] **Step 6: Commit** with the subject above.

### Task 2: Share a project by email with GET /project/{id}/share

Subject: `Share a project by email with GET /project/{id}/share`

**Files:**
- Create:
  - `src/project_hub/db/migrations/versions/0005_create_project_shares.py`
  - `src/project_hub/shares/__init__.py`
  - `src/project_hub/shares/tokens.py`
  - `src/project_hub/shares/entities.py`
  - `src/project_hub/shares/models.py`
  - `src/project_hub/shares/repository.py`
  - `src/project_hub/shares/repository_orm.py`
  - `src/project_hub/shares/repository_sql.py`
  - `src/project_hub/shares/service.py`
  - `src/project_hub/shares/schemas.py`
  - `src/project_hub/shares/router.py`
  - `src/project_hub/shares/dependencies.py`
- Modify:
  - `src/project_hub/db/uow.py`, `orm.py`, `sql.py`: add `shares: ShareRepository`.
  - `src/project_hub/core/exceptions.py`: add `class TooManyRequestsError(DomainError): ...`.
  - `src/project_hub/core/error_handlers.py`: map it to 429.
  - `src/project_hub/core/config.py`: add `public_url`.
  - `src/project_hub/main.py`: include the shares router.
  - `pyproject.toml` / `poetry.lock`: `poetry add "email-validator (>=2.2,<3)"`. Match the style of
    the list.
  - `docker-compose.yml`: add `APP_PUBLIC_URL: ${APP_PUBLIC_URL:-http://localhost:${APP_PORT:-8000}}`
    to `api`.
  - `.env.example`: add `APP_PUBLIC_URL`.
  - `tests/conftest.py`: `api_client` gets `smtp_host="localhost"`, `smtp_port=<TEST_SMTP_PORT>`
    and `public_url="http://testserver"`, and `_clean_env` the new keys. Add a factory fixture for
    a client with overridden settings, used by the 503 tests and Task 4.
  - `tests/db/test_migrations.py`: head `0005`, import `ShareModel`, a `project_shares` table test
    and a downgrade test.
  - `tests/core/test_exceptions.py` or `test_error_handlers.py`: add 429 to the mapping test.
  - `tests/projects/test_projects_auth_api.py`: add the param
    `("GET", f"/project/{uuid4()}/share?with=a@example.com", id="share")`.
  - `README.md`: section "Share by email" (the share part), `project_shares` in the migration
    list, `project shared` in the security log list.
  - `docs/PRDs/roadmap.md`: "Deferred to implementation" row "Email share details" → decided in
    10 (one-line summary + link to the design); add the "For the AWS epics (8a, 8b)" bullets
    from the design under "AWS cost strategy" notes or as a short subsection there.
- Test: `tests/shares/__init__.py`, `tests/shares/test_repository_contract.py`,
  `tests/shares/test_share_api.py`, `tests/shares/test_shares_log.py`,
  `tests/shares/test_tokens.py`.

**Interfaces:**
- Consumes: `Mailer`, `OutgoingMail` and `MailDeliveryError` (Task 1); `app.state.mailer`; the
  `get_project` access check pattern from `projects/service.py`.
- Produces:
  - `tokens.new_token() -> str` and `tokens.hash_token(token: str) -> str` (64 lowercase hex).
  - `ShareLink(id: UUID, project_id: UUID, email: str, expires_at: datetime)`: a frozen dataclass.
  - `ShareRepository` Protocol, exactly as in the design: `delete_expired`, `count_pending`
    (keyword-only `except_email`), `put`, `find_pending`, `claim`. Task 3 uses `find_pending` and
    `claim`; build and contract-test all five here.
  - `uow.shares` on both Units of Work.
  - `ShareModel` (`__tablename__ = "project_shares"`). Constraint names:
    `fk_project_shares_project_id_projects` (CASCADE), `uq_project_shares_project_id_email`,
    `uq_project_shares_token_hash`, `ck_project_shares_email_length`,
    `ck_project_shares_token_hash_format`. The ORM metadata must match the migration (the existing
    `test_orm_metadata_matches_migrated_schema`).
  - `Settings.public_url: str | None = None`: blank → None, must start with `http://` or
    `https://`, no `?` or `#`, trailing `/` stripped.
  - `dependencies.get_share_mailer(request) -> Mailer`: raises
    `ServiceUnavailableError("Email sharing is not configured")` if `app.state.mailer` or
    `settings.public_url` is None. Declare it after `CurrentUser` in the route.
  - `service.share(uow, mailer: Mailer, public_url: str, user: User, project_id: UUID, email: str, *, now: datetime) -> ShareLink`.
    Runs the design's share table: steps 4–7, then `delete_expired`, `count_pending`, `put`,
    send, commit, and the log record. `email` arrives lower-cased.
  - `schemas.ShareEmail = Annotated[EmailStr, StringConstraints(max_length=254)]`, applied as
    `Query(alias="with")`. `ShareResponse(email: str, expires_at: datetime)`.
  - Log: logger `project_hub.shares.service`; `extra` keys `event`, `login`, `user_id`,
    `project_id` and `email`; message like the projects one.
- Repository notes:
  - `put` is `INSERT … ON CONFLICT ON CONSTRAINT uq_project_shares_project_id_email DO UPDATE SET
    token_hash, expires_at, created_at = now()`, inside a savepoint (as `add_member`). A
    `ForeignKeyViolation` on `fk_project_shares_project_id_projects` → `NotFoundError("Project not
    found")`.
  - The ORM side may use `sqlalchemy.dialects.postgresql.insert(...).on_conflict_do_update`.

- [ ] **Step 1: Write the failing repository contract tests** (`tests/shares/test_repository_contract.py`,
  via the `database` fixture). Cover design AC 24–28:
  - put → find_pending returns `ShareLink` with the stored lower-case email and expiry;
    find_pending at `expires_at + 1s` → None.
  - A second put for the same project+email replaces the hash; the old hash → None. Same email on
    a second project → two links.
  - count_pending counts only unexpired links of that project and leaves out `except_email`;
    delete_expired removes only that project's expired ones.
  - claim True then False; afterwards find_pending → None; a claim then leaving the UoW without
    commit → still findable in a new UoW.
  - put for `uuid4()` project → `NotFoundError`, and the same UoW can still `put` for a real
    project and commit. Deleting the project (`uow.projects.delete`) → find_pending None.

  Create users and projects through `uow.users`/`uow.projects` as the projects contract tests do.
- [ ] **Step 2: Write the failing API tests** (`tests/shares/test_share_api.py`, `api_client`,
  `mailpit_url`). One test per design AC 1, 3–5, 7–10, 12 and Review Focus 1–3. Key assertions:
  - AC 1: status 200, body keys exactly `{"email", "expires_at"}`, and `expires_at` within
    ±1 minute of now + 7 days. In the single mail found by `messages_to`: the sender, the subject,
    `@mila` and the project name in the `Text`, and a regex
    `http://testserver/join\?token=([A-Za-z0-9_-]{43})` matching once.
  - AC 2: with `psycopg` on `migrated_database_url`,
    `SELECT token_hash FROM project_shares` equals `hash_token(<mailed token>)`, and no row
    contains the token. Combined with caplog over all loggers: the token is in no
    `record.getMessage()`.
  - AC 3 and 4: participant 403, outsider/unknown 404 with identical bodies. `messages_to(...,
    expect=0, timeout=1)` returns `[]`.
  - AC 5: `with` missing, `""`, `"not-an-email"`, 255 characters (`"a"*243 + "@example.com"`),
    and a project id `"abc"` → 422.
  - AC 7: a factory client with `smtp_host=None`, and another with `public_url=None` → 503 with
    the exact text.
  - AC 8: a factory client whose `smtp_port` is a closed port → 503 `Email could not be sent`.
    Then, using the normal `api_client`, the same DB has no `project_shares` row.
  - AC 9: insert 10 links for 10 addresses through 10 share calls (real mail, all accepted). The
    11th → 429 and no mail; sharing again with address #3 → 200. Make one of the 10 expired
    (`UPDATE project_shares SET expires_at = now() - interval '1 second' WHERE email = …`), and
    the 11th → 200.
  - AC 10: two shares; the stored row count for that email is 1, and its hash equals the second
    mail's token's hash, not the first's. The join half of AC 10 is added in Task 3.
  - AC 12: `updated_at` from `GET …/info` is unchanged after a share.

  `tests/shares/test_shares_log.py`: AC 11, in the style of `tests/projects/test_projects_log.py`.
  `tests/shares/test_tokens.py`: `new_token()` is 43 URL-safe characters and two calls differ;
  `hash_token("abc")` equals the known SHA-256 hex of `abc`.
- [ ] **Step 3: Run, expect FAIL**: `poetry run pytest tests/shares -v`.
- [ ] **Step 4: Implement** the migration, the model, the repositories, the UoW wiring, the
  service, the router (`@router.get("/project/{project_id}/share")`, response `ShareResponse`), the
  dependency, `TooManyRequestsError` → 429, `public_url`, the dependency add, compose, the
  `.env.example` line, README, and the roadmap.
- [ ] **Step 5: Update the migration tests** (head `0005`, the table and constraint test, a
  downgrade to `0004` drops it) and the auth param. Run the full suite: `poetry run pytest -v`,
  expect PASS (both backends). Run `poetry run python -m tests.support.backend_coverage` on the
  log as CI does, and `poetry check --lock`; ruff and pyright must be clean.
- [ ] **Step 6: Commit** with the subject above.

### Task 3: Join a project through the emailed link with GET /join

Subject: `Join a project as a participant through the emailed link`

**Files:**
- Modify:
  - `src/project_hub/shares/service.py`: add `join`.
  - `src/project_hub/shares/router.py`: add `GET /join`.
  - `src/project_hub/shares/schemas.py`: add `JoinResponse`.
  - `src/project_hub/main.py`: add `NoStoreMiddleware`.
  - `README.md`: the join part of "Share by email", with the Swagger demo steps and the
    `project joined` log event.
- Create: `src/project_hub/shares/no_store.py`, `tests/shares/test_join_api.py`.
- Modify tests: `tests/shares/test_shares_log.py` (AC 21), `tests/shares/test_share_api.py`
  (the join half of AC 10), `tests/test_docker_smoke.py` (new test, AC 30).

**Interfaces:**
- Consumes:
  - `ShareRepository.find_pending` and `claim`, and `hash_token` (Task 2);
  - `get_current_user(credentials, uow, tokens)` and `bearer_scheme` from
    `auth/dependencies.py`;
  - `get_token_service`;
  - `uow.projects.get_for_user` and `add_member`;
  - `ProjectResponse.from_access`.
- Produces:
  - `JoinResult(access: ProjectAccess, already_member: bool)`: a frozen dataclass in
    `shares/entities.py`.
  - `service.join(uow, user: User, token: str, *, now: datetime) -> JoinResult`, following the
    design's join table, checks 4–6:
    1. `find_pending(hash_token(token), now)`; None → `NotFoundError("Invite link is invalid or
       expired")`.
    2. `get_for_user` is not None → `JoinResult(access, True)`, with no claim and no commit.
    3. `claim` returns False → the same NotFound.
    4. `add_member`. A `ConflictError` → `await uow.rollback()`, re-read `get_for_user`, and
       return `already_member=True`. A `NotFoundError` propagates.
    5. Re-read `get_for_user`, commit, log `project joined` (`email` = `link.email`).
  - `JoinResponse(login: str, already_member: bool, project: ProjectResponse)`.
  - Route `GET /join`, parameters:
    - `request: Request`;
    - `token: Annotated[str, Query(min_length=1, max_length=128)]`;
    - `credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]`;
    - `uow`;
    - `tokens: Annotated[TokenService, Depends(get_token_service)]`.

    When `"authorization" not in request.headers`: `AuthenticationError("Not authenticated")`
    (Task 4 adds the 303 branch here). Otherwise `user = await get_current_user(credentials, uow,
    tokens)`, then `service.join`. (`HTTPBearer(auto_error=False)` returns None for `Basic …`,
    and `get_current_user` turns that into 401.)
  - `NoStoreMiddleware`: a pure ASGI middleware like `UploadLimitMiddleware`. For
    `scope["path"] == "/join"`, it adds `cache-control: no-store` to the `http.response.start`
    headers, on every status.

- [ ] **Step 1: Write the failing tests** (`tests/shares/test_join_api.py`). Use a helper that
  shares and reads the mailed token through `messages_to`. Cover design AC 13–16, 18 (the
  no-`APP_WEB_URL` cases, broken JWT, `Basic x`), 19, 20, 22 and Review Focus 5:
  - AC 13: Anna's join → 200 with `{"login": "anna", "already_member": false, "project": {…
    "my_role": "participant"}}`, then `GET …/info` 200 for Anna, and the members list contains
    Anna.
  - AC 14: then Zoe → 404 with the exact detail, and Zoe's `GET …/info` → 404.
  - AC 15:
    - a never-issued token;
    - an expired link (`UPDATE … SET expires_at = now() - interval '1 second'`);
    - a replaced link (first mail of two);
    - a deleted project (`DELETE /project/{id}` by Mila).

    All four bodies equal AC 14's.
  - AC 16: Mila joins her own link → 200, `already_member: true`, `my_role: "owner"`. An existing
    participant gets the same with `participant`. Afterwards Anna still joins with it (200,
    `already_member: false`).
  - AC 18: no header → 401 + `WWW-Authenticate: Bearer`. `Authorization: Bearer garbage` → 401.
    `Authorization: Basic eDp5` → 401. The link is still pending afterwards (Anna can join).
  - AC 19: no `token`, `token=` and a 129-character token → 422. Review Focus 5: a 128-character
    unknown token → 404.
  - AC 20: every response above has `cache-control == "no-store"`, the 422 included.
  - AC 22: `updated_at` is unchanged after a join.

  Also add the join half of AC 10 to `test_share_api.py`: the first mail's token → 404, the second
  → 200. And add AC 21 to `test_shares_log.py`: one `project joined` record with Anna's login and
  id, the project id and the link's email; none for `already_member` or the refused joins.
- [ ] **Step 2: Docker test** `test_compose_stack_shares_and_joins_a_project` in
  `tests/test_docker_smoke.py`. Use the same pattern as `test_compose_stack_round_trips_a_document`,
  with `APP_PUBLIC_URL=http://share.smoke.test` in the env and the mail ports `"0"`.
  1. Register and log in Mila, create a project, and share it to `random_address()`.
  2. Find the mail through `http://127.0.0.1:<compose port mail 8025>`, using `messages_to` with
     that URL.
  3. Assert that the link starts with `http://share.smoke.test/join?token=`.
  4. Register and log in Anna. Call `GET http://127.0.0.1:<api port>/join?token=…` with her
     bearer, and expect 200 and `already_member` false.
- [ ] **Step 3: Run, expect FAIL**: `poetry run pytest tests/shares -v`.
- [ ] **Step 4: Implement** `join`, `JoinResponse`, the route, the middleware (register it in
  `create_app`), and README.
- [ ] **Step 5: Run**: the full `poetry run pytest -v` passes on both backends,
  `poetry run pytest -m docker -v` passes, and ruff and pyright are clean.
- [ ] **Step 6: Commit** with the subject above.

### Task 4: Send a browser without a sign-in to the web app's join page

Subject: `Send a browser that opens the join link to the web app's sign-in`

**Files:**
- Modify:
  - `src/project_hub/core/config.py`: add `web_url`, with the same rules as `public_url`.
  - `src/project_hub/shares/router.py`: add the 303 branch.
  - `docker-compose.yml`: add `APP_WEB_URL: ${APP_WEB_URL:-}` to `api`.
  - `.env.example`
  - `README.md`
  - `docs/PRDs/roadmap.md`:
    - the "Deferred to implementation" row on browser auth → decided in 10;
    - the "Frontend requests" F5 row → `accepted`, with the final shape: the mail links to the
      API `GET /join`; without `Authorization` and with `Accept: text/html`, a browser gets `303`
      to `<APP_WEB_URL>/join?token=…`; the page calls `/api/join?token=…` with Bearer; the
      response is `{login, already_member, project}`; nginx must hide `token` in its access log;
    - row 10 in the epics table keeps its scope.
  - `docs/frontend/roadmap.md`: the F5 line, "the `GET /join` browser redirect only if epic 10
    chooses it" → it does, `303`.
- Test: `tests/shares/test_join_redirect_api.py`, `tests/test_config.py`.

**Interfaces:**
- Consumes: the `/join` route (Task 3), the factory client fixture (Task 2).
- Produces: `Settings.web_url: str | None = None`. In the route, before the 401 branch: if
  `"authorization" not in request.headers` and `settings.web_url` and `"text/html"` is in
  `request.headers.get("accept", "")`, return
  `RedirectResponse(f"{web_url}/join?{urlencode({'token': token})}", status_code=303)`.

- [ ] **Step 1: Write the failing tests** with a factory client `web_url="http://web.test"`:
  - AC 17: no header and `Accept: text/html,application/xhtml+xml` → 303,
    `location == "http://web.test/join?token=<token>"` for a mailed token, and
    `cache-control: no-store`. Anna can still join with it afterwards (the link stays pending).
  - AC 18 (redirect side):
    - `Accept: application/json` → 401;
    - `Bearer garbage` + `text/html` → 401;
    - `Basic eDp5` + `text/html` → 401;
    - the plain `api_client` (no `web_url`) + `text/html` → 401.
  - Review Focus 4: token `a b&next=//evil.example` → 303, and `urlsplit(location)` has netloc
    `web.test`, path `/join`, and `parse_qs(query) == {"token": ["a b&next=//evil.example"]}`.
  - Config: `web_url` and `public_url` reject `ftp://x`, `http://x/?a=1` and `http://x/#f`; they
    strip `http://x/` to `http://x`; a blank value → None.
- [ ] **Step 2: Run, expect FAIL**:
  `poetry run pytest tests/shares/test_join_redirect_api.py tests/test_config.py -v`.
- [ ] **Step 3: Implement** the setting and the branch. Disable redirect following in the test
  client calls (`follow_redirects=False`).
- [ ] **Step 4: Run** the full suite. It passes, and ruff and pyright are clean.
- [ ] **Step 5: Commit** with the subject above.

### Task 5: Keep join tokens out of the access log

Subject: `Hide join tokens in the access log`

**Files:**
- Modify: `src/project_hub/core/logging.py`, `README.md` (one line in the security notes).
- Test: `tests/core/test_logging.py`.

**Interfaces:**
- Produces: `configure_logging()` also adds one `_HideTokenFilter` (idempotent: no second
  instance on repeat calls) to `logging.getLogger("uvicorn.access")`. For a record whose `args` is
  a tuple of at least 3 items with a `str` at index 2 (uvicorn's `full_path`), it replaces each
  `token=<value>` query value with `token=***` (regex `([?&]token=)[^&\s]*`). It returns True
  (never drops records).

- [ ] **Step 1: Write the failing tests:**
  - `test_access_log_hides_join_token`: call `configure_logging()` and capture with
    `caplog.at_level(logging.INFO, logger="uvicorn.access")`. Then call
    `logging.getLogger("uvicorn.access").info('%s - "%s %s HTTP/%s" %d', "127.0.0.1:5000", "GET",
    "/join?token=SeCrEt-123&x=1", "1.1", 303)`. The message contains `/join?token=***&x=1` and not
    `SeCrEt-123`.
  - `test_access_log_keeps_other_lines`: `/projects?limit=5` is unchanged.
  - `test_configure_logging_twice_adds_one_filter`: count the filters on `uvicorn.access` after
    two calls.
- [ ] **Step 2: Run, expect FAIL**: `poetry run pytest tests/core/test_logging.py -v`.
- [ ] **Step 3: Implement.** The filter class needs a one-line docstring only if its reason is
  hidden: uvicorn sets up its loggers before importing the app, so the filter survives. Write it
  only if that holds and is not obvious from the name.
- [ ] **Step 4: Run** the full suite. It passes, and ruff and pyright are clean.
- [ ] **Step 5: Commit** with the subject above.

---

## Coverage map (design AC → task)

| AC | Task | AC | Task |
|---|---|---|---|
| 1–12 | 2 (10's join half in 3) | 24–28 | 2 |
| 13–16, 18–22 | 3 | 29 | 2 |
| 17, 18 (redirect side) | 4 | 30 | 3 |
| 23 | 5 | 31 | final verification |
