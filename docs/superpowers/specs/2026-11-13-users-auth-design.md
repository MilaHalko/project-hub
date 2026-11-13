# Epic 3: Users and auth

Date: 2026-11-13
Status: approved design (2026-11-13)
Roadmap: [`docs/PRDs/roadmap.md`](../../PRDs/roadmap.md), epic 3
Spec: [`docs/initial-spec.md`](../../initial-spec.md) — `POST /auth`, `POST /login`,
"JWT should last 1 hour", "validate all data with pydantic"

## Intent

Let people register, log in, log out and change their password, and give every
later epic one way to ask "who is calling?". From epic 4 on, every business route
depends on the current-user dependency built here. The project is defended in
front of a mentor, so the result must also be demonstrable live: register → log
in → call a protected route with the token in Swagger → log out → the same token
is refused.

The spec is the floor, not the ceiling: additions that users expect and that are
cheap to build and defend were proposed to the user and accepted one by one (see
[Beyond the spec](#beyond-the-spec)).

## Goals

- `POST /auth` creates a user from `login`, `password`, `repeat_password` (spec).
- `POST /login` checks `login` + `password` and returns a JWT valid for exactly
  1 hour (spec).
- Passwords are stored only as Argon2 hashes.
- A FastAPI dependency `get_current_user` turns an `Authorization: Bearer <jwt>`
  header into a `User`, or answers 401.
- `GET /users/me` returns the current user (addition, accepted).
- `POST /logout` makes every token the user holds stop working at once (addition,
  accepted).
- `PUT /users/me/password` changes the password and kills all older tokens
  (addition, accepted).
- Security events (registration, login success and failure, logout, password
  change) are logged without passwords (addition, accepted).
- All request data is validated with pydantic; all responses are JSON.

## Non-goals

- Refresh tokens (rejected, see below).
- Brute-force protection on `/login`, deleting the account (postponed, see below).
- Logging out a single device while staying logged in on others (the chosen
  logout ends every session of the user).
- Password reset by email; email in general.
- Rehashing old hashes on login when Argon2 parameters change (there are no old
  hashes yet).

## Anti-goals (it would be a failure even if it "works")

- A plain password ends up anywhere: the database, a log line, a response body
  (including a 422 validation error), `repr` of a settings or request object.
- The response tells an attacker whether a login exists (different messages or
  status codes for "no such user" and "wrong password").
- A token with a bad signature, `alg: none`, a different algorithm, no `exp`, or
  an expired `exp` is accepted.
- A token issued before a logout or a password change is still accepted.
- The JWT secret is committed to the repository or has a weak default.
- Password hashing blocks the event loop (Argon2 is deliberately slow, ~50 ms).

## Constraints

- Endpoint names exactly as in the spec: `POST /auth`, `POST /login`. Additions
  never rename or change anything the spec defines.
- Stack and tooling from the roadmap: FastAPI, pydantic v2, Poetry, ruff,
  pyright strict, pytest; no tox.
- Data layer from 1b: services get a `UnitOfWork`, call `await uow.commit()`
  themselves; `get_uow` never commits. Every database change goes into both
  backends (ORM and SQL), the shared contract tests and a new hand-written
  Alembic migration.
- Module rule from README: a module that needs another module calls that
  module's `service`, never its repository.
- Testing rule (`CLAUDE.md`, "What to test"): tests prove behaviour only. Config
  and tooling (dependencies in `pyproject.toml`, `.env.example`,
  `docker-compose.yml`) are verified by commands in verification, not by pytest
  tests that read file text.
- Do not edit `.github/workflows/` (epic 2 owns it). Epic 2 (PR #4) and the
  config-test cleanup (PR #5) are already merged; this branch is rebased on that
  `main`. If `main` moves again, `poetry.lock` conflicts are resolved by
  regenerating it with `poetry lock`, never by hand. The PR must pass CI on GitHub.
- CI's backend check (`tests/support/backend_coverage.py`) counts only tests in
  `*_contract.py` files. The repository contract tests keep satisfying it; the
  new API tests run on both backends too but need not be named `_contract`.

## Approaches considered

### Password hashing

| Option | Trade-off |
|---|---|
| **`argon2-cffi` (Argon2id)** — chosen | Winner of the Password Hashing Competition, OWASP's first recommendation; maintained; tiny API (`hash`, `verify`, `check_needs_rehash`); defaults follow RFC 9106 |
| `pwdlib[argon2]` | Same Argon2 underneath, used by the current FastAPI tutorial; adds a multi-algorithm wrapper we do not need |
| `bcrypt` | Proven, but silently truncates passwords at 72 bytes and is weaker against GPU cracking |
| `passlib` | Unmaintained; breaks on current Python and `bcrypt` versions |

The salt is not a separate column: Argon2's output is one string
(`$argon2id$v=19$m=…,t=…,p=…$<salt>$<hash>`) that carries the algorithm, its
parameters and the salt, stored in `password_hash`.

### JWT

| Option | Trade-off |
|---|---|
| **`PyJWT`, HS256** — chosen | Most used, maintained, used by the FastAPI tutorial; validates `exp` itself; `decode` requires an explicit `algorithms` list, which blocks `alg: none` and algorithm-swap attacks |
| `python-jose` | Was in older FastAPI docs; barely maintained, CVEs in 2024 |
| `authlib` / `joserfc` | Full JOSE suite; far more than needed |

HS256 (one shared secret) rather than RS256 (key pair): the same service issues
and checks the tokens, so a public key would buy nothing.

### Token model and logout

A JWT cannot be "un-issued": the server checks only its signature and `exp`.
Logout therefore needs some server-side state.

| Option | Trade-off |
|---|---|
| Pure stateless JWT, no logout | Simplest; a stolen token lives for the full hour |
| Deny-list of revoked token ids (`jti`) in a new table | Logs out one device only; one extra query per request; old rows need cleaning up; does not help password change (we do not know the ids of the other tokens) |
| **`token_version` column on `users`** — chosen (user, 2026-11-13) | One integer column; the token carries the version in claim `ver`; logout or password change increments it, so every older token is refused at once. No extra query: `get_current_user` already loads the user. Logs out every device, which is the safe default after a password change anyway |

## Beyond the spec

Proposed to the user on 2026-11-13; her decisions:

| Addition | Decision | Reason |
|---|---|---|
| `GET /users/me` | **Accepted** | Live demo of the JWT until epic 4 adds protected routes |
| `POST /logout` (via `token_version`) | **Accepted** | Expected basic feature; a stolen token stops working after logout |
| `PUT /users/me/password` | **Accepted** | Expected basic feature; kills tokens that may have leaked with the old password |
| Password must not equal the login | **Accepted** | One validator, removes the most obvious weak password |
| Security event log | **Accepted** | A few log lines; helps investigate attacks |
| Refresh tokens | **Rejected** | Contradicts "JWT should last 1 hour": a refresh token stretches a session over days; large, risky logic (storage, rotation, reuse detection) |
| Brute-force protection on `/login` | **Postponed — important future improvement** | Kept out to keep this epic's scope modest. Sketch for later: a `login_attempts` table keyed by the submitted login (also for unknown logins, so a 429 does not reveal which logins exist); 5 failures → 429 `Too Many Requests` with `Retry-After` for 15 minutes; new `TooManyRequestsError` → 429. Known trade-off: an attacker can lock someone's login for 15 minutes. Alternative at the edge: a rate-based rule on the load balancer (epic 8) |
| `DELETE /users/me` | **Postponed — future improvement** | Depends on what happens to projects the user owns; decide in or after epic 4 |

## Design

### Layout

```
src/project_hub/
  core/config.py          + jwt_secret
  auth/
    passwords.py          PasswordHasher: hash / verify (argon2-cffi), run off the event loop
    tokens.py             TokenService: issue / decode (PyJWT, HS256, 1 h), injectable clock for issuing
    schemas.py            RegisterRequest, LoginRequest, TokenResponse, ChangePasswordRequest
    service.py            register(), login(), logout(), change_password(); security event log
    router.py             POST /auth, POST /login, POST /logout
    dependencies.py       get_current_user, CurrentUser (Annotated alias), bearer scheme
  users/
    entities.py           User gets token_version
    repository.py         + update_password(), increment_token_version()
    repository_orm.py     + both methods
    repository_sql.py     + both methods
    models.py             + token_version
    service.py            create_user(), get_user(), get_user_by_login(),
                          set_password(), revoke_tokens()  (wrap the repository)
    schemas.py            UserResponse (id, login, created_at — never password_hash or token_version)
    router.py             GET /users/me, PUT /users/me/password
  db/migrations/versions/
    0002_add_users_token_version.py
```

Dependency direction: `auth.service` → `users.service` → `uow.users`.
`users.router` → `auth.dependencies` / `auth.service` → `users.service`. No
import cycles; `core/` still imports no feature module.

### Settings

- `jwt_secret: SecretStr | None = None`, env `APP_JWT_SECRET`.
- An empty value counts as "not set". A set value shorter than 32 characters
  fails settings validation (HS256 needs at least a 256-bit key).
- Not set → the app still starts (`/health` works, as without a database), but
  `POST /login` and every route that needs the current user answer 500 and log
  `APP_JWT_SECRET is not set`. This mirrors how 1b handles a missing
  `APP_DATABASE_URL`, and keeps the existing compose and Docker smoke tests
  (which run with an empty env file) unchanged.
- Never committed. `.env.example` has the variable commented out with the
  command to generate one: `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
  `docker-compose.yml` passes `APP_JWT_SECRET: ${APP_JWT_SECRET:-}` to `api`.
  Tests build settings with their own value.

### Validation (pydantic)

| Field | Rule |
|---|---|
| `login` | 3–32 characters, only `A–Z a–z 0–9 _ . -`; case-sensitive (as the 1b contract tests already fix: `mila` and `Mila` are different users) |
| `password`, `new_password` | 8–128 characters, printable ASCII only (English letters, digits, keyboard symbols, space; user, 2026-11-14); `SecretStr` so it never shows in `repr`; must not equal the login |
| `repeat_password`, `repeat_new_password` | must equal the password above, otherwise 422 `Passwords do not match` |
| `new_password` | must differ from `current_password`, otherwise 422 |

Invalid input → 422. The validation-error response never echoes the submitted
values back: the `input` (and `ctx`) parts of FastAPI's default error list are
removed for all routes, so a rejected password is not returned in the body.

### Endpoints

| Request | Success | Errors |
|---|---|---|
| `POST /auth` `{login, password, repeat_password}` | 201 `{id, login, created_at}` | 422 invalid input; 409 `Login '<login>' is already taken` |
| `POST /login` `{login, password}` | 200 `{access_token, token_type: "bearer", expires_in: 3600}` | 422; 401 `Invalid login or password` (same for unknown login and wrong password) |
| `GET /users/me` + token | 200 `{id, login, created_at}` | 401 |
| `POST /logout` + token | 204, no body | 401 |
| `PUT /users/me/password` + token `{current_password, new_password, repeat_new_password}` | 200 with a fresh token, same body as `/login` | 401 bad token; 400 `Current password is incorrect`; 422 invalid input |

All 401 responses carry `WWW-Authenticate: Bearer` (already done by the 1b error
handler for `AuthenticationError`). The wrong current password is a 400
(`DomainError`), not a 401: the caller's token is fine, and a 401 would tell
clients to drop it.

### Token

- Claims: `sub` = user id (UUID as string), `ver` = the user's `token_version`
  at issue time, `iat` = issue time, `exp` = `iat` + 3600 s.
- Signed with HS256 and `APP_JWT_SECRET`.
- Decoding requires `exp`, `iat`, `sub`, `ver`, accepts only HS256, and applies no
  leeway (the 1-hour limit is exact).
- Expiry is checked by PyJWT itself, against real time; our code never compares
  `exp` by hand. `jwt.decode` cannot take a clock, so the clock is injectable only
  when *issuing* a token: tests issue back-dated tokens (for example "issued
  3590 s ago") instead of waiting an hour. *Builder's call, settled in the design
  check: rejected alternatives were switching PyJWT's `exp` check off and
  comparing by hand (a security check we would own), or freezing time with an
  extra dev library (`freezegun` / `time-machine`).*

### Current-user dependency

`get_current_user` reads the `Authorization` header through FastAPI's
`HTTPBearer(auto_error=False)` (this is what makes the "Authorize" button appear
in Swagger) and raises `AuthenticationError` (→ 401) when:

- the header is missing or not `Bearer`;
- the token is malformed, has a wrong signature, a different algorithm or `alg: none`;
- `exp`, `iat`, `sub` or `ver` is missing, `sub` is not a UUID, `ver` is not an
  integer, or the token has expired;
- the user in `sub` no longer exists;
- `ver` differs from the user's current `token_version` (logged out or password
  changed since the token was issued).

Otherwise it returns the `User` loaded through `users.service.get_user`. Epic 4
uses it as `user: CurrentUser`.

### Logout and password change

- `logout`: `users.service.revoke_tokens(user.id)` increments `token_version`,
  then commits. Every token with the old `ver` is refused from then on.
- `change_password`: verify `current_password` against the stored hash (off the
  event loop); on mismatch raise `DomainError("Current password is incorrect")`.
  Otherwise hash the new password and call `users.service.set_password`, which
  stores the hash **and** increments `token_version` in one statement; commit;
  return a fresh token with the new version.
- Both repository methods are single atomic `UPDATE … RETURNING` statements in
  the SQL backend (`token_version = token_version + 1`), and the equivalent in the
  ORM backend, so two concurrent requests cannot lose an increment.

### Login timing

When the login is unknown, `login()` still runs one Argon2 verification against
a fixed dummy hash, so "no such user" and "wrong password" take about the same
time and cannot be told apart by timing.

### Security event log

`auth/service.py` uses a module logger (`logging.getLogger(__name__)`) and logs
at `INFO`: `user registered`, `login succeeded`, `login failed`, `logout`,
`password changed`, each with the login (and user id when known). Never a
password, a hash or a token.

### Database

- `User` gains `token_version: int`.
- `UserRepository` gains:
  - `update_password(user_id, password_hash) -> User | None` — sets the hash and
    increments `token_version` atomically; `None` for an unknown id;
  - `increment_token_version(user_id) -> User | None` — increments
    `token_version` atomically; `None` for an unknown id.
- Both methods in `OrmUserRepository` and `SqlUserRepository`; the existing
  methods also return `token_version`.
- Migration `0002_add_users_token_version`: `ALTER TABLE users ADD COLUMN
  token_version integer NOT NULL DEFAULT 0`; downgrade drops the column. The
  existing migration tests (round-trip, schema equals the ORM metadata) must
  keep passing.

### Docs

README: an "Auth" section (the endpoints, how to get and use a token in Swagger,
`APP_JWT_SECRET` and how to generate it, what logout does), a "Known limitations
and future improvements" list (brute-force protection, account deletion), and
the new layout entries.

## Acceptance criteria

API tests go through `TestClient` against an app built with `create_app` on the
real test Postgres, and run once per backend (`orm` and `sql`).

Registration — `POST /auth`

1. Given valid `login`, `password` and matching `repeat_password`, when posted,
   then 201 with `{id, login, created_at}` and no password, hash or
   `token_version` in the body.
2. Given a registered user, the stored `password_hash` is an Argon2 hash that is
   not the password, and the password verifies against it.
3. Given a login that is already taken, then 409 with
   `{"detail": "Login '<login>' is already taken"}`.
4. Given `repeat_password` different from `password`, then 422 and no user is created.
5. Given a login shorter than 3, longer than 32, or with a character outside
   `A–Z a–z 0–9 _ . -`, then 422.
6. Given a password shorter than 8 or longer than 128 characters, or with a
   character outside printable ASCII (Cyrillic, accented letters, emoji, tab,
   newline), then 422, and the response body does not contain the submitted
   password.
7. Given a password equal to the login, then 422.
8. Given a missing field or a body that is not JSON, then 422.

Login — `POST /login`

9. Given correct credentials, then 200 with `token_type == "bearer"`,
   `expires_in == 3600` and an `access_token`.
10. The issued token's `exp` is exactly 3600 seconds after its `iat`, `sub` is the
    user's id and `ver` is the user's `token_version`.
11. Given a wrong password, or a login that does not exist, then 401 with the same
    body `{"detail": "Invalid login or password"}` and `WWW-Authenticate: Bearer`.
12. Given a missing field, then 422.

Current user — `GET /users/me` and `get_current_user`

13. Given a token from `/login`, then 200 with that user's `{id, login, created_at}`
    and no password hash.
14. Given a token issued 3590 s ago (59 min 50 s), then 200; given a token issued
    3600 s or more ago, then 401. (The 10 s margin keeps the test stable on a
    slow machine; criterion 10 pins the exact 3600 s.)
15. Given no `Authorization` header, a non-Bearer scheme, or a malformed token,
    then 401 with `WWW-Authenticate: Bearer`.
16. Given a token signed with another secret, signed with another algorithm,
    with `alg: none`, or with a modified payload, then 401.
17. Given a correctly signed token without `exp`, `sub` or `ver`, or with a `sub`
    that is not a UUID, then 401.
18. Given a correctly signed token for a user id that does not exist, then 401.

Logout — `POST /logout`

19. Given a valid token, then 204; afterwards that token gets 401 on
    `GET /users/me`.
20. Given two tokens of the same user (two logins), logout with one makes both
    get 401; a new login afterwards gives a token that works.
21. Given no token or an invalid one, then 401.

Change password — `PUT /users/me/password`

22. Given the correct current password and a valid new one, then 200 with a fresh
    token that works; the old token gets 401; `/login` works with the new password
    and fails with the old one.
23. Given a wrong current password, then 400 `{"detail": "Current password is
    incorrect"}`, and the old password and token still work.
24. Given `repeat_new_password` different from `new_password`, a new password equal
    to the current one, equal to the login, outside 8–128 characters, or with a
    character outside printable ASCII, then 422.
25. Given no token or an invalid one, then 401.

User repository — contract tests, both backends

26. Every repository method returns a `User` with `token_version`; a new user has
    `token_version == 0`.
27. `update_password` stores the new hash and increments `token_version` by one;
    `increment_token_version` increments it by one; both return the updated
    `User`, and both return `None` for an unknown id.
28. Changes from either method are visible in a new Unit of Work only after
    `commit()`.

Migrations

29. `upgrade head` adds `users.token_version` (`integer NOT NULL DEFAULT 0`); a row
    that existed before the upgrade gets `0`; downgrade to `0001` removes the
    column; the migrated schema still matches the ORM metadata.

Security units

30. `PasswordHasher.hash` returns a different hash for the same password each
    time (salted), and `verify` accepts the right password and rejects a wrong one.
31. Settings: `APP_JWT_SECRET` is a secret (not in `repr`/`str` of settings); empty
    means not set; a value shorter than 32 characters raises `ValidationError`.
32. Given no `APP_JWT_SECRET`, the app starts and `/health` answers 200, while
    `POST /login` answers 500 with the generic body `{"detail": "Internal Server Error"}`.
33. Registration, a successful and a failed login, logout and a password change
    each write one `INFO` log record from `project_hub.auth.service`; no record
    contains the password, the hash or the token.

Checked by commands in verification, not by pytest (testing rule)

34. `poetry check --lock` passes with `argon2-cffi` and `PyJWT` as main dependencies.
35. `docker compose config` shows `APP_JWT_SECRET` passed to the `api` service.
36. A real run (`docker compose up` with a generated secret): register → login →
    `GET /users/me` 200 → logout → the same token 401 → `GET /users/me` without a
    token 401.
37. `ruff check`, `ruff format --check`, `pyright` (strict) and the full `pytest`
    (both backends) are green locally and in CI on GitHub.

## Left to the builder

- Exact class and function names inside `auth/` and `users/`, and how the
  `TokenService` and `PasswordHasher` reach the routes (app state, dependency
  functions, or both), as long as tests can issue back-dated tokens.
- How the API tests build the app per backend (a fixture next to the existing
  `database` fixture is expected).
- How hashing runs off the event loop (`anyio.to_thread.run_sync` or
  `fastapi.concurrency.run_in_threadpool`).
- Argon2 parameters: library defaults, unless tests need a faster profile
  (allowed only in tests).
- Whether the log records carry the login as a structured `extra` field or in the
  message text.
