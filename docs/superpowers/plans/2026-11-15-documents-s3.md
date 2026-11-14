# Documents and S3 (Epic 6) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Owner and participants upload (`POST /project/{id}/documents`), list (`GET /project/{id}/documents`), download (`GET /document/{id}`), replace (`PUT /document/{id}`) and delete (`DELETE /document/{id}`) pdf/docx documents stored in S3; `GET /projects` shows them; `DELETE /project/{id}` removes them and their files.

**Architecture:** A small `storage/` package (`FileStorage` Protocol, boto3 `S3FileStorage` running calls in a worker thread) and a `documents/` feature package shaped like `projects/` (entities, `DocumentRepository` Protocol with SQLAlchemy and psycopg implementations on both Units of Work, validation, service, router). Upload routes check token and project access in dependencies **before** reading the multipart body themselves. moto server stands in for S3 in compose, tests and CI.

**Tech Stack:** FastAPI, Starlette multipart (`python-multipart`), boto3 + `boto3-stubs[s3]`, SQLAlchemy 2 async + psycopg 3, Alembic, pytest + anyio, moto server 5.2.5, Poetry, ruff, pyright strict.

**Spec:** [`docs/superpowers/specs/2026-11-15-documents-s3-design.md`](../specs/2026-11-15-documents-s3-design.md). "AC n" below = its acceptance criterion n. Read the spec section a task names before starting it.

## Global Constraints

