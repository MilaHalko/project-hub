# Roadmap

Date: 2026-11-11
Status: agreed

High-level epics for implementing [`docs/initial-spec.md`](../initial-spec.md).
Each epic gets its own PRD in this folder and its own branch and PR.

## Ground rules

- **The spec is the source of truth.** If `CLAUDE.md` or any other file
  contradicts it, the spec wins and the other file gets fixed.
- **Everything marked optional in the spec is mandatory**: the email share link
  (`GET /project/<id>/share` + `GET /join`) and S3 + Lambda image resize.
- **Endpoint names stay exactly as in the spec.**
- **The spec is the floor, not the ceiling.** The goal is the best app we can
  build and defend, not the minimum. Every epic looks for additions that are
  necessary, convenient or expected in a real product, that are not hard, and
  that the user can explain at the defense: new endpoints (logout, change
  password, `GET /users/me`), useful checks, small UX or security
  improvements. Rules:
  - an addition never breaks or renames anything the spec defines, and never
    breaks a hard rule (spec, AWS account rules, "What to test");
  - the agent **proposes, argues and asks**: for each addition say what it is,
    why it matters (for users, security or the defense), what it costs (files,
    endpoints, migrations, tests), and recommend yes or no. The user decides;
    nothing beyond the spec is built without her yes;
  - rejected or postponed additions are written down in the epic's design doc
    with the reason, so they are not proposed again by accident.
- **Access roles:** the owner can do anything; a participant can do everything
  except delete the project (participants may add, update and delete documents
  and update project info). Inviting stays owner-only, as in the spec.

## Stack decisions

| Area | Decision |
|---|---|
| Packaging and tooling | Poetry (no tox), ruff, pyright, pytest |
| ORM implementation | SQLAlchemy 2.0 (async, `postgresql+psycopg` driver) |
| Non-ORM implementation | psycopg 3 with plain SQL |
| Infrastructure as code | Terraform |
| Runtime | ECR + ECS Fargate + RDS PostgreSQL + S3 + Lambda |
| CI/CD | GitHub Actions |

### Swappable data layer

The ORM and non-ORM implementations must be interchangeable:

- Each aggregate has a repository `Protocol`; services depend only on it.
- ORM objects never leave the repository: it returns domain models.
- Transactions go through a Unit of Work, also a `Protocol` with two
  implementations. It lives outside `core/` (for example `project_hub/db/`),
  because it imports repositories from feature modules.
- The backend is picked by a setting (`APP_DB_BACKEND`, `orm` or `sql`) with a
  test that rejects typos.
- One shared contract test suite runs against both implementations; CI runs
  both.
- The schema comes from hand-written migrations, independent of ORM models.
- Every epic that touches the database implements both repositories.

## Epics

