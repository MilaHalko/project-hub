# Size and Quota Lambda Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every project carries a denormalized storage total and a limit; the API refuses
uploads and replacements over the limit; an S3 → EventBridge → SQS → Lambda path recounts
the total from S3.

**Architecture:** Migration `0006` adds the total and a "counted at" stamp to `projects`.
The document service locks the project row, checks the limit, and refreshes the total in
the same transaction as every document change. A standalone Lambda module (stdlib,
`boto3`, `psycopg` only) lists the project's S3 objects and writes the total unless a newer
figure is stored. Terraform wires the bucket to EventBridge (persistent) and the rule,
queue, Lambda and SSM endpoint (ephemeral).

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, psycopg 3, Alembic, boto3, moto server,
pytest, Docker (`public.ecr.aws/lambda/python:3.13`), Terraform 1.17.2, tflint 0.66.0,
checkov 3.4.5, GitHub Actions.

**Spec:** [`docs/superpowers/specs/2026-11-16-size-quota-lambda-design.md`](../specs/2026-11-16-size-quota-lambda-design.md)

## Global Constraints

- Response fields: `storage_used_bytes: int`, `storage_limit_bytes: int`, in every project response.
- Setting: `project_max_bytes` (`APP_PROJECT_MAX_BYTES`), default `52_428_800`, `ge=1`, `le=10_737_418_240`.
- Columns: `projects.storage_used_bytes BIGINT NOT NULL DEFAULT 0` with check `ck_projects_storage_used_non_negative` (`storage_used_bytes >= 0`); `projects.storage_counted_at TIMESTAMPTZ NULL`.
- Migration revision `"0006"`, down revision `"0005"`, file `0006_add_projects_storage_used.py`.
- Refusal: `PayloadTooLargeError` → HTTP 413. A project may be exactly at its limit.
- Lambda module imports only the standard library, `boto3`, `botocore` and `psycopg`; never `project_hub.core`, FastAPI, pydantic or SQLAlchemy.
- Lambda resource names: function, queue, log group, role and security group all `project-hub-storage-usage` (log group `/aws/lambda/project-hub-storage-usage`), DLQ `project-hub-storage-usage-dlq`.
- Never edit `.github/workflows/deploy.yml`; never touch `frontend/`; never run `terraform apply`/`destroy`; never handle AWS keys.
- Docker ports bind to `127.0.0.1` only.
- Every repository change lands in both `repository_orm.py` and `repository_sql.py` and in the shared contract tests.
- Comments/docstrings: none by default (see `CLAUDE.md` "Comments"); never delete existing ones.
- Commits: one vertical slice per commit, plain-words subject (no `feat:` prefix), 1–3 line body, **no `Co-Authored-By` trailer**.
- Checks before every commit: `poetry run ruff check`, `poetry run ruff format --check`, `poetry run pyright`, and the task's tests. Services: `docker compose up -d --wait db s3 mail`.

## Review Focus

1. **Two uploads at once near the limit** — the second must wait for the first and then be refused if it no longer fits. Test: contract test in Task 3 (second `lock_storage_used` blocks until the first transaction ends).
2. **Limit lowered below current usage** — responses show `used > limit`, deletes still work, a replace that does not grow the file still works. Test: Task 3 `test_replace_that_shrinks_is_allowed_over_the_limit`.
3. **Many files, each small, together over the limit** — the whole request is refused and no file is left in S3. Test: Task 3 `test_upload_over_limit_stores_nothing`.
4. **Events arriving after the project was deleted** — the Lambda updates nothing and reports no failure. Test: Task 4 `test_unknown_project_is_not_a_failure`.
5. **Out-of-order Lambda runs** — an older count never overwrites a newer one (API or Lambda). Test: Task 4 `test_older_count_does_not_overwrite_newer`.

---

### Task 1: Every project response shows its used space and limit