- Endpoint names verbatim: `GET|POST /project/{project_id}/documents`, `GET|PUT|DELETE /document/{document_id}`; ids are `UUID` path parameters.
- Every route takes `user: CurrentUser` (`project_hub.auth.dependencies`).
- Project no access / unknown → `NotFoundError("Project not found")`; document no access / unknown → `NotFoundError("Document not found")`. Both via `project_hub.projects.service.get_project`.
- Errors: `ValidationFailedError` 422, `PayloadTooLargeError` 413 (new), `StorageUnavailableError` 503 `{"detail": "File storage is unavailable"}` (new), all `{"detail": str}`.
- Content types exactly: `application/pdf`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`.
- S3 key exactly `projects/{project_id}/documents/{uuid4().hex or str(uuid4())}` — new random part per stored file, never the file name.
- Settings (`core/config.py`): `s3_bucket: str | None = None`, `s3_endpoint_url: str | None = None`, `s3_region: str = "eu-west-1"`, `document_max_bytes: int = 10_485_760` (1…104_857_600), `document_max_files: int = 10` (1…100); blank `s3_bucket`/`s3_endpoint_url` → `None`.
- Constraint, index and column names exactly as in the spec "Database — migration `0004`".
- Every repository change in BOTH `Orm…` and `Sql…` implementations, proven by `tests/documents/test_repository_contract.py` (fixture `database`; file name must end in `_contract.py`).
- SQL backend: explicit `SAVEPOINT`/`ROLLBACK TO SAVEPOINT` around writes that can fail (pattern in `projects/repository_sql.py` `add`); all SQL parameterized. ORM `UPDATE … RETURNING` with `populate_existing=True`.
- Services commit (`await uow.commit()`); `get_uow` never commits.
- boto3 calls only through `asyncio.to_thread`; when `s3_endpoint_url` is set the botocore `Config` has `s3={"addressing_style": "path"}`.
- Tests never use real AWS credentials: `AWS_ACCESS_KEY_ID=AWS_SECRET_ACCESS_KEY=test`, `AWS_SHARED_CREDENTIALS_FILE`/`AWS_CONFIG_FILE` → an empty file, `AWS_PROFILE`/`AWS_SESSION_TOKEN` unset, for the whole session. No real keys in compose, CI or `.env.example`.
- Ports bound to `127.0.0.1` only; moto host port `${APP_S3_PORT:-55435}`.
- Comments (`CLAUDE.md` "Comments"): none by default; one only for a hidden reason that makes code unsafe to change. Never delete an existing comment or docstring. Check every diff for new `#` and `"""` lines before committing.
- Tests prove behaviour (`CLAUDE.md` "What to test"): no tests re-reading config files, no tests of `tests/support/` helpers, S3 against moto, no mocks of S3. Never weaken or delete an existing test; the only existing tests allowed to change: `test_upgrade_twice_is_noop` (head → `0004`), `test_orm_metadata_matches_migrated_schema` (import `DocumentModel`), `test_compose_stack_serves_health` (running set gains `s3`, env gains `APP_S3_PORT=0`), and `test_compose_stack_migrates_database` (env gains `APP_S3_PORT=0`).
- Commits (`CLAUDE.md` "Commits"): one slice per commit (code + tests + settings + compose + migration + README lines), plain-words subject, 1–3 line body. **No `Co-Authored-By` trailer.**
- Before each commit: `poetry run ruff check`, `poetry run ruff format --check`, `poetry run pyright`, `poetry run pytest` with `docker compose up -d --wait db s3` and `TEST_DATABASE_URL=postgresql://project_hub:project_hub@localhost:55433/postgres` (this worktree's db is on 55433). Tasks that touch compose or the smoke test also run `poetry run pytest -m docker`.
- Implementation agent: `python-development:python-development-fastapi-pro`.

## Review Focus

1. Upper-case extension `THESIS.PDF` is accepted and the name is stored as sent. → Task 2 `test_upper_case_extension_accepted`.
2. A valid pdf named `.docx` (and a valid docx named `.pdf`) is refused with 422, not stored as the wrong type. → Task 2 `test_content_must_match_extension`.
3. The same bytes twice in one request become two documents with two different S3 keys. → Task 2 `test_same_file_twice_in_one_request`.
4. A name with quotes, a semicolon or non-ASCII (`a"b;c.pdf`, `диплом.pdf`) gives a well-formed `Content-Disposition` that round-trips the name. → Task 4 `test_download_header_survives_odd_names`.
5. A `POST` that uses the field name `file` instead of `files` gets 422 `No files were sent`, not a silent empty 201. → Task 2 `test_wrong_field_name_is_422`.

---

## File map

```
src/project_hub/
  core/config.py                 + s3_*, document_* settings                                  (T1, T2)
  core/exceptions.py             + PayloadTooLargeError, ServiceUnavailableError               (T1, T2)
  core/error_handlers.py         + 413, 503 in _STATUS_BY_ERROR                                (T1, T2)
  storage/files.py               FileStorage, StorageUnavailableError, discard_quietly         (T1)
  storage/s3.py                  create_s3_client, S3FileStorage, create_s3_storage            (T1)
  storage/create_bucket.py       ensure_bucket, main                                           (T1)
  storage/dependencies.py        get_storage, Storage                                          (T1)
  documents/entities.py          DocumentType, NewDocument, Document, ReplacedFile, new_storage_key (T2, T5)
  documents/validation.py        ValidFile, clean_file_name, detect_type, read_valid_file      (T2)
  documents/forms.py             read_uploads                                                  (T2, T5)
  documents/repository.py        DocumentRepository                                            (T2–T8)
  documents/models.py            DocumentModel                                                 (T2)
  documents/repository_orm.py, documents/repository_sql.py                                     (T2–T8)
  documents/schemas.py           UploaderResponse, DocumentResponse                            (T2)
  documents/dependencies.py      AccessibleProject, AccessibleDocument                         (T2, T4)
  documents/service.py           upload/list/download/replace/delete/documents_by_project      (T2–T7)
  documents/router.py            five routes                                                   (T2–T6)
  documents/upload_limit.py      UploadLimitMiddleware                                         (T9)
  projects/repository*.py        + touch                                                       (T2)
  projects/schemas.py            ProjectListItem.documents: list[DocumentResponse]            (T7)
  projects/router.py, service.py GET /projects documents (T7), delete_project + storage (T8)
  db/uow.py, db/orm.py, db/sql.py  documents repository on both UoWs                          (T2)
  db/migrations/versions/0004_create_documents.py                                              (T2)
  main.py                        app.state.storage, app.state.settings, router, middleware     (T1, T2, T9)
tests/
  conftest.py                    s3 fixtures, AWS env isolation, api_client with storage       (T1)
  support/storage.py             s3 test client helpers (bucket_keys, empty_bucket)            (T1)
  support/documents.py           pdf_bytes, docx_bytes, upload, broken_storage                 (T2)
  storage/test_s3_storage.py, storage/test_create_bucket.py                                    (T1)
  documents/test_*_api.py, documents/test_repository_contract.py, documents/test_documents_log.py
docker-compose.yml, .env.example, .github/workflows/ci.yml, README.md, docs/PRDs/roadmap.md
```

---

### Task 1: Store files in S3 through a small storage interface (moto locally and in CI)

Spec: "Settings", "Storage", "Local infrastructure", "Tests and fixtures". AC 41, 42, 43, 47 (S3 part), 48 (stack comes up with `s3`).

**Files:**
- Create: `src/project_hub/storage/__init__.py`, `storage/files.py`, `storage/s3.py`, `storage/create_bucket.py`, `storage/dependencies.py`, `tests/storage/__init__.py`, `tests/storage/test_s3_storage.py`, `tests/storage/test_create_bucket.py`, `tests/support/storage.py`
- Modify: `pyproject.toml` + `poetry.lock` (`poetry add "boto3 (>=1.44,<2)"`, `poetry add --group dev "boto3-stubs[s3] (>=1.44,<2)"`), `core/config.py`, `core/exceptions.py`, `core/error_handlers.py`, `main.py`, `tests/conftest.py`, `tests/test_config.py`, `tests/test_main.py`, `tests/test_docker_smoke.py` (allowed changes only), `docker-compose.yml`, `.env.example`, `.github/workflows/ci.yml`, `README.md`, `docs/PRDs/roadmap.md` (AWS cost strategy note: "S3 emulated with moto server locally; LocalStack needs an auth token since 2026.03; 7a/7b re-check Lambda emulation")

**Interfaces:**
- Produces:
  - `core.exceptions.ServiceUnavailableError(DomainError)` → 503.
  - `storage.files.StorageUnavailableError(ServiceUnavailableError)`; `StorageUnavailableError()` takes no argument, message `"File storage is unavailable"`.
  - `storage.files.FileStorage(Protocol)`: `async put(key: str, data: bytes, content_type: str) -> None`, `async get(key: str) -> bytes`, `async delete(keys: Sequence[str]) -> None`.
  - `storage.files.discard_quietly(storage: FileStorage, keys: Sequence[str], *, project_id: UUID) -> Awaitable[None]`: calls `delete`, on `StorageUnavailableError` logs WARNING `document files left in storage` (logger `project_hub.storage.files`, `extra={"event": "document files left in storage", "project_id": …, "keys": list(keys)}`) and returns.
  - `storage.s3.create_s3_client(settings: Settings) -> S3Client`; `S3FileStorage(client: S3Client, bucket: str)`; `create_s3_storage(settings: Settings) -> S3FileStorage | None` (`None` when `s3_bucket` is `None`).
  - `storage.create_bucket.ensure_bucket(client: S3Client, bucket: str, region: str) -> bool` (True = created); `main() -> int` (exit 2 with a message when `APP_S3_BUCKET` is unset); runnable as `python -m project_hub.storage.create_bucket`.
  - `storage.dependencies.get_storage(request: Request) -> FileStorage` (raises `RuntimeError("File storage is not configured: set APP_S3_BUCKET")` when `app.state.storage` is `None`); `Storage = Annotated[FileStorage, Depends(get_storage)]`.
  - `create_app` sets `app.state.storage = create_s3_storage(settings)` and `app.state.settings = settings`; logs WARNING `APP_S3_BUCKET is not set; documents are disabled` when `None`.
  - Test fixtures in `tests/conftest.py`: session `s3_endpoint_url: str` (from `TEST_S3_ENDPOINT_URL`, default `http://localhost:55435`; `pytest.fail` with a clear message if unreachable), session `s3_client` (a boto3 client for assertions), session `storage_bucket: str` (`project-hub-test-<hex>`, created, emptied and deleted at session end); `api_client` passes `s3_bucket`, `s3_endpoint_url` into `IsolatedSettings` and empties the bucket after each test. `_clean_env` also deletes `APP_S3_BUCKET`, `APP_S3_ENDPOINT_URL`, `APP_S3_REGION`, `APP_DOCUMENT_MAX_BYTES`, `APP_DOCUMENT_MAX_FILES`.
  - `tests/support/storage.py`: `bucket_keys(client, bucket) -> list[str]`, `empty_bucket(client, bucket) -> None`.

- [ ] **Step 1: Write the failing storage tests** (`tests/storage/test_s3_storage.py`, real moto, `pytest.mark.anyio`)
  - `test_put_then_get_returns_same_bytes`: put `b"%PDF-1.4 x"` under `projects/p/documents/k`; `get` returns it; the object's `ContentType` (via `s3_client.head_object`) is the one passed.
  - `test_delete_removes_several_keys`: put 3 keys, delete 2 → `bucket_keys` holds only the third.
  - `test_delete_accepts_empty_list_and_missing_keys`: `delete([])` and `delete(["nope"])` return without error.
  - `test_delete_more_than_1000_keys`: put 1001 tiny objects, delete all → bucket empty (proves chunking).
  - `test_missing_bucket_raises_storage_unavailable`: storage on bucket `project-hub-missing-<hex>`: `put`, `get`, `delete(["k"])` each raise `StorageUnavailableError`.
  - `test_unreachable_endpoint_raises_storage_unavailable`: endpoint `http://127.0.0.1:9` → `put` raises `StorageUnavailableError` (keep the timeout short via settings-built client; the test must finish in < 15 s).
  - `test_get_missing_key_raises_storage_unavailable`.
  - `test_discard_quietly_logs_warning_on_failure` (caplog): missing bucket → no exception, one WARNING `document files left in storage` with `record.keys == ["k"]` and `record.project_id`.
- [ ] **Step 2: Write the failing bucket and settings tests**
  - `tests/storage/test_create_bucket.py`: `test_creates_missing_bucket_then_noop` (first call True and `head_bucket` succeeds, second call False); `test_main_without_bucket_setting_exits_2` (subprocess `python -m project_hub.storage.create_bucket` with `APP_S3_BUCKET` unset → exit code 2); `test_main_creates_configured_bucket` (subprocess with `APP_S3_BUCKET`, `APP_S3_ENDPOINT_URL`, dummy creds → exit 0, bucket exists; delete it after).
  - `tests/test_config.py`: `test_blank_s3_settings_are_unset` (`APP_S3_BUCKET="  "`, `APP_S3_ENDPOINT_URL=""` → both `None`); `test_s3_region_defaults_to_eu_west_1`.
  - `tests/test_main.py`: `test_storage_is_none_without_bucket` (`app.state.storage is None`, warning logged); `test_storage_is_built_with_bucket` (`isinstance(app.state.storage, S3FileStorage)`).
  - `tests/core/test_error_handlers.py`: a route raising `StorageUnavailableError()` answers 503 `{"detail": "File storage is unavailable"}` (follow the existing pattern in that file).
- [ ] **Step 3: Run them, see them fail** — `poetry run pytest tests/storage tests/test_config.py tests/test_main.py tests/core -q` → import errors / failures for the new names.
- [ ] **Step 4: Implement** the Interfaces above. `S3FileStorage` maps every `botocore.exceptions.BotoCoreError` and `ClientError` to `StorageUnavailableError` (`raise … from err`, log at ERROR with the exception). `delete` uses `delete_objects` in chunks of 1000 with `Quiet=True`; any entry in `Errors` → `StorageUnavailableError`. Client `Config(connect_timeout=5, read_timeout=30, retries={"max_attempts": 3, "mode": "standard"}, max_pool_connections=20)` (+ path addressing when an endpoint is set). `ensure_bucket` passes `CreateBucketConfiguration={"LocationConstraint": region}` unless region is `us-east-1`.
- [ ] **Step 5: Compose, env, CI**
  - `docker-compose.yml`: service `s3` (`motoserver/moto:5.2.5`, `ports: ["127.0.0.1:${APP_S3_PORT:-55435}:5000"]`, a healthcheck that works inside that image, e.g. a Python one-liner `urllib.request.urlopen('http://localhost:5000/moto-api/')`); service `storage-init` (`build: .`, `command: ["python", "-m", "project_hub.storage.create_bucket"]`, env `APP_S3_BUCKET`, `APP_S3_ENDPOINT_URL: http://s3:5000`, `APP_S3_REGION`, `AWS_ACCESS_KEY_ID: test`, `AWS_SECRET_ACCESS_KEY: test`, `depends_on: s3: service_healthy`); `api` gets the same S3 env and `depends_on: storage-init: service_completed_successfully`. Add a compose comment that the keys are dummy values for the local emulator.
  - `.env.example`: `APP_S3_BUCKET=project-hub-documents`, commented `APP_S3_ENDPOINT_URL`, `APP_S3_REGION=eu-west-1`, `APP_S3_PORT=55435`, and the `TEST_S3_ENDPOINT_URL` note next to `TEST_DATABASE_URL`; one line "never put real AWS keys here".
  - `.github/workflows/ci.yml` job `checks`: service `s3: image: motoserver/moto:5.2.5, ports: ["5000:5000"]`; job env `TEST_S3_ENDPOINT_URL: http://localhost:5000`, `AWS_ACCESS_KEY_ID: test`, `AWS_SECRET_ACCESS_KEY: test`. Pin nothing else differently.
  - `tests/test_docker_smoke.py`: the two compose tests add `"APP_S3_PORT": "0"` to `env`; `test_compose_stack_serves_health` expects `{"db": "running", "s3": "running", "api": "running"}`.
- [ ] **Step 6: Run** — `docker compose up -d --wait db s3`; full `pytest`, `pytest -m docker`, ruff, pyright → all green. `docker compose config | grep -n "127.0.0.1"` shows the `s3` port on loopback. `poetry check --lock` passes.
- [ ] **Step 7: README** — Docker table rows `s3` (55435, `APP_S3_PORT`) and `storage-init`; a short "File storage" paragraph (moto locally, files in memory and lost when `s3` stops, settings table, dummy credentials, never real keys); the test section mentions `TEST_S3_ENDPOINT_URL`.
- [ ] **Step 8: Commit** — `Store files in S3 through FileStorage, with moto locally and in CI`.

---

### Task 2: Upload pdf and docx documents with POST /project/{id}/documents

Spec: "Database — migration `0004`", "Entities and repository", "File validation", "Reading the body only after access is checked", "Service and access rules" (upload row), "API". AC 1–10, 12, 29 (upload), 32, 32a (POST), 33, 38, 39, 40, 44–46, 47 (limits).

**Files:**
- Create: `db/migrations/versions/0004_create_documents.py`, `documents/__init__.py`, `entities.py`, `validation.py`, `forms.py`, `repository.py`, `models.py`, `repository_orm.py`, `repository_sql.py`, `schemas.py`, `dependencies.py`, `service.py`, `router.py`; `tests/documents/__init__.py`, `test_upload_api.py`, `test_repository_contract.py`, `test_validation.py`, `test_documents_log.py`, `test_documents_auth_api.py`; `tests/support/documents.py`
- Modify: `pyproject.toml`/`poetry.lock` (`poetry add "python-multipart (>=0.0.33,<0.1)"`), `core/config.py`, `core/exceptions.py`, `core/error_handlers.py`, `projects/repository.py`, `projects/repository_orm.py`, `projects/repository_sql.py`, `db/uow.py`, `db/orm.py`, `db/sql.py`, `main.py`, `tests/db/test_migrations.py` (allowed changes + new tests), `tests/projects/test_repository_contract.py` (new `touch` test), `tests/test_config.py`, `README.md`, `docs/PRDs/roadmap.md` (frontend-requests rows: metadata → accepted, download → accepted "through the API", CORS → not needed; "Deferred to implementation" upload row → "decided in 6: through the API")

**Interfaces:**
- Consumes: Task 1 `FileStorage`, `Storage`, `StorageUnavailableError`, `discard_quietly`, `app.state.settings`; epic 4 `projects.service.get_project(uow, user, project_id) -> ProjectAccess`.
- Produces:
  - `core.exceptions.PayloadTooLargeError(DomainError)` → 413.
  - `documents.entities`: `PDF_CONTENT_TYPE`, `DOCX_CONTENT_TYPE` (strings above); `DocumentType(StrEnum)` `PDF="pdf"`, `DOCX="docx"` with properties `extension -> str` (`".pdf"`/`".docx"`) and `content_type -> str`; frozen slotted dataclasses `NewDocument(project_id: UUID, name: str, content_type: str, size: int, storage_key: str, uploaded_by: UUID)`, `Document(id: UUID, project_id: UUID, name: str, content_type: str, size: int, storage_key: str, uploaded_by: UUID | None, uploader_login: str | None, created_at: datetime, updated_at: datetime)`; `new_storage_key(project_id: UUID) -> str`.
  - `documents.validation`: `ValidFile(name: str, content_type: str, data: bytes)` (frozen); `clean_file_name(raw: str | None) -> str`; `detect_type(data: bytes) -> DocumentType | None`; `async read_valid_file(upload: UploadFile, max_bytes: int) -> ValidFile`.
  - `documents.forms.read_uploads(request: Request, settings: Settings, field: str, *, exactly_one: bool) -> Awaitable[list[ValidFile]]`.
  - `DocumentRepository(Protocol)` with `add(document: NewDocument) -> Document` and `get(document_id: UUID) -> Document | None` (later tasks add the rest of the spec's Protocol).
  - `ProjectRepository.touch(project_id: UUID) -> None`.
  - `UnitOfWork.documents: DocumentRepository`.
  - `documents.dependencies.AccessibleProject = Annotated[ProjectAccess, Depends(get_accessible_project)]` (`get_accessible_project(project_id: UUID, user: CurrentUser, uow) -> ProjectAccess` → `get_project`).
  - `documents.schemas`: `UploaderResponse(id: UUID, login: str)`, `DocumentResponse(id, project_id, name, content_type, size: int, uploaded_by: UploaderResponse | None, created_at, updated_at)` with `from_document(document: Document) -> Self`.
  - `documents.service.upload_documents(uow: UnitOfWork, storage: FileStorage, user: User, project_id: UUID, files: Sequence[ValidFile]) -> list[Document]`; `_log_event(event: str, user: User, project_id: UUID, document_id: UUID)` (logger `project_hub.documents.service`, same shape as `projects.service._log_event` plus `document_id`).
  - Route `POST /project/{project_id}/documents` → 201 `list[DocumentResponse]`, with `openapi_extra` describing `multipart/form-data` `{files: array of string/binary}` (required).
  - Test helpers `tests/support/documents.py`: `pdf_bytes(marker: str = "x") -> bytes` (starts `%PDF-1.4`), `docx_bytes(marker: str = "x") -> bytes` (zip with `[Content_Types].xml` and `word/document.xml`), `upload(client, token, project_id, files: list[tuple[str, bytes]], field: str = "files") -> httpx2.Response`, `broken_storage(app) -> contextmanager` (temporarily replaces `app.state.storage` with an `S3FileStorage` on a missing bucket), `with_limits(app, *, max_bytes: int | None = None, max_files: int | None = None) -> contextmanager` (temporarily replaces `app.state.settings` with a `model_copy`).

- [ ] **Step 1: Write the failing migration tests** (`tests/db/test_migrations.py`)
  - `test_upgrade_creates_documents_table`: columns and types, nullability (`uploaded_by` nullable), every constraint name from the spec, `ix_documents_project_id`, FK delete rules (`CASCADE`, `SET NULL`) from `information_schema` / `pg_constraint`.
  - `test_documents_constraints_reject_bad_rows`: empty name, 256-char name, `content_type='text/plain'`, `size=0`, duplicate `storage_key` each raise (AC 45).
  - `test_downgrade_to_0003_drops_documents`: `documents` gone, `projects` stays.
  - Change `test_upgrade_twice_is_noop` to `("0004",)`; import `DocumentModel` in `test_orm_metadata_matches_migrated_schema`.
- [ ] **Step 2: Write the failing contract tests** (`tests/documents/test_repository_contract.py`, both backends; users and projects created through their repositories)
  - `test_add_returns_document_with_uploader_login` (AC 33): generated id, tz-aware `created_at == updated_at`, `uploader_login == "mila"`; `get` returns an equal `Document`; `get(uuid4())` is `None`.
  - `test_add_with_unknown_project_raises_and_uow_stays_usable` (AC 38).
  - `test_deleting_project_removes_its_documents` and `test_deleting_uploader_sets_uploaded_by_none` (AC 39; delete the user with plain SQL through the fixture's URL after removing any blocking project, or upload into a project owned by someone else).
  - `test_nothing_stored_without_commit` (AC 40).
  - In `tests/projects/test_repository_contract.py`: `test_touch_changes_updated_at` (add in one UoW, touch in a second, `updated_at` later).
- [ ] **Step 3: Write the failing validation unit tests** (`tests/documents/test_validation.py`, no I/O beyond `UploadFile` over `BytesIO`)
  - `clean_file_name`: `"../../etc/x.pdf"` → `"x.pdf"`; `"C:\\tmp\\x.pdf"` → `"x.pdf"`; `"  a.pdf "` → `"a.pdf"`; `None`, `""`, `"dir/"` → `ValidationFailedError("File name is missing")`; 256 chars → 422; `"a\nb.pdf"` → 422.
  - `detect_type`: pdf bytes → `PDF`; docx bytes → `DOCX`; PNG bytes, `b"PK\x03\x04garbage"`, a zip without `word/document.xml` → `None`.
  - `read_valid_file`: extension rule message `"photo.png: only pdf and docx documents are allowed"`; `max_bytes + 1` bytes → `PayloadTooLargeError("big.pdf: file is larger than 10 MB")` for `max_bytes=10_485_760`, and `"… larger than 100 bytes"` for `max_bytes=100` (rule: whole MiB → `"N MB"`, otherwise `"N bytes"`); empty → `"e.pdf: file is empty"`; mismatch → `"x.docx: content is not a valid docx"` / `"x.pdf: content is not a valid pdf"`; reads at most `max_bytes + 1` bytes; `content_type` is the canonical one whatever `upload.content_type` says.
- [ ] **Step 4: Write the failing API tests** (`tests/documents/test_upload_api.py`, `api_client`, `s3_client`, `storage_bucket`)
  - `test_owner_uploads_one_pdf` (AC 1): exact response fields; `bucket_keys` has one key starting `projects/<id>/documents/` and its bytes equal the upload.
  - `test_uploads_pdf_and_docx_in_order` (AC 2).
  - `test_participant_uploads` (AC 3).
  - `test_outsider_and_unknown_project_get_same_404` (AC 4): outsider with a valid file, outsider with an invalid file, random UUID → identical 404 bodies; bucket empty; list via SQL shows no rows.
  - `test_bad_file_in_batch_stores_nothing` (AC 5), parametrized over: `photo.png`, PNG bytes as `.pdf`, zip without `word/document.xml` as `.docx`, empty `.pdf`, name with `\x07`; batch = good pdf + the bad one; 422 whose `detail` contains the bad file's name; bucket empty, no rows.
  - `test_file_over_limit_is_413` (AC 6) using `with_limits(max_bytes=100)`.
  - `test_too_many_files_is_422` (AC 7) using `with_limits(max_files=2)` and 3 files → `"Too many files: at most 2 per request"`; `test_no_files_is_422` (`"No files were sent"`).
  - `test_path_in_file_name_is_dropped` (AC 8): name `x.pdf`, key does not contain `x.pdf` or `..`.
  - `test_same_name_twice_allowed` (AC 9).
  - `test_storage_unavailable_is_503_and_no_row` (AC 10) with `broken_storage`.
  - `test_upload_moves_project_to_top` (AC 29): two projects, upload into the older one, it is first in `GET /projects`.
  - Review Focus: `test_upper_case_extension_accepted`, `test_content_must_match_extension`, `test_same_file_twice_in_one_request` (two keys, both objects present), `test_wrong_field_name_is_422`.
  - `test_unicode_name_round_trips`: `диплом.pdf` comes back unchanged in the response.
- [ ] **Step 5: Write the failing auth and log tests**
  - `tests/documents/test_documents_auth_api.py`: `POST` without token / with garbage token → 401 with `WWW-Authenticate: Bearer`; non-UUID project id → 422 (AC 32). `test_upload_body_not_parsed_before_access` (AC 32a): body `b"not multipart"` with `Content-Type: multipart/form-data; boundary=x` → 401 without token and 404 for an outsider (not 422). Later tasks extend this file for their routes.
  - `tests/documents/test_documents_log.py` (AC 12): two files → two INFO records `document uploaded` with `login`, `user_id`, `project_id`, `document_id` in `extra`, and the file name in neither message nor extra.
- [ ] **Step 6: Run, see them fail** — `poetry run pytest tests/documents tests/db/test_migrations.py tests/projects/test_repository_contract.py -q`.
- [ ] **Step 7: Implement** migration `0004` (spec table, `down_revision = "0003"`), `DocumentModel` (constraint names identical, `eager_defaults`), both repositories (`add`, `get` joining `users` for `uploader_login`; savepoint around `add`), `touch` on both project repositories, UoW wiring, settings `document_max_bytes`/`document_max_files` with `Field(ge=…, le=…)`, `PayloadTooLargeError` mapping, validation, forms, dependencies, service, schemas, router, `main.py` include.
  - `read_uploads`: `async with request.form() as form` (Starlette default `max_files=1000`); a Starlette `HTTPException(400)` from parsing → `ValidationFailedError(f"Invalid multipart form: {detail}")`; items of `form.getlist(field)` that are not `UploadFile` are ignored; zero → `"No files were sent"`; `exactly_one` and count ≠ 1 → `"Exactly one file is required"`; more than `settings.document_max_files` → `"Too many files: at most N per request"`; then `read_valid_file` for each, in order. The limits come from `request.app.state.settings`.
  - Route signature: `upload_documents(project_id: UUID, request: Request, project: AccessibleProject, user: CurrentUser, uow, storage: Storage) -> list[DocumentResponse]` — the dependency runs first, then `read_uploads`, then the service.
  - Service order exactly as the spec's upload row; on `put` failure delete already-put keys with `discard_quietly` and re-raise; on any later exception delete all put keys the same way and re-raise; `touch` before `commit`; log after commit.
- [ ] **Step 8: Run** — full checks green.
- [ ] **Step 9: Settings test** — `tests/test_config.py`: `test_document_limits_reject_out_of_range` parametrized (`APP_DOCUMENT_MAX_BYTES` 0 and 104857601, `APP_DOCUMENT_MAX_FILES` 0 and 101 → `ValidationError`); `test_document_limits_default` (10_485_760, 10).
- [ ] **Step 10: README** — "Documents" section (upload part: field `files`, limits and their settings, validation rules and messages, all-or-nothing, 503, log event), `0004` row in the migrations table. Roadmap rows as listed in Files.
- [ ] **Step 11: Commit** — `Upload pdf and docx documents with POST /project/{id}/documents`.

---

### Task 3: List a project's documents with GET /project/{id}/documents

Spec: service `list_documents`, API. AC 13, 14, 34 (single project), 32 (this route).

**Interfaces:**
- Consumes: Task 2 entities, `AccessibleProject`, `DocumentResponse`.
- Produces: `DocumentRepository.list_for_project(project_id: UUID) -> list[Document]` (`created_at DESC, id DESC`); `documents.service.list_documents(uow, project_id: UUID) -> list[Document]`; route `GET /project/{project_id}/documents` → `list[DocumentResponse]`.

- [ ] **Step 1: Failing tests** — contract `test_list_for_project_orders_newest_first_and_filters_project` (two projects, three documents, equal `created_at` inside one transaction → ordered by id desc); API `tests/documents/test_list_api.py`: `test_owner_and_participant_see_documents_newest_first` (AC 13, none of another project's), `test_empty_project_lists_empty`, `test_outsider_and_unknown_get_404` (AC 14); auth file: 401 / 422 for this route.
- [ ] **Step 2: Run, fail.**
- [ ] **Step 3: Implement** both repositories, service, route.
- [ ] **Step 4: Run** — full checks green.
- [ ] **Step 5: README** — list route in "Documents".
- [ ] **Step 6: Commit** — `List a project's documents with GET /project/{id}/documents`.

---

### Task 4: Download a document with GET /document/{id}

Spec: download row, "Download headers". AC 15, 16, 17, 32 (this route), 48 (round trip in the stack).

**Files:** + `tests/documents/test_download_api.py`; modify `tests/test_docker_smoke.py` (new test only).

**Interfaces:**
- Consumes: Task 2 `get`, Task 1 `FileStorage.get`.
- Produces: `documents.service.get_document(uow, user, document_id: UUID) -> Document` (unknown → `NotFoundError("Document not found")`; `get_project` raising `NotFoundError` → re-raised as `NotFoundError("Document not found")`); `documents.dependencies.AccessibleDocument = Annotated[Document, Depends(get_accessible_document)]`; `documents.service.download_document(storage, document: Document) -> bytes`; `documents.router.content_disposition(name: str) -> str`.

- [ ] **Step 1: Failing tests**
  - `test_owner_and_participant_download_exact_bytes` (AC 15): status 200, bytes equal, `content-type` stored type, `content-disposition` starts `attachment;`, `x-content-type-options: nosniff`, `cache-control: private, no-store`.
  - `test_download_header_survives_odd_names` (Review Focus 4): for `a"b;c.pdf` and `диплом.pdf`, parse the header with `email.message.Message` (`msg["content-disposition"] = header; msg.get_filename()`) and get the original name back; the header has no raw `"` inside the `filename=` value and no CR/LF.
  - `test_outsider_and_unknown_get_same_404` (AC 16).
  - `test_missing_object_is_503` (AC 17): delete the object with `s3_client.delete_object`, then 503.
  - auth file: 401 / 422 for this route.
  - `tests/test_docker_smoke.py::test_compose_stack_round_trips_a_document` (AC 48): stack up (env `APP_PORT`, `APP_DB_PORT`, `APP_S3_PORT` = `0`, `APP_JWT_SECRET` set to a test-only 32+ char value), register, login, create project, upload a minimal pdf with `urllib` multipart (or `httpx2`), download it, bytes equal; `down -v` in `finally`.
- [ ] **Step 2: Run, fail.**
- [ ] **Step 3: Implement** — `Response(content=…, media_type=document.content_type, headers=…)`. `content_disposition`: `attachment; filename="<ascii>"; filename*=UTF-8''<quote(name, safe="")>` where `<ascii>` replaces every non-ASCII char and `"`, `\`, `;` and control chars with `_`.
- [ ] **Step 4: Run** — full checks and `pytest -m docker` green.
- [ ] **Step 5: README** — download route and headers; "the frontend downloads with `fetch` and the Bearer header".
- [ ] **Step 6: Commit** — `Download a document with GET /document/{id}`.

---

### Task 5: Replace a document's file with PUT /document/{id}

Spec: replace row. AC 18–23, 29 (replace), 32/32a (this route), 35.

**Interfaces:**
- Consumes: Task 2 `read_uploads(..., field="file", exactly_one=True)`, `new_storage_key`, Task 4 `AccessibleDocument`.
- Produces: `documents.entities.ReplacedFile(name: str, content_type: str, size: int, storage_key: str, uploaded_by: UUID)`; `DocumentRepository.replace_file(document_id: UUID, file: ReplacedFile) -> Document | None`; `documents.service.replace_document(uow, storage, user, document: Document, file: ValidFile) -> Document`; route `PUT /document/{document_id}` → `DocumentResponse`, `openapi_extra` with one binary `file`.

- [ ] **Step 1: Failing tests**
  - contract `test_replace_file_changes_fields_keeps_created_at` (AC 35: add in UoW 1, replace in UoW 2, `updated_at` later, same-UoW `get` sees it; unknown id → `None`).
  - API `tests/documents/test_replace_api.py`: `test_owner_and_participant_replace` (AC 18: same id and `created_at`, new fields, `uploaded_by` = caller, download gives new bytes, old key gone, exactly one key for the document); `test_pdf_and_docx_swap` (AC 19); `test_outsider_and_unknown_get_404_and_nothing_changes` (AC 20); `test_invalid_file_keeps_old_document` parametrized over the AC 5 cases + over-limit (AC 21: 422/413, download still old bytes, old key present); `test_zero_or_two_files_is_422` (`"Exactly one file is required"`); `test_storage_unavailable_keeps_document` (AC 22); `test_replace_moves_project_to_top` (AC 29).
  - log: `document replaced` record (AC 23). Auth: 401/422 and the not-parsed-before-access check for `PUT`.
- [ ] **Step 2: Run, fail.**
- [ ] **Step 3: Implement** per the spec's replace row: `put` new key → `replace_file` → `touch` → commit → log → `discard_quietly([old_key])`; database failure → `discard_quietly([new_key])`, re-raise; `replace_file` returning `None` → `discard_quietly([new_key])`, `NotFoundError("Document not found")`.
- [ ] **Step 4: Run** — full checks green.
- [ ] **Step 5: README**, **Step 6: Commit** — `Replace a document's file with PUT /document/{id}`.

---

### Task 6: Delete a document with DELETE /document/{id}

Spec: delete row. AC 24–27, 29 (delete), 32, 36.

**Interfaces:**
- Produces: `DocumentRepository.delete(document_id: UUID) -> Document | None`; `documents.service.delete_document(uow, storage, user, document: Document) -> None`; route `DELETE /document/{document_id}` → 204, `response_class=Response`.

- [ ] **Step 1: Failing tests** — contract `test_delete_returns_row_then_get_is_none` (AC 36); API `tests/documents/test_delete_api.py`: `test_owner_and_participant_delete` (AC 24: 204 empty body, then download 404, not in list, object gone), `test_outsider_and_unknown_get_404_nothing_deleted` (AC 25), `test_s3_failure_still_204_with_warning` (AC 27: `broken_storage` around the delete; row gone; WARNING `document files left in storage` with the key), `test_delete_moves_project_to_top` (AC 29); log `document deleted` (AC 26); auth 401/422.
- [ ] **Step 2: Run, fail.** **Step 3: Implement** (`delete` → `touch` → commit → log → `discard_quietly`). **Step 4: Run** green.
- [ ] **Step 5: README**, **Step 6: Commit** — `Delete a document with DELETE /document/{id}`.

---

### Task 7: See each project's documents in GET /projects

Spec: "`GET /projects`". AC 28, 34 (many projects).

**Interfaces:**
- Produces: `DocumentRepository.list_for_projects(project_ids: Sequence[UUID]) -> dict[UUID, list[Document]]` (one query, entry for every id); `documents.service.documents_by_project(uow, project_ids: Sequence[UUID]) -> dict[UUID, list[Document]]`; `ProjectListItem.documents: list[DocumentResponse] = []` and `ProjectListItem.from_access(access, documents: Sequence[Document] = ()) -> Self`.

- [ ] **Step 1: Failing tests** — contract `test_list_for_projects_has_entry_for_every_id` (two with documents, one without, one unknown id → `[]` each where empty; per-project order newest first); API in `tests/documents/test_projects_list_api.py`: `test_projects_list_includes_each_projects_documents` (AC 28: exact `DocumentResponse` dicts per project, `[]` for an empty project). The existing `tests/projects/test_list_api.py` keeps passing unchanged.
- [ ] **Step 2: Run, fail.** **Step 3: Implement** (router calls `documents_by_project` once with the page's ids). **Step 4: Run** green.
- [ ] **Step 5: README** (`GET /projects` paragraph), **Step 6: Commit** — `See each project's documents in GET /projects`.

---

### Task 8: Delete a project's documents and files with the project

Spec: "Project delete". AC 30, 31, 37.

**Interfaces:**
- Produces: `DocumentRepository.storage_keys_for_project(project_id: UUID) -> list[str]`; `projects.service.delete_project(uow, storage: FileStorage, user, project_id) -> None`; `projects.router.delete_project` gains `storage: Storage`.

- [ ] **Step 1: Failing tests** — contract `test_storage_keys_for_project_only_that_project` (AC 37); API `tests/documents/test_project_delete_api.py`: `test_project_delete_removes_documents_and_files` (AC 30: two projects with documents; delete one; its keys gone, other project's keys stay; its documents 404), `test_project_delete_s3_failure_still_204_with_warning` (AC 30 second half: `broken_storage`; warning names the keys; project gone), `test_participant_delete_touches_nothing` (AC 31: 403, documents and keys intact). Existing `tests/projects/test_delete_api.py` stays unchanged and green.
- [ ] **Step 2: Run, fail.** **Step 3: Implement** (spec order: keys → delete → commit → log → `discard_quietly`). **Step 4: Run** green.
- [ ] **Step 5: README** (project delete line), **Step 6: Commit** — `Delete a project's documents and their files with the project`.

---

### Task 9: Refuse oversized upload requests before reading them

Spec: "Request size guard". AC 11.

**Files:** create `documents/upload_limit.py`, `tests/documents/test_upload_limit_api.py`; modify `main.py`, `README.md`.

**Interfaces:**
- Produces: `UploadLimitMiddleware(app: ASGIApp)` (pure ASGI), added in `create_app`; for `POST` on `^/project/[^/]+/documents/?$` and `PUT` on `^/document/[^/]+/?$` only; limits read from `scope["app"].state.settings` on each request: `POST` max = `document_max_files × document_max_bytes + 1_048_576`, `PUT` max = `document_max_bytes + 1_048_576`.

- [ ] **Step 1: Failing tests** — `test_post_without_content_length_is_411` (body as a generator → chunked; `{"detail": "Content-Length is required"}`); `test_post_over_limit_is_413_and_route_never_runs` (`with_limits(max_bytes=100, max_files=1)`, a real valid multipart body of ~1.1 MiB padded with a large extra form field; 413 `{"detail": "Request is too large"}`; no row, bucket empty); same two for `PUT` (document unchanged); `test_other_routes_unaffected` (`POST /projects` with a chunked JSON body still works, `GET /document/{id}` untouched); `test_normal_upload_still_works`.
- [ ] **Step 2: Run, fail.** **Step 3: Implement** (answer with a JSON response without calling the inner app; a non-integer or negative `Content-Length` → 400 `{"detail": "Invalid Content-Length"}`). **Step 4: Run** green.
- [ ] **Step 5: README** (411/413 and the demo note), **Step 6: Commit** — `Refuse oversized upload requests before reading them`.

---

## Coverage check (spec AC → task)

| AC | Task | AC | Task | AC | Task |
|---|---|---|---|---|---|
| 1–10, 12 | 2 | 24–27 | 6 | 41–43 | 1 |
| 11 | 9 | 28 | 7 | 44–46 | 2 |
| 13–14 | 3 | 29 | 2, 5, 6 | 47 | 1, 2 |
| 15–17 | 4 | 30–31 | 8 | 48 | 1, 4 |
| 18–23 | 5 | 32 | 2–6 | 49 | every task + final verification |
| 32a | 2, 5 | 33, 38–40 | 2 | 34 | 3, 7 |
| 35 | 5 | 36 | 6 | 37 | 8 |

Not covered by a test on purpose (simple code, failure hard to produce against real S3): `replace_document` when deleting the **old** key fails after a successful commit (logged WARNING, still 200).

## After the tasks

- Shared notes folder: `epic-6-documents-notes-for-frontend.md` and `epic-6-documents-handover.md` (key layout, `FileStorage`, moto, what 7a/7b can rely on).
- Phase 5 verification table (AC → test/command → status), Phase 6 review, PR.
