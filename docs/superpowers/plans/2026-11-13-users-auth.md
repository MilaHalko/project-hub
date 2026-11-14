# Users and Auth (Epic 3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Register (`POST /auth`), log in with a 1-hour JWT (`POST /login`), see yourself (`GET /users/me`), log out (`POST /logout`) and change the password (`PUT /users/me/password`), with a current-user dependency for every later epic.

**Architecture:** New feature package `auth/` (password hashing, JWT, login/logout/password-change service, routes, current-user dependency) on top of `users/` (repository + new thin `service.py`, `/users/me` routes). Logout and password change bump a `users.token_version` column carried in the token as claim `ver`; the column is added by migration `0002` and implemented in both data backends.

**Tech Stack:** FastAPI 0.162, pydantic 2.14, `argon2-cffi` (Argon2id), `PyJWT` (HS256), SQLAlchemy 2 async + psycopg 3, Alembic, pytest + anyio, Poetry.

**Spec:** [`docs/superpowers/specs/2026-11-13-users-auth-design.md`](../specs/2026-11-13-users-auth-design.md) — acceptance criteria (AC) numbers below refer to it.

## Global Constraints

- Endpoint names verbatim: `POST /auth`, `POST /login`; additions `GET /users/me`, `POST /logout`, `PUT /users/me/password`.
- Token lifetime exactly 3600 s, HS256 only, no leeway; claims `sub` (UUID str), `ver` (int), `iat`, `exp`.
- `login`: 3–32 chars, regex `^[A-Za-z0-9_.-]+$`, case-sensitive. Passwords: 8–128 chars, `SecretStr`, never equal to the login.
- `APP_JWT_SECRET`: `SecretStr | None`; empty → `None`; shorter than 32 chars → `ValidationError`; never committed.
- No plain password, hash or token in a log record or response body (422 included).
- Every DB change in BOTH `OrmUserRepository` and `SqlUserRepository`, proven by `tests/users/test_repository_contract.py` (fixture `database`, params `orm`/`sql`).
- Services call `await uow.commit()`; `get_uow` never commits. A module calls another module's `service`, never its repository.
- Tests prove behaviour only (`CLAUDE.md` "What to test"): no pytest test reads `pyproject.toml`, `.env.example` or `docker-compose.yml`; no tests for `tests/support/` helpers.
- Do not touch `.github/workflows/`.
- Commits: one micro-feature per commit (code + tests + config + docs of that slice), plain-words subject saying what one can now do, 1–3 line body. **No `Co-Authored-By` trailer.** Lint/format fixes go into the slice's own commit.
- Each task runs `poetry run ruff check`, `poetry run ruff format --check`, `poetry run pyright` and the task's tests before committing. Postgres must be up: `docker compose up -d --wait db`.
- Implementation agent: `python-development:python-development-fastapi-pro`.

## Review Focus

1. A password with spaces or non-ASCII characters (`"  пароль 123 "`) is stored and checked exactly as typed — never stripped or normalised. → Task 2 test.
2. A login with surrounding spaces (`"mila "`) or non-ASCII letters is rejected with 422, never trimmed into a collision with `"mila"`. → Task 1 test.
3. A lowercase scheme (`Authorization: bearer <token>`) is accepted like `Bearer`. → Task 3 test.
4. Wrong JSON types (`"password": 12345678`) or unknown extra fields give 422 or are ignored — never 500. → Task 1 test.
5. Calling `POST /logout` twice with the same token: the second call is 401, not 500. → Task 4 test.

---

## File map

```
src/project_hub/
  main.py                 include auth + users routers; app.state.password_hasher, app.state.token_service
  core/config.py          jwt_secret                                              (Task 2)
  core/error_handlers.py  422 handler that drops "input"/"ctx"                    (Task 1)
  auth/__init__.py
  auth/passwords.py       PasswordHasher                                          (Task 1)
  auth/tokens.py          TokenService.issue (Task 2), .decode (Task 3), ver claim (Task 4)
  auth/schemas.py         RegisterRequest (1), LoginRequest + TokenResponse (2), ChangePasswordRequest (5)
  auth/service.py         register (1), login (2), logout (4), change_password (5), event log (6)
  auth/router.py          POST /auth (1), POST /login (2), POST /logout (4)
  auth/dependencies.py    get_password_hasher (1), get_token_service (2), get_current_user + CurrentUser (3)
  users/service.py        create_user (1), get_user_by_login (2), get_user (3), revoke_tokens (4), set_password (5)
  users/schemas.py        UserResponse                                            (1)
  users/router.py         GET /users/me (3), PUT /users/me/password (5)
  users/entities.py, models.py, repository*.py   token_version + increment_token_version (4), update_password (5)
  db/migrations/versions/0002_add_users_token_version.py                          (4)
tests/
  conftest.py             api_client fixture (both backends)                      (Task 1, extended in 2)
  support/auth.py         register / login / bearer helpers (no tests of its own) (Task 1, extended in 2)
  auth/test_passwords.py, test_register_api.py (1); test_tokens.py, test_login_api.py (2);
  users/test_me_api.py (3); auth/test_logout_api.py (4); users/test_change_password_api.py (5);
  auth/test_security_log.py (6)
```

