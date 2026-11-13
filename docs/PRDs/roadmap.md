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
| 0.5 | Poetry migration | Build backend `poetry-core`, `poetry.lock` replaces `uv.lock`, README and `CLAUDE.md` switch from uv to Poetry | 0 |
| 1a | Docker and Postgres | `Dockerfile`, `docker-compose` with Postgres, test database setup, `core/exceptions.py` (domain errors → JSON with proper status codes) | 0.5 |
| 1b | Data layer | Repository and Unit of Work protocols, SQLAlchemy and psycopg implementations, migrations, `APP_DB_BACKEND` switch, shared contract tests | 1a |
| 2 | CI | GitHub Actions: lint, type check, tests for both DB backends, image build | 1b |
| 8a | Terraform infrastructure | Persistent and ephemeral layers (see [AWS cost strategy](#aws-cost-strategy)) | 2 |
| 8b | Deploy on merge | Push the image to ECR on every merge; deploy to ECS when the ephemeral layer is up | 8a |
| 3 | Users and auth | `POST /auth`, `POST /login`, password hashing, JWT valid for 1 hour, current-user dependency | 1b |
| 4 | Projects and access | Project CRUD, owner/participant roles, access checks on every request, owner-only delete | 3 |
| 5 | Invites | `POST /project/<id>/invite?user=<login>`, owner only | 4 |
| 6 | Documents and S3 | Upload, download, update and delete documents; delete files with the project | 4 |
| 7a | Lambda: size and quota | S3 event → Lambda sums the project's file sizes into a denormalized total → per-project limit | 6 |
| 7b | Lambda: image resize | S3 event → Lambda resizes images | 6 |
| 9 | Package | Build the package with Poetry in CI | 2 |
| 10 | Email share and join | `GET /project/<id>/share?with=<email>`, hashed token, `GET /join` | 5 |

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

- Daily development is local: Postgres in `docker-compose`, S3 and Lambda
  emulated with LocalStack.
- CI always pushes the image to ECR (persistent layer). The ECS deploy step runs
  only when the ephemeral layer is up, controlled by a repository variable, so
  merges do not fail while it is destroyed.
- The 7a Lambda writes to the database, so it is tested in the cloud only with
  the ephemeral layer up. The 7b Lambda works S3 → S3 and can be tested in the
  persistent layer.
- Destroy rather than stop: a stopped RDS instance restarts by itself after 7
  days, and an idle load balancer is still billed.

## AWS sandbox rules

The cloud is a course-provided AWS sandbox. Its usage agreement adds hard rules;
breaking one terminates the sandbox and deletes everything in it.

- **Regions:** only `us-east-1`, `eu-west-1` and `ap-south-1` are open. We use
  `eu-west-1`.
- **No company name:** the course provider's company name must not appear
  anywhere in the sandbox: account name, resource names, tags, DNS records,
  certificates, HTTP headers or page content, service banners. All names derive
  from `project-hub`. The GitHub repository was renamed to `project-hub` for the
  same reason (it shows up in the GitHub OIDC trust policy).
- **No corporate email** for anything in the sandbox: AWS Budgets alerts, SES
  senders or recipients (epic 10), registrations.
- **Certificates:** only self-generated or AWS-issued (ACM).
- **Scope:** only actions the project needs. Every action is logged.
- **Limited lifespan:** when the sandbox expires, everything in it is deleted
  with no recovery, the persistent layer included. So:
  - all infrastructure must come back with `terraform init && terraform apply`
    from this repository;
  - nothing exists only in the sandbox: configuration and secrets have a source
    outside it, and the Terraform state is never kept only in the sandbox;
  - data in RDS and S3 is demo data, never the only copy of anything.
- **Budget:** exceeding the sandbox budget terminates it. The AWS Budgets alert
  in the persistent layer must fire well below that limit.

Open questions for the mentors (answers go here, decided by 8a at the latest):

| Question | Affects |
|---|---|
| Sandbox lifespan and expiry date | 8a, checkpoint planning |
| Budget limit | 8a (Budgets alert threshold) |
| Are IAM roles and a GitHub OIDC identity provider allowed? If not, CI uses access keys stored as GitHub secrets | 8a, 8b |
| Where may the Terraform state live (S3 backend in the sandbox, or outside it)? | 8a |

## Other constraints

- **GitHub plan:** the repository is private on the free plan, so branch
  protection (blocking a merge while CI is red) is not available. A red CI must
  be fixed before merging by discipline.
- **What to test:** see "What to test" in `CLAUDE.md`. Tests prove behaviour;
  tooling and configuration are proven by commands that really run them.

## Deferred to implementation

| Question | Decided in |
|---|---|
| Upload path: through the API or presigned S3 URL | 6 |
| Which images exist for the resize Lambda (documents are only pdf and docx) | 7b |
| Email share details | 10 |
| How a browser user authenticates on `GET /join` (JWT is sent in a header, which a clicked link does not carry) | 10 |