**Files:**
- Create: `src/project_hub/db/migrations/versions/0006_add_projects_storage_used.py`
- Modify: `src/project_hub/projects/models.py` (two columns + check constraint on `ProjectModel`)
- Modify: `src/project_hub/projects/entities.py` (`Project.storage_used_bytes: int`)
- Modify: `src/project_hub/projects/repository_orm.py`, `repository_sql.py` (select the column wherever a `Project` is built)
- Modify: `src/project_hub/core/config.py` (`project_max_bytes`)
- Modify: `src/project_hub/projects/schemas.py`, `projects/router.py`, `shares/schemas.py`, `shares/router.py` (pass the limit)
- Modify: `.env.example`, `README.md` (setting next to `APP_DOCUMENT_MAX_BYTES`), `tests/conftest.py` (`APP_PROJECT_MAX_BYTES` in `_clean_env`)
- Test: `tests/db/test_migrations.py`, `tests/projects/test_repository_contract.py`, `tests/projects/test_create_api.py`, `tests/projects/test_info_api.py`, `tests/shares/test_join_api.py`

**Interfaces:**
- Produces: `Project.storage_used_bytes: int`; `Settings.project_max_bytes: int`;
  `ProjectResponse.from_access(access: ProjectAccess, storage_limit_bytes: int) -> ProjectResponse`;
  `ProjectListItem.from_access(access: ProjectAccess, storage_limit_bytes: int, documents: Sequence[Document] = ()) -> ProjectListItem`.

- [ ] **Step 1: Write the failing tests**
  - `test_migrations.py::test_0006_backfills_storage_used`: at `0005`, insert a user, two projects, documents of sizes 100 and 250 on the first; upgrade to head; first project has `storage_used_bytes == 350` and non-null `storage_counted_at`, second has `0`.
  - `test_migrations.py::test_storage_used_rejects_negative`: insert with `storage_used_bytes = -1` raises `CheckViolation`.
  - `test_migrations.py::test_downgrade_to_0005_drops_storage_columns`: both columns gone.
  - Contract (both backends): `test_new_project_has_no_storage_used` — `add(...)`, `get_for_user`, `list_for_user`, `update` all return `storage_used_bytes == 0`.
  - API: `test_create_api.py` — **extend the existing `set(body) == {...}` assertion** with `"storage_used_bytes"` and `"storage_limit_bytes"`, and add `test_create_shows_storage_fields` (`== 0` and `== 52_428_800`).
  - API: `test_info_api.py::test_info_shows_limit_from_settings` — client built with `IsolatedSettings(project_max_bytes=1000)`, `GET /project/<id>/info` → `storage_limit_bytes == 1000`.
  - API: `test_join_api.py::test_join_project_has_storage_fields` — both keys present in `body["project"]`.
- [ ] **Step 2: Run them and see them fail** — `poetry run pytest tests/db/test_migrations.py tests/projects tests/shares -q` → failures on the missing columns/keys.
- [ ] **Step 3: Implement** the migration (add columns, check constraint, `UPDATE projects p SET storage_used_bytes = COALESCE((SELECT SUM(size) FROM documents d WHERE d.project_id = p.id), 0), storage_counted_at = now()`), the model, the entity field, both repositories, the setting, the schema fields and every `from_access` call site (settings come from `request.app.state.settings`, as in `documents/router.py`).
- [ ] **Step 4: Run the full suite** — `poetry run pytest -q` → all pass (both backends).
- [ ] **Step 5: Commit** — `Show each project's used space and storage limit`

### Task 2: Used space follows uploads, replacements and deletes

**Files:**
- Modify: `src/project_hub/projects/repository.py`, `repository_orm.py`, `repository_sql.py` (`refresh_storage_used`)
- Modify: `src/project_hub/documents/service.py` (call it before every document-changing commit)
- Test: `tests/projects/test_repository_contract.py`, `tests/documents/test_upload_api.py`, `test_replace_api.py`, `test_delete_api.py`

**Interfaces:**
- Consumes: Task 1 columns and `Project.storage_used_bytes`.
- Produces: `ProjectRepository.refresh_storage_used(project_id: UUID) -> int` — sets
  `storage_used_bytes = COALESCE(SUM(documents.size), 0)` for that project and
  `storage_counted_at = now()`; returns the new total (0 for an unknown project, no error).

- [ ] **Step 1: Write the failing tests**
  - Contract: `test_refresh_storage_used_sums_documents` — two documents (sizes 10, 20) → returns `30`, `get_for_user(...).project.storage_used_bytes == 30`; after deleting one → `20`.
  - API: upload two files → `GET /project/<id>/info` `storage_used_bytes` equals the sum of their sizes; replace one with a bigger file → total follows; delete → total drops; `GET /projects` item shows the same number.