---

### Task 1: Register with `POST /auth`; passwords stored as Argon2 hashes

Covers AC 1–8, 30. Also creates the shared API test fixture and the README "Auth" section.

**Files:**
- Modify: `pyproject.toml`, `poetry.lock` (`poetry add "argon2-cffi>=25.1,<26"` — check the latest release and pin `>=latest,<next-major`)
- Create: `src/project_hub/auth/__init__.py`, `auth/passwords.py`, `auth/schemas.py`, `auth/service.py`, `auth/router.py`, `auth/dependencies.py`, `users/service.py`, `users/schemas.py`
- Modify: `src/project_hub/main.py`, `src/project_hub/core/error_handlers.py`, `README.md`
- Create tests: `tests/auth/__init__.py`, `tests/auth/test_passwords.py`, `tests/auth/test_register_api.py`, `tests/support/auth.py`
- Modify tests: `tests/conftest.py` (new fixture), `tests/core/test_error_handlers.py` (one new test, existing ones untouched)

**Interfaces:**
- Produces:
  - `auth.passwords.PasswordHasher(hasher: argon2.PasswordHasher | None = None)`; `async hash(password: str) -> str`; `async verify(password_hash: str, password: str) -> bool` (False on mismatch or on an invalid hash, never raises for those). Both run the argon2 call via `anyio.to_thread.run_sync`.
  - `auth.dependencies.get_password_hasher(request: Request) -> PasswordHasher` — returns `request.app.state.password_hasher`.
  - `auth.schemas.Login = Annotated[str, StringConstraints(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_.-]+$")]`; `Password = Annotated[SecretStr, Field(min_length=8, max_length=128)]` (if pydantic rejects length constraints on `SecretStr`, use an `AfterValidator` that checks `len(v.get_secret_value())`).
  - `auth.schemas.RegisterRequest(login: Login, password: Password, repeat_password: SecretStr)`; a `model_validator(mode="after")` raises `ValueError("Passwords do not match")` and `ValueError("Password must not equal the login")`.
  - `users.schemas.UserResponse(id: UUID, login: str, created_at: datetime)`, built with `UserResponse.from_user(user: User)` (or `model_validate(user, from_attributes=True)`).
  - `users.service.create_user(uow: UnitOfWork, login: str, password_hash: str) -> User` (calls `uow.users.add(NewUser(...))`, no commit).
  - `auth.service.register(uow: UnitOfWork, hasher: PasswordHasher, data: RegisterRequest) -> User` — hashes, creates, commits.
  - `auth.router.router` (APIRouter, tag `auth`); `POST /auth` → 201 `UserResponse`.
  - `main.create_app` sets `app.state.password_hasher = PasswordHasher()` and includes `auth.router.router`.
  - Test fixture `api_client` in `tests/conftest.py`: params `["orm", "sql"]`, builds `create_app(IsolatedSettings(db_backend=..., database_url=SecretStr(migrated_database_url)))`, then sets `app.state.password_hasher = PasswordHasher(argon2.PasswordHasher.from_parameters(argon2.profiles.CHEAPEST))` (fast hashing, tests only), yields `TestClient(app)` inside `with`, and calls `truncate_tables(migrated_database_url)` afterwards.
  - `tests/support/auth.py`: `register(client: TestClient, login: str = "mila", password: str = "correct-horse-1") -> httpx.Response` (sends `repeat_password` = `password`).

- [ ] **Step 1: Write failing unit tests** in `tests/auth/test_passwords.py` (`pytestmark = pytest.mark.anyio`):
  - `test_hash_is_salted_argon2id`: two `hash("correct-horse-1")` results differ, both start with `"$argon2id$"`, neither contains the password.
  - `test_verify_accepts_right_and_rejects_wrong_password`: `verify(h, "correct-horse-1") is True`, `verify(h, "wrong-horse-1") is False`.
  - `test_verify_returns_false_for_invalid_hash`: `verify("not-a-hash", "x") is False`.
