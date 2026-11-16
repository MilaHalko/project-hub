# Epic 7a: Size and quota Lambda

Date: 2026-11-16
Status: approved design (2026-11-16)
Roadmap: [`docs/PRDs/roadmap.md`](../../PRDs/roadmap.md), epic 7a, the "Notes" under
[AWS cost strategy](../../PRDs/roadmap.md#aws-cost-strategy), and the frontend request
"Used space and limit per project in project responses"
Spec: [`docs/initial-spec.md`](../../initial-spec.md) — "AWS Lambda functions (for image
processing, size calculations on s3 event)", "S3+Lambda: … calculation of sum of project
file's size and apply limit", "Normalization + denormalization of db tables"
Builds on: [epic 6 design](2026-11-15-documents-s3-design.md) (storage keys
`projects/<project_id>/documents/<hex>`, upload/replace/delete flows),
[epic 8a design](2026-11-15-terraform-infra-design.md) (two Terraform layers)

## Intent

Every project gets a storage limit, and everyone who opens a project sees how much of it
is used ("18 of 50 MB" in the web app). The used total is a denormalized column on the
project row, so reading a project never sums its documents. An S3 event triggers a Lambda
that recomputes the total from the files really stored in S3, which is the spec's
"S3+Lambda: calculation of sum of project file's size". The API refuses an upload or a
replacement that would push the project over its limit.

At the defense this must be easy to show and explain: upload until the limit, see the
`413`, see the number in every project response, and explain why the API and the Lambda
both write the total (below).

## Goals

- `projects.storage_used_bytes` (denormalized total) and a guard timestamp, new migration
  `0006`, backfilled from the existing documents.
- A per-project limit as a setting, `APP_PROJECT_MAX_BYTES`, like `document_max_bytes`.
- Upload (`POST /project/<id>/documents`) and replace (`PUT /document/<id>`) that would go
  over the limit are refused with `413` and a clear message; nothing is stored.
- `storage_used_bytes` and `storage_limit_bytes` in **every** project response.
- The Lambda handler, its own tests against real Postgres and S3 (moto), and a run of the
  built zip inside AWS's Lambda runtime image.
- Terraform for the Lambda and its wiring, proven by `terraform validate`, `tflint` and
  `checkov`. Nothing is applied by the agent.
- Both data backends (`orm`, `sql`) read and write the new columns; shared contract tests
  cover them.

## Non-goals

- Different limits for different projects (a column with a per-project override). The
  limit is the same setting for all projects; "per project" means it applies to each
  project's total.