- [ ] **Step 2: Run and see them fail.**
- [ ] **Step 3: Implement** the method in both repositories and call `uow.projects.refresh_storage_used(project_id)` right before `uow.projects.touch(...)` in `upload_documents`, `replace_document`, `delete_document`.
- [ ] **Step 4: Run** `poetry run pytest -q` → all pass.
- [ ] **Step 5: Commit** — `Keep a project's used space in step with its documents`

### Task 3: Uploads and replacements over the project limit are refused

**Files:**
- Modify: `src/project_hub/projects/repository.py`, `repository_orm.py`, `repository_sql.py` (`lock_storage_used`)
- Modify: `src/project_hub/documents/service.py` (check before any `storage.put`), `src/project_hub/documents/validation.py` (make the size-text helper public as `size_text` if reused)
- Modify: `src/project_hub/documents/router.py` (pass `settings.project_max_bytes` to the service)
- Modify: `README.md` (limit rule in the documents section)
- Test: `tests/projects/test_repository_contract.py`, `tests/documents/test_quota_api.py` (new)

**Interfaces:**
- Consumes: Task 2 `refresh_storage_used`.
- Produces: `ProjectRepository.lock_storage_used(project_id: UUID, *, except_document: UUID | None = None) -> int | None` — `SELECT … FOR UPDATE` on the project row, returns the sum of document sizes in the project excluding `except_document`; `None` if the project does not exist.
  `upload_documents(uow, storage, user, project_id, files, *, limit_bytes: int)` and `replace_document(uow, storage, user, document, file, *, limit_bytes: int)`.
- Message (exact): `f"Project storage limit reached: {size_text(used)} of {size_text(limit)} used, this upload needs {size_text(incoming)}"`.

- [ ] **Step 1: Write the failing tests**
  - Contract: `test_lock_storage_used_excludes_document`; `test_lock_storage_used_unknown_project_is_none`; `test_second_lock_waits_for_first_transaction` (two units of work; the second `lock_storage_used` does not return within 0.5 s while the first is open, and returns after the first commits).
  - API (`IsolatedSettings(project_max_bytes=N)` with small test files):
    - `test_upload_up_to_the_limit_is_accepted` (exactly `N`);
    - `test_upload_over_limit_is_refused` → 413, detail starts with `"Project storage limit reached"`;
    - `test_upload_over_limit_stores_nothing` — several files each under the limit, together over it → 413, no new rows, no new S3 objects under the project prefix;
    - `test_replace_over_limit_is_refused` → 413, old file still downloadable;
    - `test_replace_that_shrinks_is_allowed_over_the_limit` — lower the limit below current use (new client with smaller setting), replace with a smaller file → 200;
    - `test_delete_is_allowed_over_the_limit` → 204.
- [ ] **Step 2: Run and see them fail.**
- [ ] **Step 3: Implement** — upload: `lock_storage_used(project_id)` first, refuse if `used + sum(len(f.data)) > limit`, then the existing put/add flow. Replace: `lock_storage_used(project_id, except_document=document.id)`, refuse if `others + new > limit and new > document.size`, and move `storage.put` after the check, inside the `try`.
- [ ] **Step 4: Run** `poetry run pytest -q` → all pass.
- [ ] **Step 5: Commit** — `Refuse uploads and replacements over the project storage limit`

### Task 4: The Lambda recounts a project's used space from S3

**Files:**
- Create: `src/project_hub/storage_usage/__init__.py` (empty), `src/project_hub/storage_usage/handler.py`
- Create: `tests/storage_usage/__init__.py`, `tests/storage_usage/test_handler.py`, `tests/support/storage_usage.py` (event builders)
- Modify: `README.md` (short "Storage usage Lambda" section: what triggers it, its env vars)

**Interfaces:**
- Consumes: Task 1 columns.
- Produces: `handler(event: Mapping[str, Any], context: object) -> dict[str, list[dict[str, str]]]` returning `{"batchItemFailures": [{"itemIdentifier": <messageId>}, …]}`;
  `project_id_from_key(key: str) -> UUID | None` (only `projects/<uuid>/documents/<anything non-empty>`);
  env: `APP_DATABASE_URL` or `APP_DATABASE_URL_PARAMETER` (SSM name, `WithDecryption=True`, cached per cold start), `APP_S3_ENDPOINT_URL` (optional), `APP_S3_REGION` (default `eu-west-1`).