- [ ] **Step 2: Write failing API tests** in `tests/auth/test_register_api.py` (all use `api_client`, so each runs for `orm` and `sql`):
  - `test_register_returns_201_with_public_fields` (AC1): status 201; `set(body) == {"id", "login", "created_at"}`; `body["login"] == "mila"`; `"correct-horse-1" not in r.text`; `"argon2" not in r.text`.
  - `test_register_stores_argon2_hash` (AC2): read `password_hash` with `psycopg.connect(migrated_database_url)`; starts with `"$argon2id$"`, `!= "correct-horse-1"`, and `argon2.PasswordHasher().verify(stored, "correct-horse-1")` is True.
  - `test_register_duplicate_login_is_409` (AC3): second register → 409, `{"detail": "Login 'mila' is already taken"}`.
  - `test_register_password_mismatch_is_422_and_creates_nothing` (AC4): 422; `"Passwords do not match"` in `r.text`; `users` table empty.
  - `test_register_rejects_bad_login` (AC5), parametrized over `"ab"`, `"a" * 33`, `"mi la"`, `"mila "`, `"мила"`, `"mila!"` → 422 (covers Review Focus 2).
  - `test_register_rejects_bad_password_without_echoing_it` (AC6), parametrized over `"short1!"` (7 chars) and `"x" * 129` → 422 and the password string `not in r.text`.
  - `test_register_password_equal_to_login_is_422` (AC7): login `"mila_long"`, password `"mila_long"` → 422.
  - `test_register_missing_field_or_not_json_is_422` (AC8): body without `repeat_password` → 422; `content="not json"` with JSON content type → 422.
  - `test_register_wrong_types_is_422` (Review Focus 4): `"password": 12345678` → 422; extra field `"admin": true` with a valid body → 201.
- [ ] **Step 3: Write the failing error-handler test** in `tests/core/test_error_handlers.py`: add a `POST /echo-secret` route to `error_client` taking a pydantic body `{"value": Annotated[str, Field(min_length=10)]}`; `test_validation_error_does_not_echo_input`: posting `{"value": "s3cr3t"}` → 422, `"s3cr3t" not in r.text`, `r.json()["detail"][0]["loc"] == ["body", "value"]`. `test_validation_error_unchanged` must keep passing.
- [ ] **Step 4: Run** `poetry run pytest tests/auth tests/core/test_error_handlers.py -v` — expect import errors / failures for the new tests only.
- [ ] **Step 5: Implement** the interfaces above. 422 handler in `core/error_handlers.py`: `register_error_handlers` adds a `RequestValidationError` handler returning 422 `{"detail": [ {k: v for k, v in e.items() if k not in ("input", "ctx")} for e in exc.errors() ]}` (pass through `jsonable_encoder`). Route: `async def register_user(data: RegisterRequest, uow: Annotated[UnitOfWork, Depends(get_uow)], hasher: Annotated[PasswordHasher, Depends(get_password_hasher)]) -> UserResponse` with `status_code=201`.
- [ ] **Step 6: README** — new section `## Auth` after `## Database`: what `POST /auth` takes and returns, the login and password rules, that passwords are stored as Argon2id hashes (salt inside the hash string), and a `### Known limitations and future improvements` list: brute-force protection on `/login` (important; sketch from the spec), `DELETE /users/me` (after epic 4). Add `auth/` to `## Layout`.
- [ ] **Step 7: Run** `poetry run pytest -v` (full suite) + ruff + format + pyright — all green.
- [ ] **Step 8: Commit**
  ```bash
  git add -A src tests README.md pyproject.toml poetry.lock
  git commit -m "Register users with POST /auth" -m "Login and password are validated with pydantic; the password is stored as an Argon2id hash. Validation errors no longer echo the submitted values back."
  ```

---

### Task 2: Log in with `POST /login` and get a 1-hour JWT

Covers AC 9, 10 (without `ver`), 11, 12, 31, 32; Review Focus 1.

**Files:**
- Modify: `pyproject.toml`, `poetry.lock` (`poetry add "pyjwt>=2.10,<3"` — check latest, pin `>=latest,<3`)
- Modify: `src/project_hub/core/config.py`, `auth/schemas.py`, `auth/service.py`, `auth/router.py`, `auth/dependencies.py`, `users/service.py`, `main.py`, `.env.example`, `docker-compose.yml`, `README.md`
- Create: `src/project_hub/auth/tokens.py`
- Tests: modify `tests/test_config.py` (add tests), `tests/conftest.py` (`api_client` gets a secret), `tests/support/auth.py`; create `tests/auth/test_tokens.py`, `tests/auth/test_login_api.py`

