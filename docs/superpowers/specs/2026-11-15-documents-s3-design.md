# Epic 6: Documents and S3

Date: 2026-11-15
Status: approved design (2026-11-15)
Roadmap: [`docs/PRDs/roadmap.md`](../../PRDs/roadmap.md), epic 6
Spec: [`docs/initial-spec.md`](../../initial-spec.md) — `GET /projects` ("full info
(details + documents)"), `DELETE /project/<project_id>` ("Deletes the corresponding
documents"), `GET|POST /project/<project_id>/documents`,
`GET|PUT|DELETE /document/<document_id>`; "Add/Update/Remove projects documents (docx,
pdf)"; "All the returned data must be in JSON format (except for file data)"
Builds on: [epic 4 design](2026-11-14-projects-access-design.md) (access model, 404 rule,
`delete_project` seam)

## Intent

Let the owner and the participants of a project keep its documents (pdf and docx) in
the project: upload one or several, see the list, download, replace one with a new
file, delete one. The files themselves live in S3; Postgres keeps only what is known
about them. Deleting a project deletes its documents and their files.

The project is defended in front of a mentor, so every rule must be easy to explain
and to show live in Swagger: upload two files, download one, replace it, show that an
outsider gets 404 and that a renamed `.exe` is refused. Epics 7a (size and quota
Lambda) and 7b (image resize Lambda) build on the S3 part, so the storage layer must
be small and behind a Protocol.

## Goals

- The five document endpoints of the spec, with the epic 4 access rules: owner and
  participants may list, upload, download, replace and delete; anybody else gets the
  same 404 as for an id that does not exist.
- Only pdf and docx, checked by extension **and** by content.
- `GET /projects` fills `documents` for every project.
- `DELETE /project/<id>` removes the project's document rows and their S3 files.
- Both data backends (`orm`, `sql`), shared contract tests, hand-written migration
  `0004`.