- SQL (exact): `UPDATE projects SET storage_used_bytes = %s, storage_counted_at = %s WHERE id = %s AND (storage_counted_at IS NULL OR storage_counted_at < %s)`; the stamp is `datetime.now(UTC)` taken just before listing.
- Event shape: SQS event `{"Records": [{"messageId": …, "body": json.dumps(eventbridge_event)}]}`; EventBridge event `{"detail-type": "Object Created" | "Object Deleted", "source": "aws.s3", "detail": {"bucket": {"name": …}, "object": {"key": …}}}`.

- [ ] **Step 1: Write the failing tests** (real test Postgres via `migrated_database_url`, real moto S3 bucket fixture):
  - `test_created_event_stores_sum_of_objects`;
  - `test_deleted_event_counts_what_is_left` (and zero when nothing is left);
  - `test_one_count_per_project_per_batch` (three records, one project → one listing; assert via the result only, e.g. stamp set once and correct total);
  - `test_unknown_project_is_not_a_failure` → `batchItemFailures == []`, no row changed;
  - `test_key_outside_projects_is_ignored` and `test_malformed_body_is_ignored` → no failure, no change;
  - `test_older_count_does_not_overwrite_newer` (row stamped in the future → unchanged);
  - `test_more_than_1000_objects_are_counted` (1001 tiny objects);
  - `test_database_error_reports_the_messages_of_that_project` (unreachable database URL → every message id of the project in `batchItemFailures`).
- [ ] **Step 2: Run and see them fail** — `poetry run pytest tests/storage_usage -q`.
- [ ] **Step 3: Implement** `handler.py` (group records by project id, list with the `list_objects_v2` paginator on `projects/<id>/documents/`, one `psycopg.connect` per invocation, `autocommit=True`, structured log line `storage usage counted` with `project_id` and `bytes`).
- [ ] **Step 4: Run** `poetry run pytest -q` and `poetry run pyright` → pass.
- [ ] **Step 5: Commit** — `Recount a project's used space from S3 in a Lambda handler`

### Task 5: Build the Lambda zip and prove it runs in the AWS Lambda runtime

**Files:**
- Create: `scripts/build_storage_usage_lambda.sh` (args: output zip path, default `dist/storage-usage-lambda.zip`)
- Create: `tests/storage_usage/test_lambda_package.py` (marker `lambda_package`)
- Modify: `pyproject.toml` (marker `lambda_package` registered; `addopts` excludes it like `docker` and `package`)
- Modify: `.github/workflows/ci.yml` — **new job `lambda` only** (no edits to existing jobs except the `terraform` job if Task 6 needs the zip)
- Modify: `README.md` (how to build the zip and run `pytest -m lambda_package`), `.gitignore` if `dist/` is not already ignored

**Interfaces:**
- Consumes: Task 4 `project_hub.storage_usage.handler.handler`.
- Produces: zip at `dist/storage-usage-lambda.zip` containing `project_hub/__init__.py`, `project_hub/storage_usage/*.py`, and `psycopg` + `psycopg_binary` for `manylinux2014_aarch64`, Python 3.13, version read from `poetry.lock`.

- [ ] **Step 1: Write the failing smoke test** — builds the zip into `tmp_path`, unzips it, runs `public.ecr.aws/lambda/python:3.13` with the folder mounted read-only at `/var/task`, CMD `project_hub.storage_usage.handler.handler`, `-p 127.0.0.1:0:8080`, `--add-host=host.docker.internal:host-gateway`, env pointing the database and S3 endpoint at `host.docker.internal`; uploads an object for a test project, POSTs an SQS event to `/2015-03-31/functions/function/invocations`, asserts `{"batchItemFailures": []}` and the stored total. Container is removed in a `finally` (reuse `tests/support/docker.py` helpers).
- [ ] **Step 2: Run and see it fail** — `poetry run pytest -m lambda_package -v` → script missing.
- [ ] **Step 3: Implement** the script (`pip install --platform manylinux2014_aarch64 --implementation cp --python-version 3.13 --only-binary=:all: --target …`), the marker, the CI job (`runs-on: ubuntu-24.04-arm`, services postgres + moto as in `checks`, steps: checkout, Poetry, setup-python, `poetry install`, build the zip, upload artifact `storage-usage-lambda`, `poetry run pytest -m lambda_package -v`). Pin action SHAs exactly as the existing jobs do.
- [ ] **Step 4: Run** `poetry run pytest -m lambda_package -v` locally → pass; `poetry run pytest -q` → still excludes it.
- [ ] **Step 5: Commit** — `Build the storage usage Lambda zip and run it in the Lambda runtime`