**Interfaces:**
- Consumes: Task 1's `PasswordHasher`, `get_password_hasher`, `Login`, `api_client`.
- Produces:
  - `Settings.jwt_secret: SecretStr | None = None` (env `APP_JWT_SECRET`); `field_validator(mode="before")` turns `""` into `None`; a set value with `len < 32` raises `ValueError("jwt_secret must be at least 32 characters")`.
  - `auth.tokens.TOKEN_TTL = timedelta(hours=1)`; `ALGORITHM = "HS256"`.
  - `auth.tokens.TokenService(secret: str, *, clock: Callable[[], datetime] = <utc now>)`; `issue(user_id: UUID) -> str` with claims `sub=str(user_id)`, `iat=int(now)`, `exp=iat+3600`. (Task 4 adds `token_version`.)
  - `auth.dependencies.get_token_service(request: Request) -> TokenService` — raises `RuntimeError("APP_JWT_SECRET is not set")` when `request.app.state.token_service is None` (→ existing 500 handler logs it).
  - `main.create_app` sets `app.state.token_service = TokenService(secret) if settings.jwt_secret else None`.
  - `auth.schemas.LoginRequest(login: Annotated[str, StringConstraints(min_length=1, max_length=32)], password: Annotated[SecretStr, Field(min_length=1, max_length=128)])` — no login regex here, so any wrong credentials are a 401, not a 422.
  - `auth.schemas.TokenResponse(access_token: str, token_type: Literal["bearer"] = "bearer", expires_in: int = 3600)`.
  - `users.service.get_user_by_login(uow, login: str) -> User | None`.
  - `auth.service.login(uow, hasher, tokens: TokenService, data: LoginRequest) -> TokenResponse` — raises `AuthenticationError("Invalid login or password")` for an unknown login or a wrong password. Unknown login still runs `hasher.verify(_DUMMY_HASH, password)` where `_DUMMY_HASH` is computed once at import with the default Argon2 parameters.
  - `POST /login` → 200 `TokenResponse`.
  - Tests: `tests/conftest.py` constant `TEST_JWT_SECRET = "test-only-secret-" + "0" * 32` passed as `jwt_secret` in `api_client`; `tests/support/auth.py` adds `login(client, login="mila", password="correct-horse-1") -> str` (returns the token, asserts 200) and `bearer(token: str) -> dict[str, str]`.

- [ ] **Step 1: Failing settings tests** in `tests/test_config.py`: `test_jwt_secret_defaults_to_none`; `test_empty_jwt_secret_means_not_set` (`APP_JWT_SECRET=""` → `None`); `test_short_jwt_secret_is_rejected` (31 chars → `ValidationError`); `test_jwt_secret_is_secret` (32+ chars value not in `repr(s)` / `str(s)`, `get_secret_value()` round-trips). Add `"APP_JWT_SECRET"` to the `_clean_env` key list in `tests/conftest.py`.
- [ ] **Step 2: Failing token unit test** in `tests/auth/test_tokens.py`: `test_issue_sets_sub_iat_and_exp_one_hour_later` — fixed clock `datetime(2026, 11, 13, 12, 0, tzinfo=UTC)`; decode with `jwt.decode(token, SECRET, algorithms=["HS256"], options={"verify_exp": False})`; `claims["sub"] == str(user_id)`, `claims["iat"] == int(fixed.timestamp())`, `claims["exp"] - claims["iat"] == 3600`; header `alg == "HS256"`.
- [ ] **Step 3: Failing API tests** in `tests/auth/test_login_api.py` (`api_client`):
  - `test_login_returns_bearer_token` (AC9): 200, `token_type == "bearer"`, `expires_in == 3600`, `access_token` non-empty.
  - `test_login_token_lasts_exactly_one_hour_and_names_the_user` (AC10): decode the returned token with `TEST_JWT_SECRET`; `exp - iat == 3600`; `sub` equals the id returned by `/auth`.
  - `test_wrong_password_and_unknown_login_look_the_same` (AC11): both 401, both bodies `== {"detail": "Invalid login or password"}`, both `www-authenticate == "Bearer"`.
  - `test_login_missing_field_is_422` (AC12).
  - `test_password_is_checked_exactly_as_typed` (Review Focus 1): register with `"  пароль 123 "`; login with it → 200; with `"пароль 123"` → 401.
  - `test_login_without_jwt_secret_is_500` (AC32): app from `IsolatedSettings(database_url=..., db_backend=...)` without secret; `TestClient(app, raise_server_exceptions=False)`; `/health` → 200; `/login` → 500 `{"detail": "Internal Server Error"}`. (Register a user first through the same client so the failure is the secret, not the credentials.)