- Real S3 tests against an emulator in docker compose and in CI; no mocks.
- Limits and S3 settings are plain settings in `core/config.py`.
- Additions accepted by the user (see [Beyond the spec](#beyond-the-spec)).

## Non-goals

- Per-project space quota and the size-summing Lambda — epic 7a.
- Image resize — epic 7b.
- Terraform for the real bucket — epic 8a.
- Any frontend code. Notes for the frontend epic F4 go to the shared notes folder.
- Anything in [Future improvements](#future-improvements).

## Anti-goals (it would be a failure even if it "works")

- A user without access to a project can list, download, replace or delete one of its
  documents, or can tell from the answer that the document exists.
- A file that is not really pdf or docx is stored (for example `virus.exe` renamed to
  `virus.pdf`).
- A failed request leaves half of its work behind: some files of a batch stored, a
  document row pointing to a file that is not in S3, or a replaced document whose
  metadata describes the old file.
- The user-supplied file name decides where the file goes in S3.
- A huge request fills the server's disk or memory before it is refused.
- Tests that fake S3 with mocks instead of talking to a real S3 API.
- Real AWS keys anywhere in the repository, compose or CI.

## Constraints

- Endpoint names exactly as in the spec.
- Swappable data layer (roadmap): `DocumentRepository` Protocol, SQLAlchemy and
  psycopg implementations, on both Units of Work, domain entities out of the
  repository, schema from a hand-written migration, shared contract tests on both
  backends (file name ends in `_contract.py` so `tests/support/backend_coverage.py`
  counts it).
- "What to test" in `CLAUDE.md`: endpoints through `TestClient`, repositories on real
  Postgres, migrations on a real database, S3 against a real S3 API, Docker smoke
  tests that build and run the stack; no tests that re-read config files.
- Migration head is `0003`; this epic adds `0004` (`down_revision = "0003"`).
- Existing error mapping: `NotFoundError` → 404, `PermissionDeniedError` → 403,
  `ConflictError` → 409, `ValidationFailedError` → 422, all `{"detail": str}`.
- AWS sandbox rules: names derive from `project-hub`, region `eu-west-1`, no company
  name anywhere. This epic runs locally only.
- The backend stays free of frontend code.

## Decisions taken with the user (2026-11-14/15)

| Question | Decision |
|---|---|
| Upload path | **Through the API** (multipart form). Presigned upload URLs rejected: two-step flow, the type can only be checked after the file is already in S3, needs bucket CORS, awkward in Swagger |
| Download | **Through the API**: `GET /document/<id>` answers with the file bytes. The spec says file data is the one thing not returned as JSON. The frontend fetches with the `Authorization` header and saves the blob |
| What "update document" means | `PUT /document/<id>` **replaces the file** of one document; the id stays. A document is exactly one file; a project has many documents |
| A bad file in a batch | **All or nothing per request**: one bad file → 422 naming the file, nothing stored. The frontend sends **one request per file**, so in the UI good files are saved and a bad one shows its own error |
| Upload order inside a request | Files are stored one after another, not in parallel (a handful of small files; simpler error handling) |
| Limits | 10 MB per file, 10 files per request, empty file refused; both limits are settings in `core/config.py` |
| Duplicate file names in one project | **Allowed** (two `thesis.docx` are two documents, told apart by date and uploader) |
| Project `updated_at` | **Touched** when a document of the project is uploaded, replaced or deleted, so the project moves to the top of `GET /projects` |
| S3 library | **boto3**, calls run in a worker thread (`asyncio.to_thread`), typed with `boto3-stubs[s3]` |
| Local and CI S3 | **moto server** in docker compose and as a CI service container (see [Approaches](#approaches-considered)) |

## Approaches considered

### Upload and download path

| | A. Through the API | B. Presigned S3 URLs | C. Upload through the API, download by presigned URL |
|---|---|---|---|
| Access, type and size checked before the file is stored | yes | no (only after upload) | yes |
| Steps for one upload | one request | ask for a URL, upload to S3, confirm | one request |
| Bucket CORS and CSP `connect-src` for the S3 origin | not needed | needed | needed for download |
| Shown in Swagger | one "Try it out" | not really | half |
| Load on the API server | file bytes pass through it (bounded by the 10 MB limit) | none | upload only |

**Chosen: A** (user). The server stays the single place that decides who may touch a
file and what a valid file is; this is what the defense has to show.

### S3 emulator for local work and CI

| | LocalStack (planned in the roadmap) | Older LocalStack image pinned before 2026.03 | **moto server** | Real S3 in the sandbox |
|---|---|---|---|---|
| Works without an account or key | no: since 2026.03 it needs an auth token, and the free plan has no CI token | yes | yes | needs AWS keys in CI |
| Maintained | yes | no (frozen) | yes (`motoserver/moto`, Apache-2.0) | — |
| Same code as for AWS | yes | yes | yes (boto3 `endpoint_url`) | yes |

**Chosen: moto server** (agent's proposal, the user asked why and accepted). LocalStack
now refuses to start without a token
([release 2026.03.0](https://blog.localstack.cloud/localstack-for-aws-release-2026-03-0/),
[roadmap post](https://blog.localstack.cloud/the-road-ahead-for-localstack/)), and agents
never handle keys. Epics 7a/7b re-check this choice for Lambda emulation; the roadmap
note "S3 and Lambda emulated with LocalStack" is updated to say so.

### S3 client library

| | **boto3 + `asyncio.to_thread`** | aioboto3 / aiobotocore |
|---|---|---|
| Who maintains it | AWS | third party, follows boto3 with a delay |
| Typing under pyright strict | `boto3-stubs[s3]` | weaker |
| Shared with the Lambdas of 7a/7b | yes (in the Lambda runtime) | no |
| Async | through a worker thread | native |

**Chosen: boto3** (user). Hand-written signed HTTP requests were dropped: easy to get
wrong, nothing to gain.

## Beyond the spec

Proposed to the user with what, why and cost; decisions of 2026-11-15.

| # | Addition | Decision |
|---|---|---|
| 1 | Document metadata has `size`, `content_type`, `created_at` (first upload) and `updated_at` (last replacement); frontend request | **accepted** |
| 2 | `uploaded_by: {id, login}` — who uploaded or last replaced the file | **accepted** |
| 3 | Security-log records `document uploaded`, `document replaced`, `document deleted` | **accepted** |
| 4 | Rename a document without replacing the file | **postponed** → Future improvements |
| 5 | Version history (old file kept after a replace) | **rejected** |
| 6 | Refuse a duplicate name with 409 and offer "replace" | **rejected**: the user prefers allowing duplicates |
| 7 | Automatic rename of a duplicate (`thesis (1).docx`) | **postponed** → Future improvements |
| 8 | Touch the project's `updated_at` on document changes | **accepted** |

Frontend requests from the roadmap: metadata (size, type, date) → **accepted** (#1);
download decision → **decided: through the API**; bucket CORS and CSP `connect-src`
→ **not needed** (no browser-to-S3 traffic).

## Design

### Layout

| Package / file | Holds |
|---|---|
| `src/project_hub/storage/__init__.py` | — |
| `storage/files.py` | `FileStorage` Protocol, `StorageUnavailableError` |
| `storage/s3.py` | `S3FileStorage` (boto3), `create_s3_storage(settings)` |
| `storage/create_bucket.py` | `python -m project_hub.storage.create_bucket`: creates the configured bucket if it is missing (local compose only) |
| `storage/dependencies.py` | `get_storage(request)`, like `db/dependencies.get_uow` |
| `src/project_hub/documents/entities.py` | `DocumentType`, `NewDocument`, `Document`, `ReplacedFile` |
| `documents/validation.py` | file name, size and content checks → `ValidFile` |
| `documents/repository.py` | `DocumentRepository` Protocol |
| `documents/models.py` | `DocumentModel` (SQLAlchemy) |
| `documents/repository_orm.py`, `documents/repository_sql.py` | the two implementations |
| `documents/schemas.py` | `DocumentResponse`, `UploaderResponse` |
| `documents/service.py` | access rules, S3 + database ordering, logging; no HTTP |
| `documents/router.py` | the five routes |
| `documents/upload_limit.py` | the request-size guard (see [Request size guard](#request-size-guard)) |

Also: `db/uow.py` gets `documents: DocumentRepository`; `db/orm.py` and `db/sql.py`
build it; `main.py` creates the storage in the lifespan, stores it on
`app.state.storage` and includes the router; `core/exceptions.py` gets
`PayloadTooLargeError` (→ 413) and the error handler maps it and
`StorageUnavailableError` (→ 503); `projects/service.delete_project` and
`projects/schemas.ProjectListItem` change (below).

### Settings (`core/config.py`)

| Setting | Env | Default | Rule |
|---|---|---|---|
| `s3_bucket` | `APP_S3_BUCKET` | `None` | when unset the app starts without storage; document routes then answer 500 (same pattern as `APP_DATABASE_URL`), and a warning is logged at startup |
| `s3_endpoint_url` | `APP_S3_ENDPOINT_URL` | `None` | set for moto (`http://s3:5000` in compose); unset in AWS |
| `s3_region` | `APP_S3_REGION` | `eu-west-1` | sandbox region |
| `document_max_bytes` | `APP_DOCUMENT_MAX_BYTES` | `10485760` (10 MiB) | 1 … 104857600 |
| `document_max_files` | `APP_DOCUMENT_MAX_FILES` | `10` | 1 … 100 |

AWS credentials are **not** settings: boto3 reads its standard chain
(`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` from the environment locally, the ECS task
role in AWS). Compose and CI pass the dummy values `test`/`test`, which moto accepts;
`.env.example` documents this and says never to put real keys there. Blank strings for
`s3_bucket` and `s3_endpoint_url` count as unset (like `jwt_secret`). `_clean_env` in
`tests/conftest.py` also clears the new `APP_*` variables.

### Storage

```python
class FileStorage(Protocol):
    async def put(self, key: str, data: bytes, content_type: str) -> None: ...
    async def get(self, key: str) -> bytes: ...
    async def delete(self, keys: Sequence[str]) -> None: ...
```

- `S3FileStorage(client, bucket)`; every boto3 call goes through `asyncio.to_thread`.
  One client is built at startup (boto3 clients are thread-safe) with
  `endpoint_url`, `region_name` and botocore `Config(connect_timeout=5,
  read_timeout=30, retries={"max_attempts": 3, "mode": "standard"},
  max_pool_connections=20)`. When `endpoint_url` is set (moto), the config also has
  `s3={"addressing_style": "path"}`: otherwise botocore builds virtual-hosted URLs
  such as `http://project-hub-documents.s3:5000`, which do not resolve.
- `delete` accepts any number of keys, sends `DeleteObjects` in chunks of 1000, does
  nothing for an empty list, and succeeds for keys that do not exist (S3 semantics).
  A per-key error in the `DeleteObjects` answer counts as a failure.
- Any botocore/boto3 error (connection, timeout, missing bucket, access denied, a
  missing object on `get`) becomes `StorageUnavailableError`; the original is logged
  as the exception cause, never sent to the client. The error handler answers
  **503 `{"detail": "File storage is unavailable"}`**.
- `create_bucket` creates the bucket when `HeadBucket` says it is missing, and is a
  no-op otherwise; it passes `CreateBucketConfiguration` with the region unless the
  region is `us-east-1`.

**Object keys:** `projects/{project_id}/documents/{uuid4}`. The random part is new for
every stored file, including a replacement, and has nothing to do with the user's file
name. The project prefix lets the 7a Lambda map an S3 event to its project and lets a
whole project be listed or cleaned up by prefix. The key is stored in the document row
(`storage_key`) and never shown in the API.

### Database — migration `0004`

```
documents
  id            uuid        PK, default gen_random_uuid()
  project_id    uuid        NOT NULL, FK → projects(id) ON DELETE CASCADE
  name          text        NOT NULL, CHECK (char_length(name) BETWEEN 1 AND 255)
  content_type  text        NOT NULL, CHECK (content_type IN ('application/pdf',
                            'application/vnd.openxmlformats-officedocument.wordprocessingml.document'))
  size          bigint      NOT NULL, CHECK (size > 0)
  storage_key   text        NOT NULL, UNIQUE
  uploaded_by   uuid        NULL, FK → users(id) ON DELETE SET NULL
  created_at    timestamptz NOT NULL, default now()
  updated_at    timestamptz NOT NULL, default now()
  index ix_documents_project_id (project_id)
```

- Explicit constraint names: `fk_documents_project_id_projects`,
  `fk_documents_uploaded_by_users`, `ck_documents_name_length`,
  `ck_documents_content_type`, `ck_documents_size_positive`,
  `uq_documents_storage_key`.
- `ON DELETE CASCADE` from `projects`: the rows go with the project in the same
  transaction (the S3 files are removed by the service, below).
- `uploaded_by … ON DELETE SET NULL` (agent's call): a document belongs to the
  project, not to its uploader; when `DELETE /users/me` arrives, deleting a participant
  must neither delete nor block the documents they uploaded. The API then shows
  `uploaded_by: null`.
- The `CHECK`s repeat the validation rules as a second line of defense.
- `ix_documents_project_id` serves the list per project, the list for many projects
  (`= ANY(...)`) and the cascade. Sorting a project's documents happens on that small
  set; no index on `created_at`.
- `downgrade()` drops `documents`.

### Entities and repository

- `DocumentType` (`StrEnum`: `pdf`, `docx`) with its extension and canonical content
  type.
- `NewDocument(project_id, name, content_type, size, storage_key, uploaded_by)`
- `Document(id, project_id, name, content_type, size, storage_key, uploaded_by,
  uploader_login, created_at, updated_at)` — `uploaded_by` and `uploader_login` are
  `None` after the uploader is deleted.
- `ReplacedFile(name, content_type, size, storage_key, uploaded_by)`

```python
class DocumentRepository(Protocol):
    async def add(self, document: NewDocument) -> Document: ...
    async def get(self, document_id: UUID) -> Document | None: ...
    async def list_for_project(self, project_id: UUID) -> list[Document]: ...
    async def list_for_projects(self, project_ids: Sequence[UUID]) -> dict[UUID, list[Document]]: ...
    async def replace_file(self, document_id: UUID, file: ReplacedFile) -> Document | None: ...
    async def delete(self, document_id: UUID) -> Document | None: ...
    async def storage_keys_for_project(self, project_id: UUID) -> list[str]: ...
```

- Lists are ordered `created_at DESC, id DESC`. `list_for_projects` returns an entry
  (possibly `[]`) for every id asked for, in one query, so `GET /projects` makes no
  query per project.
- `replace_file` sets the five fields and `updated_at = now()`; `created_at` stays.
  It returns the new row or `None` for an unknown id. The ORM version uses
  `populate_existing=True`, as in `users` and `projects`.
- `delete` returns the deleted row (the service needs its `storage_key` and
  `project_id`) or `None`.
- `add` and `replace_file` failures (foreign key, check) leave the Unit of Work usable
  (savepoint pattern from `users`/`projects`).
- The repository checks no access; the service does.
- `ProjectRepository` gets `touch(project_id) -> None` (`UPDATE projects SET
  updated_at = now()`), used by the document service (decision #8).

### File validation (`documents/validation.py`)

For every uploaded file, in this order; the first failure stops the whole request:

1. **Name.** Take the client's file name, keep only the part after the last `/` or
   `\`, strip surrounding whitespace. Missing or empty → 422 `File name is missing`.
   Longer than 255 characters or containing a control character (category `Cc`) →
   422. The name is stored as cleaned; it is never used as a path.
2. **Extension.** The name must end in `.pdf` or `.docx` (case-insensitive) → else
   422 `"<name>: only pdf and docx documents are allowed"`.
3. **Size.** Read at most `document_max_bytes + 1` bytes. More → 413
   `"<name>: file is larger than 10 MB"` (the number comes from the setting). Zero
   bytes → 422 `"<name>: file is empty"`.
4. **Content.**
   - pdf: the bytes start with `%PDF-`.
   - docx: `zipfile.ZipFile(io.BytesIO(data))` opens (a `BadZipFile` → invalid) and
     its `namelist()` contains `[Content_Types].xml` and `word/document.xml`. Only the
     member list is read; nothing is decompressed (no zip-bomb risk).
   - The detected type must match the extension → else 422
     `"<name>: content is not a valid pdf"` / `"… docx"`.
5. The stored `content_type` is the canonical one for the detected type; the
   client's `Content-Type` header is ignored.

The number of files is checked before any file: more than `document_max_files` → 422
`"Too many files: at most 10 per request"`; none → 422 `"No files were sent"`. For
`PUT`, anything other than exactly one `file` part → 422
`"Exactly one file is required"`.

### Reading the body only after access is checked

FastAPI reads a form declared as route parameters (`files: list[UploadFile]`) with
`await request.form()` **before** it runs any dependency, `CurrentUser` and the access
check included. Starlette keeps each file part in a `SpooledTemporaryFile` (1 MB in
memory, then on disk). So with form parameters, a caller without a token, or an
outsider, could make the server parse and spool up to the request limit before getting
401/404.

Therefore the two upload routes do **not** declare the files as parameters. They take
`request: Request`, run `CurrentUser` and the project access check first (as
dependencies or as the first service call), and only then call
`request.form(max_files=…, max_fields=…)` themselves. Swagger still shows the file
pickers through `openapi_extra` (a `multipart/form-data` request body with a `files`
array of binary strings for `POST`, one binary `file` for `PUT`). The form is closed
after use. Order inside a request: token (401) → project or document access (404) →
form parsing → validation (422/413).

Form-level errors that cannot reach the service (a body that is not valid multipart)
answer 422 and are only possible after the access check.

### Request size guard

A small pure ASGI middleware (`documents/upload_limit.py`) runs only for
`POST /project/{id}/documents` and `PUT /document/{id}`, before anything else:

- no `Content-Length` header → **411** `{"detail": "Content-Length is required"}`;
- `Content-Length` above `document_max_files × document_max_bytes + 1 MiB` (form
  overhead) for `POST`, or `document_max_bytes + 1 MiB` for `PUT` → **413**
  `{"detail": "Request is too large"}`;
- the body is not read in both cases. A client that lies about `Content-Length`
  cannot send more than it announced: the ASGI server stops at the declared length.

These two answers come before the token check (a 2 GB request without a token gets
413, not 401); a request of normal size without a token gets 401 as usual. The
per-file check in validation stays; it gives the precise message. Demo note: when the
server answers 413 early while a browser is still sending a big body, the browser may
show a connection reset instead of the 413; the per-file 413 (a file just above the
per-file limit but below the request limit) always shows properly, so the demo uses
that one.

### Service and access rules (`documents/service.py`)

All functions take `uow`, `storage`, the current `User` (and `Settings` where the
limits are needed). Access goes through `projects.service.get_project`, so outsiders
and unknown ids get exactly the same 404 as in epic 4.

| Function | Order of steps |
|---|---|
| `list_documents(project_id)` | `get_project` (404 `Project not found`) → `list_for_project` |
| `upload_documents(project_id, files)` | `get_project` → validate **all** files → `put` each to S3 under a new key, one after another → `add` each row → `touch` project → commit → log `document uploaded` per document. If any `put` fails: delete the keys already put, 503. If a database step or the commit fails: delete all put keys, re-raise |
| `download_document(document_id)` | `get` → `None` → 404 `Document not found`; `get_project(document.project_id)` → its `NotFoundError` is turned into 404 `Document not found` → `storage.get` |
| `replace_document(document_id, file)` | access as in download → validate → `put` under a new key → `replace_file` → `touch` → commit → log `document replaced` → delete the **old** key. If `put` fails: 503, nothing changed. If the database fails: delete the new key, re-raise. If deleting the old key fails: still 200, a WARNING is logged |
| `delete_document(document_id)` | access as in download → `delete` → `touch` → commit → log `document deleted` → delete the key. If the S3 delete fails: still 204, WARNING |
| `documents_for(project_ids)` | `list_for_projects`; used by `GET /projects` |

Form parsing and validation run **after** the access check (see
[Reading the body only after access is checked](#reading-the-body-only-after-access-is-checked)),
so an outsider learns nothing about the project from validation errors. A participant has exactly the same rights as the
owner for documents (roadmap roles).

**Project delete** (`projects/service.delete_project`, the epic 4 seam, now also takes
`storage`): access and owner check as before → `keys =
uow.documents.storage_keys_for_project(id)` → `uow.projects.delete(id)` (cascade
removes the rows) → commit → log `project deleted` → `storage.delete(keys)`. If the S3
delete fails, the answer is still 204 and a WARNING `document files left in storage`
is logged with `project_id` and the keys, so they can be removed by hand. The reverse
order (S3 first) was rejected: a failed commit would leave rows pointing to deleted
files.

**Security log:** logger `project_hub.documents.service`, INFO, one record per
document with `event`, `login`, `user_id`, `project_id`, `document_id` (message text
and `extra`, as in `projects.service`). The file name is not logged (user content).
Storage cleanup failures are WARNING records with `project_id` and the keys.

### API

All routes need `Authorization: Bearer <token>`; without a valid token 401 with
`WWW-Authenticate: Bearer`, as before. `project_id` / `document_id` are UUID path
parameters: anything else gives 422.

| Route | Request | Success | Errors |
|---|---|---|---|
| `GET /project/{id}/documents` | — | 200, `list[DocumentResponse]`, newest first | 404 |
| `POST /project/{id}/documents` | multipart, field `files` (1–10 files) | 201, `list[DocumentResponse]` in the order sent | 404, 411, 413, 422, 503 |
| `GET /document/{id}` | — | 200, the file bytes | 404, 503 |
| `PUT /document/{id}` | multipart, field `file` (exactly one) | 200, `DocumentResponse` | 404, 411, 413, 422, 503 |
| `DELETE /document/{id}` | — | 204, no body | 404 |

**`DocumentResponse`:**

```json
{
  "id": "…",
  "project_id": "…",
  "name": "thesis.docx",
  "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "size": 482113,
  "uploaded_by": {"id": "…", "login": "anna"},
  "created_at": "2026-11-15T10:00:00Z",
  "updated_at": "2026-11-15T10:00:00Z"
}
```

`uploaded_by` is `null` when the uploader no longer exists.

**Download headers:** `Content-Type` = the stored content type;
`Content-Disposition: attachment; filename="<ASCII fallback>"; filename*=UTF-8''<percent-encoded name>`
(RFC 6266 / 5987, so names like `диплом.pdf` survive and quotes or newlines cannot
break the header); `Content-Length`; `X-Content-Type-Options: nosniff`;
`Cache-Control: private, no-store`. The whole file (≤ 10 MB) is read into memory and
sent; no streaming.

**`GET /projects`:** `ProjectListItem.documents` becomes `list[DocumentResponse]`
(today `list[dict[str, Any]]`, always `[]`). The field name and its place stay as in
epic 4, so nothing the frontend already uses changes. All documents of each listed
project are included; the page of projects (`limit` ≤ 100) bounds the response.

### Local infrastructure

`docker-compose.yml`:

- `s3`: image `motoserver/moto:5.2.5`, port `127.0.0.1:${APP_S3_PORT:-55435}:5000`
  (loopback only, like `db`), a healthcheck.
- `storage-init`: the app image running `python -m project_hub.storage.create_bucket`,
  after `s3` is healthy; like `migrate`, it exits 0.
- `api`: gets `APP_S3_BUCKET=${APP_S3_BUCKET:-project-hub-documents}`,
  `APP_S3_ENDPOINT_URL=http://s3:5000`, `APP_S3_REGION`, the dummy
  `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` (`test`), and waits for `storage-init`
  to complete.
- moto keeps files in memory: they disappear when the `s3` container stops. That is
  acceptable for local work; it is stated in the README. Postgres rows then point to
  missing files → download answers 503; `docker compose down -v` resets both.

`.env.example`: the new `APP_S3_*`, `APP_DOCUMENT_*` and `APP_S3_PORT` lines, the
dummy-credentials note, and `TEST_S3_ENDPOINT_URL` for the tests.

CI (`.github/workflows/ci.yml`): job `checks` gets a `motoserver/moto:5.2.5` service
container on port 5000 and `TEST_S3_ENDPOINT_URL=http://localhost:5000` plus the dummy
credentials. Job `docker` needs nothing new (compose brings `s3` up itself).

### Tests and fixtures

- Session fixture `s3_endpoint_url` from `TEST_S3_ENDPOINT_URL` (default
  `http://localhost:55435`); if the emulator does not answer, the run **fails** with a
  clear message (like the database), it never skips.
- The tests never use the developer's own AWS credentials: an autouse fixture sets
  `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` to `test`, and points
  `AWS_SHARED_CREDENTIALS_FILE` and `AWS_CONFIG_FILE` at an empty file, and clears
  `AWS_PROFILE`/`AWS_SESSION_TOKEN`.
- Fixture `storage_bucket`: a fresh bucket `project-hub-test-<random>` per test
  session, emptied and deleted at the end. `api_client` passes it in its settings;
  after each test the bucket is emptied (like `truncate_tables`).
- Storage tests (`tests/storage/`) run against moto through `S3FileStorage`.
  "Storage unavailable" is produced for real: a storage pointed at a bucket that does
  not exist, or at a closed port.
- Test files are built in the tests: a minimal valid pdf (`%PDF-1.4 …`) and a minimal
  docx made with `zipfile` (`[Content_Types].xml` + `word/document.xml`), plus bad
  ones (PNG bytes named `.pdf`, a zip without `word/document.xml`, an empty file).
- The Docker smoke test brings the stack up, registers, logs in, creates a project,
  uploads a pdf and downloads it, and compares the bytes.

### Docs

README: a "Documents" section (routes, access, limits and their settings, validation,
download headers, the all-or-nothing rule, what happens on storage failures, log
events), `s3` and `storage-init` in the Docker table, the `0004` row in the migrations
table, the new settings, and the future-improvements list below. Roadmap: the frontend
requests rows (metadata → done, download → done, CORS → not needed), the "Deferred to
implementation" upload row answered, and the LocalStack note replaced by moto with the
reason.

Shared notes folder: `epic-6-documents-notes-for-frontend.md` (one file per request,
download through `fetch` + blob, error codes and messages, duplicates allowed,
`uploaded_by` may be `null`) and a hand-over note for epics 7a/7b (key layout, the
`FileStorage` Protocol, moto).

## Acceptance criteria

API tests go through `TestClient` against `create_app` with the real test Postgres
and the moto bucket, once per backend (`orm`, `sql`). "Outsider" = a logged-in user who
is neither owner nor participant; a participant is added with the epic 4 helper.

Upload — `POST /project/{id}/documents`

1. Given the owner and one valid pdf, when posted, then 201 with one document:
   `name`, `content_type == "application/pdf"`, `size` equal to the bytes sent,
   `uploaded_by` the caller, `created_at == updated_at`; the bytes are in the bucket
   under a key starting with `projects/<project_id>/documents/`.
2. Given a pdf and a docx in one request, then 201 with two documents in the order
   sent, each with its canonical content type.
3. Given a participant, then the same as 1, with `uploaded_by` the participant.
4. Given an outsider or an unknown project id, then 404 `Project not found` —
   identical for both, also when the files are invalid — and nothing is stored in the
   bucket or the database.
5. Given a batch where one file is bad (wrong extension, `.pdf` with PNG bytes, a zip
   named `.docx` without `word/document.xml`, an empty file, a control character in the
   name), then 422 with a message naming that file, and **no** file of the batch is in
   the bucket or the database.
6. Given a file of `document_max_bytes + 1` bytes (the test sets a small limit), then
   413 with a message naming the file, nothing stored.
7. Given more than `document_max_files` files, then 422 `Too many files: at most N per
   request`, nothing stored; given no files, then 422.
8. Given a file name with a path (`../../etc/x.pdf`, `C:\\tmp\\x.pdf`), then the
   document's `name` is `x.pdf` and the S3 key does not contain it.
9. Given the same file name twice in a project, then both documents exist.
10. Given the storage is unavailable, then 503 `File storage is unavailable` and no
    document row exists.
11. A request without `Content-Length` gets 411; a request whose `Content-Length` is
    above the limit gets 413 before the body is read (the test proves the route never
    ran: no row, nothing in the bucket).
12. A successful upload logs one INFO `document uploaded` per document with login,
    user id, project id and document id, without the file name.

List — `GET /project/{id}/documents`

13. Given owner or participant, then 200 with the project's documents, newest first,
    and none of another project's documents.
14. Given a project without documents, then `[]`; outsider or unknown id, then 404
    `Project not found`.

Download — `GET /document/{id}`

15. Given owner or participant, then 200, the exact bytes uploaded, the stored
    `Content-Type`, `Content-Disposition: attachment` with the name (a non-ASCII name
    round-trips through `filename*`), `X-Content-Type-Options: nosniff`.
16. Given an outsider or an unknown id, then 404 `{"detail": "Document not found"}`,
    identical for both.
17. Given the file is missing from the bucket, then 503.

Replace — `PUT /document/{id}`

18. Given owner or participant and a valid file, then 200 with the same `id` and
    `created_at`, the new `name`, `size`, `content_type`, `uploaded_by` = caller and a
    later `updated_at`; downloading returns the new bytes; the old S3 object is gone.
19. A pdf can be replaced by a docx and the other way round.
20. Given an outsider or unknown id, then 404 `Document not found`, nothing changes.
21. Given an invalid file (rules of 5–6), then 422/413, the document and its old file
    are unchanged.
22. Given the storage is unavailable, then 503 and the document is unchanged.
23. A replace logs one INFO `document replaced` with login, user id, project id and
    document id.

Delete — `DELETE /document/{id}`

24. Given owner or participant, then 204 with an empty body; afterwards download is
    404, the document is gone from the list, and its S3 object is gone.
25. Given an outsider or unknown id, then 404 `Document not found`, nothing deleted.
26. A delete logs one INFO `document deleted` with login, user id, project id and
    document id.
27. If the S3 delete fails after the row is deleted, the answer is still 204 and a
    WARNING with the key is logged.

Projects

28. `GET /projects` returns every listed project with `documents` holding exactly that
    project's documents (same shape as the list endpoint, newest first), `[]` for a
    project without documents, using one document query for the whole page.
29. Uploading, replacing or deleting a document moves its project to the top of
    `GET /projects` (`updated_at` changes).
30. `DELETE /project/{id}` by the owner removes the project's document rows and all of
    their S3 objects; other projects' objects stay. If the S3 delete fails, the answer
    is still 204 and a WARNING `document files left in storage` names the keys.
31. A participant's `DELETE /project/{id}` is still 403 and no document or file is
    touched.

Auth

32. Every document route without a token, or with an invalid one, answers 401 with
    `WWW-Authenticate: Bearer`; a non-UUID id gives 422.
32a. An upload (`POST` and `PUT`) without a token, or by an outsider, answers 401/404
    without the form being parsed (the test proves it: a body that is not valid
    multipart still gets 401/404, not 422).

Repository contract (both backends)

33. `add` returns a `Document` with generated `id`, timezone-aware timestamps and the
    uploader's login; `get` returns it; `get` of an unknown id is `None`.
34. `list_for_project` orders `created_at DESC, id DESC`; `list_for_projects` returns
    an entry for every requested id, `[]` included.
35. `replace_file` changes the five fields and `updated_at`, keeps `created_at`,
    returns `None` for an unknown id; a read in the same Unit of Work sees the change.
36. `delete` returns the deleted row, then `get` is `None`; unknown id → `None`.
37. `storage_keys_for_project` returns the keys of exactly that project.
38. `add` with an unknown project id raises and the Unit of Work stays usable.
39. Deleting the project removes its document rows (cascade); deleting the uploader
    sets `uploaded_by` to `None`.
40. `ProjectRepository.touch` changes `updated_at`. Nothing is stored without
    `commit()`.

Storage (`S3FileStorage` against moto)

41. `put` then `get` returns the same bytes; `delete` removes several keys at once,
    accepts an empty list and keys that do not exist.
42. On a missing bucket or an unreachable endpoint, `put`, `get` and `delete` raise
    `StorageUnavailableError`; `get` of a missing key raises it too.
43. `create_bucket` creates a missing bucket and is a no-op when it exists.

Migration

44. `upgrade` creates `documents` with the columns, constraints and index above;
    `downgrade` to `0003` removes it and keeps `projects`; upgrade → downgrade →
    upgrade works; the head is `0004`.
45. The database rejects an empty name, a 256-character name, an unknown content type
    and `size = 0` (`CHECK`).
46. The ORM models match the migrated schema (`compare_metadata` is empty).

Settings

47. `APP_DOCUMENT_MAX_BYTES` and `APP_DOCUMENT_MAX_FILES` change the limits the API
    enforces; values outside their ranges are rejected at startup; blank
    `APP_S3_BUCKET` / `APP_S3_ENDPOINT_URL` count as unset.

Docker and checks

48. `docker compose up --wait` brings up `db`, `s3`, `api` (and `migrate`,
    `storage-init` exit 0); a document uploaded through the running stack downloads
    with the same bytes (Docker smoke test). The `s3` port is bound to `127.0.0.1`
    only (`docker compose config` in verification).
49. `poetry check --lock`, `ruff check`, `ruff format --check`, `pyright` (strict) and
    the full `pytest` (both backends, and `-m docker`) are green locally and in CI.

## Future improvements

Recorded so they are not proposed again by accident.

| Improvement | Why not now |
|---|---|
| Rename a document without replacing the file (`PATCH /document/<id>`) | Postponed by the user |
| Automatic rename of a duplicate name (`thesis (1).docx`) | Postponed by the user; needs a free-number search that is safe under concurrent uploads |
| Streaming upload and download | Not needed under a 10 MB limit; worth it if the limit grows |
| Presigned download URLs | Would unload the API for big files; needs bucket CORS |
| A job that removes orphaned S3 objects (after a failed cleanup) | Failures are logged with the keys; rare in a course project |
| Paging of documents inside `GET /projects` | A course project has a handful of documents per project |
| Real S3 in tests | Only at the cloud checkpoints (epic 8) |

Rejected: version history (user, 2026-11-15); refusing duplicate names with 409
(user, 2026-11-15).

## Calls made while writing this design

Settled without changing what gets built; listed so the user can check them.

- `uploaded_by … ON DELETE SET NULL` instead of `RESTRICT`.
- Storage failures → 503 `File storage is unavailable`; a failed *cleanup* after a
  successful commit never fails the request, it logs a WARNING with the keys.
- New exception `PayloadTooLargeError` → 413; `StorageUnavailableError` → 503; 411 for
  a missing `Content-Length` on the two upload routes.
- `python-multipart` becomes a dependency (FastAPI needs it for forms); `boto3` a
  dependency; `boto3-stubs[s3]` a dev dependency.
- Settings ranges: `document_max_bytes` 1 … 100 MiB, `document_max_files` 1 … 100.
- The existing test `test_upgrade_twice_is_noop` expects head `0003` and is updated to
  `0004`; the existing smoke test `test_compose_stack_serves_health` expects exactly
  `{db, api}` running and is updated to include `s3`; the existing project-delete and
  `GET /projects` tests keep passing unchanged. These are the only existing tests that
  change.
- `delete_project` gains a `storage` parameter; its router passes it.
- The upload routes read the form themselves after the access check, documented for
  Swagger with `openapi_extra` (builder check finding: FastAPI parses form parameters
  before dependencies).
- `PUT` with zero or several `file` parts → 422 `Exactly one file is required`.
- `motoserver/moto:5.2.5` exists on Docker Hub (published 2026-10-27).
- A document's `project_id` never changes (no moving documents between projects).
- When the storage is not configured (`APP_S3_BUCKET` unset), the app still starts;
  document routes and project delete answer 500 like routes without a database.

## Left to the builder

- Exact names of helpers, test files and fixtures.
- The SQL of `list_for_projects` (`= ANY(%s)` or a join), as long as it is one query.
- How the ASCII fallback for `filename=` is built (for example replace non-ASCII and
  `"\` with `_`).
- The moto healthcheck command and the bucket fixture details.
- Whether validation reads the `UploadFile` with `await file.read(n)` or through its
  spooled file, as long as no more than `max_bytes + 1` bytes are read per file.