### Task 6: Terraform delivers S3 events to the Lambda

**Files:**
- Modify (persistent): `infra/persistent/s3.tf` (`aws_s3_bucket_notification` with `eventbridge = true`; remove the `CKV2_AWS_62` skip), `network.tf` (S3 gateway endpoint on the private route table), `security.tf` (group `project-hub-storage-usage`: egress 5432 → db group, 443 → VPC CIDR; db ingress from it), `iam.tf` (role + policy), new `lambda.tf` or in `iam.tf` (log group 14 days), `outputs.tf` if useful
- Modify (ephemeral): new `infra/ephemeral/storage_usage.tf` (function, SQS queue + DLQ, queue policy, EventBridge rule + target, event source mapping, SSM interface endpoint + its security group), `lookup.tf` (data sources for the role, the security group, the bucket via SSM `/project-hub/s3-bucket`), `variables.tf` (`storage_usage_zip`, default `"../../dist/storage-usage-lambda.zip"`)
- Modify: `infra/README.md` (build the zip before the ephemeral apply; how to check the log group), `.github/workflows/ci.yml` (`terraform` job: only if validate needs the zip, add a first step that builds it)

**Interfaces:**
- Consumes: Task 5 zip path; handler `project_hub.storage_usage.handler.handler`; env `APP_DATABASE_URL_PARAMETER=/project-hub/database-url`, `APP_S3_REGION`.
- Values (exact): runtime `python3.13`, architectures `["arm64"]`, memory 256, timeout 30; queue visibility timeout 180, DLQ retention 1209600, `maxReceiveCount` 5; ESM `batch_size = 10`, `maximum_batching_window_in_seconds = 2`, `scaling_config { maximum_concurrency = 2 }`, `function_response_types = ["ReportBatchItemFailures"]`; rule pattern `{"source": ["aws.s3"], "detail-type": ["Object Created", "Object Deleted"], "detail": {"bucket": {"name": [<bucket>]}, "object": {"key": [{"prefix": "projects/"}]}}}`.
- IAM (least privilege): `s3:ListBucket` on the bucket with condition `s3:prefix` like `projects/*`; `ssm:GetParameter` on `/project-hub/database-url`; `sqs:ReceiveMessage`, `sqs:DeleteMessage`, `sqs:GetQueueAttributes` on the queue ARN (built from name); logs to its log group; managed `AWSLambdaVPCAccessExecutionRole`.

- [ ] **Step 1: Write the failing `terraform test`** in `infra/persistent/tests/storage_usage.tftest.hcl` (plan-only with mocked provider, like the existing tests): the storage-usage security group allows ingress from nothing and egress only on 5432 to the db group and 443 to the VPC CIDR; the db group accepts 5432 from it.
- [ ] **Step 2: Run** `terraform -chdir=infra/persistent test` (via `hashicorp/terraform:1.17.2` Docker image if not installed) → fails.
- [ ] **Step 3: Write the Terraform** for both layers.
- [ ] **Step 4: Prove it** — for both layers: `terraform fmt -check -recursive infra`, `terraform init -backend=false && terraform validate`, `tflint --recursive --config "$PWD/infra/.tflint.hcl" --chdir infra`, `checkov` with the same arguments as the CI job, `terraform test` → all clean. Every new checkov skip has a one-line reason in the existing style. Use Docker images `hashicorp/terraform:1.17.2`, `ghcr.io/terraform-linters/tflint:v0.66.0`, `bridgecrew/checkov:3.4.5` when the binaries are not installed.
- [ ] **Step 5: Commit** — `Deliver S3 document events to the storage usage Lambda in AWS`

### Task 7: Roadmap and PR

**Files:** `docs/PRDs/roadmap.md` (row 7a ✅ with the PR number; frontend request "Used space and limit per project" → `done`; deferred table untouched), `docs/frontend/roadmap.md` is **not** touched.

- [ ] **Step 1:** Full verification (Phase 5 of `add-feature`).
- [ ] **Step 2: Commit** — `Mark epic 7a size and quota as done in the roadmap` (after the PR number is known).