- [ ] **Step 4: Run** the new tests — they fail.
- [ ] **Step 5: Implement** the interfaces above.
- [ ] **Step 6: Config and docs.** `.env.example`: commented `# APP_JWT_SECRET=` with a line explaining it is required for login, at least 32 characters, never committed, generated with `python -c "import secrets; print(secrets.token_urlsafe(32))"`. `docker-compose.yml` `api.environment`: `APP_JWT_SECRET: ${APP_JWT_SECRET:-}`. README `## Auth`: `POST /login`, the 1-hour token, `APP_JWT_SECRET` (how to generate, what happens without it).
- [ ] **Step 7: Run** full `pytest`, ruff, format, pyright; and `docker compose config --format json | python -c "import json,sys; print(json.load(sys.stdin)['services']['api']['environment'].get('APP_JWT_SECRET', 'MISSING'))"` → prints an empty line (not `MISSING`).
- [ ] **Step 8: Commit**
  ```bash
  git commit -m "Log in with POST /login and get a 1-hour JWT" -m "Tokens are HS256-signed with APP_JWT_SECRET (min 32 chars, never committed). Unknown login and wrong password give the same 401 and take the same time."
  ```

---

### Task 3: See yourself with `GET /users/me` (current-user dependency)

Covers AC 13, 14, 15, 16, 17 (without `ver`), 18; Review Focus 3.

**Files:**
- Modify: `auth/tokens.py`, `auth/dependencies.py`, `users/service.py`, `main.py`, `README.md`
- Create: `src/project_hub/users/router.py`
- Tests: modify `tests/auth/test_tokens.py`; create `tests/users/test_me_api.py`

**Interfaces:**
- Consumes: `TokenService.issue`, `get_token_service`, `UserResponse`, test helpers `register`, `login`, `bearer`.
- Produces:
  - `auth.tokens.TokenClaims(user_id: UUID)` (frozen dataclass; Task 4 adds `token_version: int`).
  - `TokenService.decode(token: str) -> TokenClaims` — `jwt.decode(token, secret, algorithms=["HS256"], options={"require": ["exp", "iat", "sub"]})`; any `jwt.InvalidTokenError`, or a `sub` that is not a UUID string → `AuthenticationError("Invalid or expired token")`.
  - `users.service.get_user(uow, user_id: UUID) -> User | None`.
  - `auth.dependencies.bearer_scheme = HTTPBearer(auto_error=False)`.
  - `auth.dependencies.get_current_user(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)], uow: Annotated[UnitOfWork, Depends(get_uow)], tokens: Annotated[TokenService, Depends(get_token_service)]) -> User` — no credentials → `AuthenticationError("Not authenticated")`; decode failure or unknown user → `AuthenticationError("Invalid or expired token")`.
  - `auth.dependencies.CurrentUser = Annotated[User, Depends(get_current_user)]` — what epic 4 imports.
  - `users.router.router` (tag `users`), `GET /users/me` → `UserResponse`; included in `create_app`.

- [ ] **Step 1: Failing token unit tests** in `tests/auth/test_tokens.py` (fixed secret `S = "a" * 32`):
  - `test_decode_returns_claims_of_issued_token`.
  - `test_decode_rejects_expired_token`: issued with clock `now - 3600 s` → `AuthenticationError`.
  - `test_decode_accepts_token_just_before_expiry`: clock `now - 3590 s` → decodes.
  - `test_decode_rejects_tampering`, parametrized: token signed with `"b" * 32`; `jwt.encode(claims, S, algorithm="HS512")`; an unsigned `alg: none` token built by hand (`base64url(header).base64url(payload).`); a valid token whose payload segment is replaced with one carrying another `sub`; the string `"garbage"` → all `AuthenticationError`.
  - `test_decode_requires_claims`, parametrized: payload without `exp`; without `iat`; without `sub`; `sub="not-a-uuid"` → `AuthenticationError`.