| # | Epic | Scope | Depends on |
|---|---|---|---|
| 0 | ✅ Skeleton | FastAPI app, settings, `GET /health`, lint, type check, tests | — |
| 0.5 | ✅ Poetry migration (PR #1) | Build backend `poetry-core`, `poetry.lock` replaces `uv.lock`, README and `CLAUDE.md` switch from uv to Poetry | 0 |
| 1a | ✅ Docker and Postgres (PR #2) | `Dockerfile`, `docker-compose` with Postgres, test database setup, `core/exceptions.py` (domain errors → JSON with proper status codes) | 0.5 |
| 1b | ✅ Data layer (PR #3) | Repository and Unit of Work protocols, SQLAlchemy and psycopg implementations, migrations, `APP_DB_BACKEND` switch, shared contract tests | 1a |
| 2 | ✅ CI (PR #4) | GitHub Actions: lint, type check, tests for both DB backends, image build | 1b |
| 8a | ✅ Terraform infrastructure (PR #28) | Persistent and ephemeral layers (see [AWS cost strategy](#aws-cost-strategy)); extras: HTTPS on the ALB with a self-signed certificate, monthly and daily budget emails, `terraform test` guards for the security groups and the main-only GitHub OIDC trust, CI job `terraform` (fmt, validate, tflint, checkov, test), checkpoint runbook in `infra/README.md` | 2 |
| 8b | ✅ Deploy on merge (PR #41) | Push the image to ECR on every merge; deploy to ECS when the ephemeral layer is up | 8a |
| 3 | ✅ Users and auth (PR #8) | `POST /auth`, `POST /login`, password hashing, JWT valid for 1 hour, current-user dependency; extras: `POST /logout`, `GET /users/me`, `PUT /users/me/password`, security events log | 1b |
| 4 | ✅ Projects and access (PR #13) | Project CRUD, owner/participant roles, access checks on every request, owner-only delete; extras: `GET /projects` sorted by last update with `limit`/`offset` and `role` filter, `GET /project/<id>/members`, project created/deleted in the security events log | 3 |
| 5 | ✅ Invites (PR #17) | `POST /project/<id>/invite?user=<login>`, owner only; extras: `DELETE /project/<id>/members/<user_id>` (the owner removes a participant, a participant leaves), participant invited/removed/left in the security events log | 4 |
| 6 | ✅ Documents and S3 (PR #21) | Upload, download, update and delete documents; delete files with the project; extras: `GET /project/<id>/documents`, documents in `GET /projects` items, pdf/docx checked by content, size and count limits as settings, document changes in the security events log, S3 on moto locally and in CI | 4 |
| 7a | ✅ Lambda: size and quota (branch `feat/lambda-size-quota`) | S3 event → Lambda sums the project's file sizes into a denormalized total → per-project limit; the API keeps the total in step in the same transaction and refuses uploads and replacements over `APP_PROJECT_MAX_BYTES` with 413 under a project-row lock; `storage_used_bytes` and `storage_limit_bytes` in every project response; S3 → EventBridge → SQS → Lambda (at most 2 at once, DLQ); the zip runs in the real Lambda image in tests and in CI job `lambda` ([design](../superpowers/specs/2026-11-16-size-quota-lambda-design.md)) | 6 |
| 7b | Lambda: image resize | S3 event → Lambda resizes images | 6 |
| 9 | ✅ Package (PR #33) | Build the package with Poetry in CI; the wheel is installed into a clean virtualenv and proven to start, serve `GET /health` and migrate a real Postgres; extras: sdist rebuild check, `project-hub-migrate` command, package metadata, CI job `package` uploading the built files as an artifact | 2 |
| 10 | ✅ Email share and join (PR #36) | `GET /project/<id>/share?with=<email>`, hashed token, `GET /join`; a single-use link valid 7 days (only its SHA-256 hash stored), owner only, a repeat share replaces the link, at most 10 pending links per project, a browser without a token is sent to the web app's sign-in; extras: SMTP mail caught by Mailpit locally and in CI, share and join in the security events log, join tokens hidden in the access log | 5 |

Pydantic validation and JWT authorization are not separate epics: they are part
of every epic from 3 on.

## Order and parallel work

```
0.5 → 1a → 1b → 2 → 8a → 8b
                ↓
                3 → 4 ─┬→ 5 → 10
                       └→ 6 ─┬→ 7a
                             └→ 7b
9: any time after 2
```

- Deploy (epic 8) comes early, while the app only has `/health`, so every later
  epic ships to the cloud and infrastructure problems surface while the code is
  small.
- After epic 4 the branches `5 → 10` and `6 → 7a / 7b` are independent and can
  run in parallel sessions. Epic 9 is independent too.

## AWS cost strategy

Terraform is split into two layers.

**Persistent layer** — free or near free, always up:

- VPC, subnets, security groups, IAM roles
- ECS cluster (no running tasks)
- ECR, S3
- Lambda functions
- SSM Parameter Store for configuration and secrets (not Secrets Manager,
  which bills per secret)
- AWS Budgets alert

**Ephemeral layer** — paid, created only for a checkpoint and destroyed right
after it:

- RDS PostgreSQL
- Application Load Balancer
- ECS service with running tasks
- Public IPv4 addresses

Checkpoints (`terraform apply` → deploy → verify → `terraform destroy`):

1. After epic 8: the deploy pipeline works end to end.
2. After epic 4: auth and projects on real RDS.
3. After epics 6 and 7: real S3 events and Lambdas.
4. Final demo for the mentor.

Notes:

- Daily development is local: Postgres in `docker-compose`, S3 emulated with
  moto server locally and in CI (LocalStack needs an auth token since 2026.03,
  and agents never handle keys). Epics 7a/7b re-check Lambda emulation.
- CI always pushes the image to ECR (persistent layer). The ECS deploy step runs
  only when the ephemeral layer is up, controlled by a repository variable, so
  merges do not fail while it is destroyed.
- The 7a Lambda writes to the database, so it is tested in the cloud only with
  the ephemeral layer up. The 7b Lambda works S3 → S3 and can be tested in the
  persistent layer.
- Destroy rather than stop: a stopped RDS instance restarts by itself after 7
  days, and an idle load balancer is still billed.

Email share in AWS (from [epic 10](../superpowers/specs/2026-11-16-share-join-design.md#for-the-aws-epics-8a-8b);
nothing is built for it yet):

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

## AWS account rules

Decided in epic 8a (2026-11-15, see its
[design](../superpowers/specs/2026-11-15-terraform-infra-design.md)). The course
sandbox is not used: the cloud is the user's personal AWS account on the AWS
Free plan, paid from its credits. The sandbox rules that cost nothing are kept.

- **Region:** `eu-west-1`.
- **No company name:** the course provider's company name never appears in
  resource names, tags, DNS records, certificates, HTTP headers or page content.
  All names derive from `project-hub`. The GitHub repository was renamed to
  `project-hub` for the same reason (it shows up in the GitHub OIDC trust
  policy).
- **No corporate email:** AWS Budgets alerts, SES senders or recipients
  (epic 10) and registrations use the user's personal address, kept only in
  git-ignored `terraform.tfvars`.
- **Certificates:** only self-generated or AWS-issued (ACM). The ALB uses a
  self-signed certificate imported into ACM.
- **Recreatable:** all infrastructure comes back with
  `terraform init && terraform apply` from this repository. The Terraform state
  lives on the user's laptop, git-ignored; data in RDS and S3 is demo data,
  never the only copy of anything.
- **CI access:** GitHub OIDC, trusted only for `main` of
  `MilaHalko/project-hub`; no AWS access keys in GitHub secrets.
- **Budget:** $20 a month (emails at 50 %, 80 %, 100 % and forecast) and $1 a
  day, both counting cost before credits, so a forgotten ephemeral layer is
  noticed on the first day.
- **Free plan:** AWS keeps some services off the Free plan; the first real
  `apply` shows whether ECS Fargate and ALB are allowed. Upgrading to the paid
  plan is the user's decision.

## Other constraints

- **Protected `main`:** the ruleset `protect-main` (empty bypass list) blocks
  deleting `main` and force pushes, and allows changes only through a pull
  request whose required checks `checks` and `docker` are green. Approvals are
  not required and the branch does not have to be up to date before merging.
  Every change to `main`, documentation included, goes through a PR.
- **What to test:** see "What to test" in `CLAUDE.md`. Tests prove behaviour;
  tooling and configuration are proven by commands that really run them.

## Frontend requests

The project has a web frontend beyond the spec: a React app in its own nginx
container that proxies the API under `/api/`, so the API itself does not change
for it. Its plan lives apart from this roadmap, in
[`docs/frontend/`](../frontend/README.md) (design, epics F0–F6, style). This
section lists what the frontend needs from the API, so each API epic sees it
when it starts. An API epic that picks up a request treats it like any other
addition: propose, argue, and the user decides; a rejected or postponed request
is written down in that epic's design doc and its status updated here.

Status: **proposed** (nobody has agreed yet), **accepted** (the API epic will
build it), **done** (merged), **later** (postponed).

| Request | Why the frontend needs it | API epic | Frontend epic | Status |
|---|---|---|---|---|
| `GET /project/<id>/members` → `[{id, login, role, joined_at}]`, owner first, then participants in join order; no paging; same access rule as `GET /project/<id>/info` (404 without access, 401 without a token) | The project page shows a members panel; the info response has only `owner` and `my_role` | 4 (addition #9 of its design) | F3 | done |
| `users.avatar` (name of a preset icon, nullable) and `PATCH /users/me` accepting only known names; also in member and owner objects | Users pick a preset avatar that others see | a backend task with `add-feature`, before F1b (after 4: migration order) | F1b | accepted |
| `users.display_name`: optional, nullable, up to 50 characters, no control characters, not unique; an optional field at `POST /auth` (the spec's `login`/`password`/`repeat_password` unchanged) and changeable through the same `PATCH /users/me` as the avatar; also in the `owner` object and `GET /project/<id>/members` | `login` is the unique handle for sign-in and invites (`POST /project/<id>/invite?user=<login>`), not a person's name; the UI shows "Anna Petrenko (@anna)" | a backend task with `add-feature`, before F1b (together with `users.avatar`, one `users` migration; final decision in that task) | F1b | proposed |
| Document metadata includes size, content type and upload date | The documents list shows them | 6 | F4 | done |
| Decide how `GET /document/<id>` downloads: file through the API or a presigned S3 URL | A clicked link cannot carry the `Authorization` header; the frontend adapts to either | 6 | F4 | done: through the API |
| If uploads go straight to S3 with presigned URLs: a bucket CORS rule for the app's origin, and the bucket origin in the app's CSP `connect-src` | The browser calls S3 directly | 6, 8a | F4 | not needed |
| Used space and limit per project in project responses | The used-space bar; hidden until these fields exist, no stub | 7a | F4 | done: `storage_used_bytes`, `storage_limit_bytes` |
| The mail links to the API `GET /join?token=…`. Without `Authorization` and with `Accept: text/html`, a browser gets `303` to `<APP_WEB_URL>/join?token=…`; the web page calls `/api/join?token=…` with the Bearer header and gets `{login, already_member, project}`. nginx must hide `token` in its access log | A clicked email link carries no JWT | 10 | F5 | accepted |
| HTTPS on the ALB: own domain with ACM, self-signed, or HTTP for the demo only | Passwords and tokens in plain text otherwise (Swagger too) | 8a | — | accepted (self-signed certificate in ACM, HTTP redirects to HTTPS) |
| Totals for the projects list (projects, documents, space) | Summary counters above the list; `GET /projects` has no total count | — | — | later |
| `DELETE /users/me` answering 409 "Delete your projects first" while the user owns projects | Account deletion dialog that never fails silently | after 6 | — | later |
| Upload of one's own avatar picture | Custom avatars beyond the presets | — | — | later |

## Deferred to implementation

| Question | Decided in |
|---|---|
| Upload path: through the API or presigned S3 URL | decided in 6: through the API |
| Which images exist for the resize Lambda (documents are only pdf and docx) | 7b |
| Email share details | decided in 10: owner only, a single-use link valid 7 days (only its SHA-256 hash stored), a repeat share replaces the link, at most 10 pending links per project, SMTP mail caught by Mailpit locally and in CI ([design](../superpowers/specs/2026-11-16-share-join-design.md)) |
| How a browser user authenticates on `GET /join` | decided in 10: the mail keeps the API link; a browser without `Authorization` and with `Accept: text/html` gets `303` to the web app's `/join?token=…` (needs `APP_WEB_URL`), which signs in and then calls `GET /join` with the Bearer header | 10 |