- A user-wide quota.
- Cleaning up orphaned S3 files.
- Running the Lambda in local docker compose (see [Testing](#testing-without-aws)).

## Anti-goals

- An upload that the API accepted being undone later by the Lambda. The Lambda only
  writes a number; it never deletes or refuses anything.
- A project response that ever lacks the two fields (the web app hides the bar when they
  are missing, so a missing field silently breaks it).
- AWS keys in any file, and any `terraform apply` or `destroy` by the agent.

## Constraints

- `.github/workflows/deploy.yml` is not changed. Lambda build/test steps go in a separate
  CI job in `ci.yml`.
- The frontend (`frontend/`) is not changed in this PR.
- Persistent layer stays near free; anything billed by the hour goes to the ephemeral
  layer.
- Region `eu-west-1`, all names derive from `project-hub` (AWS account rules in the
  roadmap).
- Docker ports bind to `127.0.0.1` only.

## Approaches

Who writes `storage_used_bytes`:

1. **Lambda only.** Purest "S3 event → Lambda → denormalized total". But the number lags
   behind every change, and locally and in CI nothing runs the Lambda (below), so the
   number would never change there and the web app could not show the bar refreshing.
2. **API only, no Lambda.** Simple and exact, but drops the spec's S3 + Lambda part.
3. **API and Lambda (chosen).** The API sets the total from the `documents` table in the
   same transaction as every upload, replace and delete, so the number is right at once,
   everywhere. The Lambda recomputes it from the objects really in S3 on every S3 event,
   so a file that changes outside the API (console, a failed delete that left a file) is
   counted too. Both writers stamp the time their figure was taken; a write older than
   the stored stamp is ignored, so a late Lambda run cannot overwrite a newer number.

The user picked 3 (2026-11-16).

## Decisions

### Data

- Migration `0006` adds to `projects`:
  - `storage_used_bytes BIGINT NOT NULL DEFAULT 0`, check `>= 0`;
  - `storage_counted_at TIMESTAMPTZ NULL` (when the figure was taken);
  - backfill: `storage_used_bytes = COALESCE(SUM(documents.size), 0)`,
    `storage_counted_at = now()`.
  The downgrade drops both columns.
- `Project` (domain entity) gains `storage_used_bytes: int`. Both repositories select it
  everywhere they build a `Project` (`add`, `get_for_user`, `list_for_user`, `update`).
- `ProjectRepository` gains one method, used by the API:
  `refresh_storage_used(project_id) -> int` sets
  `storage_used_bytes = (SELECT COALESCE(SUM(size), 0) FROM documents WHERE project_id = …)`
  and `storage_counted_at = now()`, and returns the new total.
- The quota check needs the current total under a lock:
  `lock_storage_used(project_id) -> int | None` runs
  `SELECT … FROM projects WHERE id = … FOR UPDATE` and returns
  `COALESCE(SUM(documents.size), 0)` for that project (from `documents`, not from the
  column, because the column may hold a Lambda figure that includes stray S3 files).
  `None` when the project does not exist.
- Both methods exist in the ORM and the SQL repository; the shared contract tests cover
  them on both backends.

### Limit and enforcement

- Setting `project_max_bytes` (`APP_PROJECT_MAX_BYTES`), default `52_428_800` (50 MiB),
  `ge=1`, `le=10_737_418_240` (10 GiB). Documented in `.env.example` and README next to
  the other document limits.
- Upload: inside the transaction, before writing anything to S3, the service calls
  `lock_storage_used`, adds the sizes of all files in the request, and if the sum is above
  `project_max_bytes` raises `PayloadTooLargeError` → `413`, detail
  `"Project storage limit reached: <used> of <limit> used, this upload needs <n> more"`
  (sizes in the same human text as the per-file message). The project row stays locked
  until commit, so two parallel uploads cannot both pass the check.
- Replace: same, with `used − old size + new size`. A replacement that does not grow the
  project is never refused, even if the project is already over the limit (for example
  after the limit was lowered).
- Delete is never refused.
- After the document rows change, the service calls `refresh_storage_used` before commit
  (upload, replace, delete). Project delete needs nothing.
- The check is equal-to allowed: a project may be exactly at its limit.

### API fields

- `ProjectResponse` gains `storage_used_bytes: int` and `storage_limit_bytes: int`
  (the setting). `ProjectListItem` inherits them, and `JoinResponse.project` is a
  `ProjectResponse`, so every project response has them: `POST /projects`,
  `GET /projects`, `GET|PUT /project/<id>/info`, `GET /join`.
- The limit comes from settings at response time, so changing the setting changes every
  response at once.

### The Lambda

- Code: `src/project_hub/storage_usage/` (handler module `project_hub.storage_usage.handler`,
  function `handler(event, context)`). It imports only the standard library, `boto3` and
  `psycopg`, never the FastAPI app, so the zip stays small.
- Trigger: EventBridge events from the documents bucket, `detail-type` `Object Created` or
  `Object Deleted`, key prefix `projects/`. An EventBridge rule sends them to an SQS
  queue, and the Lambda reads the queue (event source mapping, batch up to 10, batching
  window 2 s, `maximum_concurrency = 2`). The handler gets SQS records whose body is the
  EventBridge event, takes the project id from `projects/<uuid>/documents/…`, and counts
  each project once per batch. Any other key, or a malformed body, is logged and
  ignored (not retried).
- Work: list the objects under `projects/<project_id>/documents/` (`ListObjectsV2`,
  paginated), sum their sizes, then
  `UPDATE projects SET storage_used_bytes = %s, storage_counted_at = %s WHERE id = %s
  AND (storage_counted_at IS NULL OR storage_counted_at < %s)`, with the time taken just
  before the listing. A project that no longer exists updates nothing; that is normal
  after a project delete.
- A failure while counting one project (database or S3 error) is reported back through
  the event source mapping's partial batch response (`batchItemFailures`), so only that
  project's messages are retried. After 5 receives a message goes to a dead-letter queue.
- Settings from environment: `APP_DATABASE_URL` or, in AWS, `APP_DATABASE_URL_PARAMETER`
  (the SSM name `/project-hub/database-url`, read once per cold start with decryption),
  `APP_S3_ENDPOINT_URL` (tests only), `APP_S3_REGION`.
- Logs: one structured line per run (`storage usage counted project_id=… bytes=…`), and a
  warning for ignored keys.

### Infrastructure

- **Persistent layer** (always up, free):
  - bucket notifications go to EventBridge (`aws_s3_bucket_notification` with
    `eventbridge = true`). One notification config per bucket is all S3 allows, so 7a and
    7b each add their own EventBridge rule instead of fighting over it.
  - an S3 **gateway** VPC endpoint on the private route table (free), so the Lambda in the
    private subnets reaches S3.
  - a security group `project-hub-storage-usage` (egress 5432 to the db group, 443 to
    the VPC CIDR for the endpoint) and a db ingress rule from it.
  - the Lambda's IAM role: `s3:ListBucket` on the bucket with prefix `projects/*`,
    `ssm:GetParameter` on `/project-hub/database-url`, `kms:Decrypt` through SSM only,
    VPC ENI permissions (`AWSLambdaVPCAccessExecutionRole`), logs to its own log group.
  - its CloudWatch log group, 14 days like the API's.
- **Ephemeral layer** (only with RDS up):
  - the Lambda function (`project-hub-storage-usage`, Python 3.13, arm64, 256 MB, 30 s
    timeout), in the private subnets with the new security group;
  - the SQS queue `project-hub-storage-usage` (SQS-managed encryption, visibility
    timeout 180 s, six times the Lambda timeout) and its dead-letter queue (14 days), the
    EventBridge rule with the queue as target, the queue policy that lets only that rule
    send, and the event source mapping with `maximum_concurrency = 2`;
  - an SSM **interface** endpoint in the private subnets (about $0.01 an hour per
    subnet), so the Lambda can read the database URL. Only in the ephemeral layer to keep
    the persistent layer free.
  - The Lambda reads `/project-hub/database-url`, which the ephemeral layer already
    writes for ECS.
- Why ephemeral: the Lambda only makes sense while RDS exists, and the roadmap says the
  7a Lambda is tested in the cloud only with the ephemeral layer up.

### Packaging and CI

- `scripts/build_storage_usage_lambda.sh` builds `dist/storage-usage-lambda.zip`:
  `pip install --platform manylinux2014_aarch64 --python-version 3.13 --only-binary=:all:
  --target <dir> psycopg[binary]==<locked version>`, then copies
  `src/project_hub/storage_usage/`. `boto3` comes from the Lambda runtime. The psycopg
  version is read from `poetry.lock`, so the zip and the tests use the same one.
- Terraform takes the zip path as a variable (`storage_usage_zip`, default
  `../../dist/storage-usage-lambda.zip`). The owner runs the script before
  `terraform apply`; `infra/README.md` says so.
- New CI job `lambda` in `ci.yml` (not touching `deploy.yml` or the existing jobs'
  steps): builds the zip, uploads it as an artifact, and runs the Lambda smoke test
  (below) against Postgres and moto services. It runs on `ubuntu-24.04-arm` (free for
  public repositories), so the arm64 zip runs natively in the arm64 Lambda image, as it
  does on the owner's Apple silicon laptop.
- The existing `terraform` job keeps running `fmt`, `validate`, `tflint`, `checkov`,
  `test`. If validate needs the zip to exist, the job builds it first (a step added at
  the start of that job).

### Testing without AWS

Lambda emulation re-checked, as the roadmap asks:

- moto's Lambda backend runs functions in Docker containers, which the moto server
  container cannot do without the Docker socket; LocalStack needs an auth token since
  2026.03. Neither is used.
- AWS's own base image `public.ecr.aws/lambda/python:3.13` includes the Runtime Interface
  Emulator: it runs the built zip as a real Lambda and takes invocations over HTTP. This
  is the smoke test.

Tests:

- **Handler tests** (`tests/storage_usage/`): call `handler(event, None)` with real-shaped
  SQS events carrying EventBridge events, against the test Postgres and the moto S3
  server. Cover: created and deleted events, a project with no files left, an unknown
  project, a key outside `projects/`, a malformed body, several events of one project in
  one batch, a stale write that must not overwrite a newer figure, more than 1000 objects
  (pagination), and a failure reported in `batchItemFailures`.
- **Contract tests** for `refresh_storage_used`, `lock_storage_used` and the new field,
  on both backends.
- **API tests** through `TestClient`: the fields in every project response, the upload
  and replace refusals, exact-limit acceptance, the total after upload, replace and
  delete, and a replace that shrinks a project already over the limit.
- **Migration test**: `0006` backfills existing projects and downgrades cleanly.
- **Lambda smoke test** (marker `lambda_package`, run by the CI job `lambda`): build the
  zip, run it in the Lambda base image, invoke it with an event, and check the number in
  Postgres.

## Beyond the spec

- **Stale-write guard** (`storage_counted_at`): needed, because two writers and
  out-of-order events would otherwise show a wrong total. Accepted as part of the
  approved design.
- **A queue between EventBridge and the Lambda** (builder's call, 2026-11-16, replacing
  the reserved concurrency of the first draft): a project delete fires one event per file,
  and each run opens a database connection. Reserved concurrency would cap that, but AWS
  refuses any reservation on accounts whose Lambda quota is still the new-account 10, so
  the ephemeral apply could fail at the checkpoint. The SQS event source mapping's
  `maximum_concurrency = 2` caps the load without reserving anything, batches the events
  of one project into one count, and gives retries and a dead-letter queue. SQS is free
  at this volume.
- Postponed: per-project limit overrides, orphaned-file cleanup, a "storage" summary for
  all of a user's projects (the roadmap's "Totals for the projects list", already "later").

## Left to the builder

- Exact message text for the 413, as long as it names used, limit and the needed size.
- Module layout inside `storage_usage/` and helper names.
- How the smoke test starts the Lambda container (testcontainers-free; the project uses
  plain `docker` CLI helpers in `tests/support/docker.py`).
- Checkov skips for findings that cost money (customer KMS keys, X-Ray, DLQ, code signing),
  each with a one-line reason, in the style of the existing skips.

## What the owner applies in AWS

1. Build the zip: `scripts/build_storage_usage_lambda.sh`.
2. `terraform -chdir=infra/persistent apply` (EventBridge on the bucket, S3 endpoint,
   security group, IAM role, log group).
3. At a checkpoint, `terraform -chdir=infra/ephemeral apply` creates the Lambda, its rule
   and the SSM endpoint with the rest of the layer; `destroy` removes them.
4. Check: upload a document, then see `storage used counted` in the log group
   `/aws/lambda/project-hub-storage-usage`.