- [ ] **Step 2: Failing API tests** in `tests/users/test_me_api.py` (`api_client`):
  - `test_me_returns_current_user` (AC13): register, login, `GET /users/me` with `bearer(token)` → 200, body equals the `/auth` response, `"password" not in r.text`.
  - `test_token_expiry_boundary` (AC14): with a test `TokenService(TEST_JWT_SECRET, clock=...)` issue tokens for the registered id dated `now - 3590 s` → 200, `now - 3600 s` → 401.
  - `test_missing_or_malformed_auth_is_401` (AC15), parametrized headers: none; `{"Authorization": "Basic bWlsYTp4"}`; `{"Authorization": "Bearer"}`; `{"Authorization": "Bearer garbage"}` → 401 and `www-authenticate == "Bearer"`.
  - `test_forged_tokens_are_401` (AC16): token signed with another 32-char secret; `alg: none` token → 401.
  - `test_token_without_required_claims_is_401` (AC17): correctly signed with `TEST_JWT_SECRET` but no `exp` / no `sub` / `sub="nope"` → 401.
  - `test_token_for_missing_user_is_401` (AC18): `issue(uuid4())` → 401.
  - `test_lowercase_bearer_scheme_works` (Review Focus 3): `{"Authorization": f"bearer {token}"}` → 200.
- [ ] **Step 3: Run** — new tests fail.
- [ ] **Step 4: Implement** the interfaces above.
- [ ] **Step 5: README** `## Auth`: `GET /users/me`, how to use the Swagger "Authorize" button (paste the `access_token`), and `CurrentUser` for later routes. Add `users/router.py`, `users/service.py`, `users/schemas.py` to `## Layout`.
- [ ] **Step 6: Run** full suite + ruff + format + pyright.
- [ ] **Step 7: Commit**
  ```bash
  git commit -m "See who you are with GET /users/me" -m "Adds the CurrentUser dependency: a Bearer JWT is checked (signature, HS256 only, expiry, required claims) and the user loaded; anything else is a 401."
  ```

---

### Task 4: Log out with `POST /logout` (token version)

Covers AC 10 (`ver`), 17 (`ver`), 19, 20, 21, 26, 27 (`increment_token_version`), 28, 29; Review Focus 5.

**Files:**
- Create: `src/project_hub/db/migrations/versions/0002_add_users_token_version.py`
- Modify: `users/entities.py`, `users/models.py`, `users/repository.py`, `users/repository_orm.py`, `users/repository_sql.py`, `users/service.py`, `auth/tokens.py`, `auth/dependencies.py`, `auth/service.py`, `auth/router.py`, `README.md`
- Tests: modify `tests/users/test_repository_contract.py` (add tests), `tests/db/test_migrations.py` (**two existing expectations change — see Step 1**), `tests/auth/test_tokens.py`, `tests/auth/test_login_api.py`, `tests/users/test_me_api.py`; create `tests/auth/test_logout_api.py`

**Interfaces:**
- Produces:
  - `User.token_version: int` (last field). `UserModel.token_version: Mapped[int]` (`Integer`, `nullable=False`, `server_default=text("0")`).
  - Migration `0002` (`down_revision = "0001"`): `op.add_column("users", sa.Column("token_version", sa.Integer(), server_default=sa.text("0"), nullable=False))`; downgrade `op.drop_column("users", "token_version")`.
  - `UserRepository.increment_token_version(user_id: UUID) -> User | None`.
    - SQL: one statement `UPDATE users SET token_version = token_version + 1 WHERE id = %s RETURNING id, login, password_hash, created_at, token_version`. All existing `SELECT … RETURNING` column lists gain `token_version`.
    - ORM: `update(UserModel).where(UserModel.id == user_id).values(token_version=UserModel.token_version + 1).returning(UserModel).execution_options(populate_existing=True)` — so a user loaded earlier in the same session gets the fresh value.
  - `users.service.revoke_tokens(uow, user_id: UUID) -> User | None`.
  - `TokenService.issue(user_id: UUID, token_version: int) -> str` adds claim `ver`; `decode` requires `ver` too and rejects a non-`int` `ver` (`bool` counts as invalid); `TokenClaims.token_version: int`.
  - `get_current_user` also raises `AuthenticationError("Invalid or expired token")` when `claims.token_version != user.token_version`.
  - `auth.service.login` now calls `tokens.issue(user.id, user.token_version)`.
  - `auth.service.logout(uow, user: User) -> None` — `revoke_tokens`, commit.
  - `POST /logout` (`CurrentUser`) → 204, no body.

- [ ] **Step 1: Migration tests** in `tests/db/test_migrations.py`. **These change two existing expectations because the schema really changes — confirmed with the user before execution:** `test_upgrade_creates_users_table` gains `("token_version", "integer", "NO")` in the column set; `test_upgrade_twice_is_noop` expects `[("0002",)]`. New tests:
  - `test_token_version_defaults_to_zero_for_existing_rows`: `upgrade(url, "0001")`, insert a user with psycopg, `upgrade(url)`, the row's `token_version == 0`.
  - `test_downgrade_to_0001_drops_token_version`: `upgrade(url)`, `downgrade(url, "0001")`, column absent, `users` still exists.
  - `test_orm_metadata_matches_migrated_schema` stays as is and must pass.
- [ ] **Step 2: Contract tests** in `tests/users/test_repository_contract.py`:
  - `test_new_user_has_token_version_zero` (AC26) — from `add`, `get_by_id`, `get_by_login`.
  - `test_increment_token_version_returns_updated_user` (AC27): returns the user with `token_version == 1`; again → 2.
  - `test_increment_token_version_unknown_id_returns_none` (AC27).
  - `test_increment_token_version_is_fresh_after_earlier_read`: in one UoW `get_by_id` then `increment_token_version` → returned `token_version == 1`, and `get_by_id` again → 1.
  - `test_increment_token_version_needs_commit` (AC28): without commit a new UoW still sees 0; with commit sees 1.
- [ ] **Step 3: Token tests**: `ver` round-trips through `issue`/`decode`; missing `ver`, `ver="0"` and `ver=True` → `AuthenticationError`. Update existing `issue(...)` calls in tests to pass `token_version=0`. Login API test (AC10) also asserts `claims["ver"] == 0`.
- [ ] **Step 4: Logout API tests** in `tests/auth/test_logout_api.py` (`api_client`):
  - `test_logout_revokes_token` (AC19): logout → 204 and `r.content == b""`; same token on `/users/me` → 401.
  - `test_logout_revokes_every_token_of_the_user` (AC20): two logins → two tokens; logout with the first; both → 401; a third login → its token gives 200.
  - `test_logout_without_valid_token_is_401` (AC21): no header; garbage token.
  - `test_logout_twice_is_401_not_500` (Review Focus 5).
  - In `tests/users/test_me_api.py`: `test_token_with_stale_version_is_401` — issue a token with `token_version=5` for a real user (version 0) → 401.
- [ ] **Step 5: Run** — new tests fail (migration tests fail on the missing column).
- [ ] **Step 6: Implement** the interfaces above.
- [ ] **Step 7: README** `## Auth`: `POST /logout` ends every session of the user (how `token_version` works, in two sentences). `## Database`: migration `0002` adds `users.token_version`.
- [ ] **Step 8: Run** full suite (both backends) + ruff + format + pyright.
- [ ] **Step 9: Commit**
  ```bash
  git commit -m "Log out with POST /logout" -m "A token_version column (migration 0002, both backends) is carried in the token as 'ver'; logout increments it, so every older token of the user is refused."
  ```

---

### Task 5: Change your password with `PUT /users/me/password`

Covers AC 22, 23, 24, 25, 27 (`update_password`), 28.

**Files:**
- Modify: `users/repository.py`, `users/repository_orm.py`, `users/repository_sql.py`, `users/service.py`, `users/router.py`, `auth/schemas.py`, `auth/service.py`, `README.md`
- Tests: modify `tests/users/test_repository_contract.py`; create `tests/users/test_change_password_api.py`

**Interfaces:**
- Produces:
  - `UserRepository.update_password(user_id: UUID, password_hash: str) -> User | None` — one atomic statement that sets the hash **and** `token_version = token_version + 1` (SQL: `UPDATE … RETURNING`; ORM: same pattern as `increment_token_version`, with `populate_existing`).
  - `users.service.set_password(uow, user_id: UUID, password_hash: str) -> User | None`.
  - `auth.schemas.ChangePasswordRequest(current_password: Annotated[SecretStr, Field(min_length=1, max_length=128)], new_password: Password, repeat_new_password: SecretStr)`; validator: repeat mismatch → `ValueError("Passwords do not match")`; new equals current → `ValueError("New password must differ from the current one")`.
  - "New password must not equal the login" cannot be a pydantic check (the login is not in the body), so it lives in the service. New domain error `core.exceptions.ValidationFailedError(DomainError)` — "input is well-formed but breaks a business rule" — mapped to 422 in `core/error_handlers.py` `_STATUS_BY_ERROR`. Its body is `{"detail": "<message>"}` (a string, unlike pydantic's list); README notes both 422 shapes.
  - `auth.service.change_password(uow, hasher, tokens, user: User, data: ChangePasswordRequest) -> TokenResponse` — wrong current password → `DomainError("Current password is incorrect")` (400); new password equals the login → `ValidationFailedError("Password must not equal the login")` (422); otherwise hash, `set_password`, commit, return a token with the new version.
  - `PUT /users/me/password` (`CurrentUser`) → 200 `TokenResponse`.

- [ ] **Step 1: Contract tests**: `test_update_password_sets_hash_and_increments_version` (AC27), `test_update_password_unknown_id_returns_none` (AC27), `test_update_password_needs_commit` (AC28), `test_update_password_is_fresh_after_earlier_read`.
- [ ] **Step 2: API tests** in `tests/users/test_change_password_api.py` (`api_client`):
  - `test_change_password_rotates_token_and_password` (AC22): 200 with a new token that works on `/users/me`; old token → 401; `/login` with new password → 200, with old → 401.
  - `test_wrong_current_password_is_400_and_changes_nothing` (AC23): 400 `{"detail": "Current password is incorrect"}`; old token still 200; old password still logs in.
  - `test_change_password_invalid_input_is_422` (AC24), parametrized: repeat mismatch; new == current; new == login; new of 7 chars; new of 129 chars → 422, and the submitted new password `not in r.text`.
  - `test_change_password_without_valid_token_is_401` (AC25).
  - In `tests/core/test_error_handlers.py`: `ValidationFailedError` → 422 (add `"validation"` to the parametrized mapping test's route dict and cases).
- [ ] **Step 3: Run** — new tests fail.
- [ ] **Step 4: Implement.**
- [ ] **Step 5: README** `## Auth`: `PUT /users/me/password` (returns a fresh token; all other sessions end).
- [ ] **Step 6: Run** full suite + ruff + format + pyright.
- [ ] **Step 7: Commit**
  ```bash
  git commit -m "Change your password with PUT /users/me/password" -m "Checks the current password, stores the new hash and bumps token_version in one statement (both backends), so every older token stops working; returns a fresh token."
  ```

---

### Task 6: Security events are logged without secrets

Covers AC 33.

**Files:**
- Modify: `src/project_hub/auth/service.py`, `README.md`
- Create: `tests/auth/test_security_log.py`

**Interfaces:**
- Produces: module logger `logging.getLogger("project_hub.auth.service")`; `INFO` records with messages exactly `"user registered"`, `"login succeeded"`, `"login failed"`, `"logout"`, `"password changed"`, each with `extra={"login": ..., "user_id": ...}` (`user_id` omitted when unknown, e.g. failed login for an unknown login).

- [ ] **Step 1: Failing test** `test_security_events_are_logged_without_secrets` (`api_client`, `caplog.at_level(logging.INFO, logger="project_hub.auth.service")`): register → wrong-password login → login → change password → logout; the `project_hub.auth.service` records' messages are exactly `["user registered", "login failed", "login succeeded", "password changed", "logout"]`; for every record, `record.getMessage()` and `str(record.__dict__)` contain neither password, nor `"$argon2"`, nor any issued token.
- [ ] **Step 2: Run** — fails.
- [ ] **Step 3: Implement** the log calls in `auth/service.py`.
- [ ] **Step 4: README** `## Auth`: one line listing the logged events and that secrets never appear.
- [ ] **Step 5: Run** full suite + ruff + format + pyright.
- [ ] **Step 6: Commit**
  ```bash
  git commit -m "Log sign-ups, logins, logouts and password changes" -m "INFO records from project_hub.auth.service with the login and user id, never a password, hash or token, to help investigate attacks."
  ```

---

## After the tasks (Phase 5, not pytest)

- AC34: `poetry check --lock` → `All set!`; `poetry show argon2-cffi pyjwt` lists both.
- AC35: `docker compose config` → `api.environment.APP_JWT_SECRET` present.
- AC36: `APP_JWT_SECRET=$(python -c 'import secrets;print(secrets.token_urlsafe(32))') docker compose up -d --build --wait`, then with `curl`: `POST /auth` 201 → `POST /login` 200 → `GET /users/me` 200 → `POST /logout` 204 → same token `GET /users/me` 401 → no token 401; `docker compose down`.
- AC37: `ruff check`, `ruff format --check`, `pyright`, `pytest` (both backends; `python -m tests.support.backend_coverage` on a `pytest -v` log) green locally, then CI green on the PR.
