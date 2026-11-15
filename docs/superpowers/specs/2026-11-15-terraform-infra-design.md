# Epic 8a: Terraform infrastructure on AWS

Date: 2026-11-15
Status: approved design (user, 2026-11-15)
Roadmap: [`docs/PRDs/roadmap.md`](../../PRDs/roadmap.md), epic 8a, "AWS cost strategy"

## Goal

The whole cloud side of the backend is code in this repository: one
`terraform apply` builds it in an empty AWS account, one `terraform destroy`
removes it. It is split into two layers so that the account costs almost
nothing between checkpoints:

- **persistent**: free or near free, always up;
- **ephemeral**: billed by the hour, created for a checkpoint and destroyed
  right after it.

Spec: "AWS S3", "AWS Lambda", "CI/CD ... pushing to registry/deploy to cloud on
merge request". Pushing images and deploying from CI are epic 8b; this epic
builds what 8b pushes to and deploys onto.

## Context that changed

- **No course sandbox.** The target is the user's **personal AWS account** on
  the AWS Free plan (about $178 of credits). It is her money, so cost guards
  matter more than in the sandbox plan. The sandbox rules are kept where they
  cost nothing: names derive from `project-hub`, the course provider's company
  name never appears in names, tags, DNS, certificates, headers or pages, and
  alerts go to her personal address.
- The roadmap section "AWS sandbox rules" and its open questions for the
  mentors are rewritten in this epic to match (see "Roadmap changes").
- Free plan caveat: AWS keeps some services off the Free plan. No official list
  says whether ECS Fargate or ALB are among them; RDS `db.t4g.micro` is
  reported as available. Only the first real `apply` proves it. If AWS refuses
  a service, upgrading to the paid plan is the user's decision.

## Goals, non-goals, anti-goals

Goals:
- Every resource from the roadmap's cost strategy, in `eu-west-1`.
- Nothing secret in git; nothing secret in the Terraform state where Terraform
  can avoid it.
- Least privilege for every IAM role; the database never reachable from the
  internet; the S3 bucket never public.
- Offline checks that really run Terraform and its linters, locally and in CI.

Non-goals (other epics):
- Pushing the image to ECR and deploying on merge: **8b**.
- Lambda functions and S3 event notifications: **7a / 7b** add them to the
  persistent layer.
- The web frontend in the cloud: its own task after frontend epic F6 (see
  `docs/frontend/roadmap.md`); it needs an nginx config change under
  `frontend/`, which this epic must not touch.
- Running `terraform apply` / `destroy`: the user does it at checkpoints.

Anti-goals (a failure even if everything "works"):
- A forgotten ephemeral layer silently billing for days.
- A `destroy` at a checkpoint that also deletes images, the bucket or the roles.
- Any change in AWS made by an agent.

## Approaches

| Option | Trade-off | Decision |
|---|---|---|
| **A. Two root folders, `infra/persistent` and `infra/ephemeral`, each with its own state** | Two `init`s and two state files; a `destroy` in `ephemeral` physically cannot touch the persistent resources; matches the roadmap's two layers one to one | **Chosen** (user, 2026-11-15) |
| B. One folder with a switch `ephemeral = true/false` | One state, one command; but a stray `terraform destroy` removes everything, and the layers exist only as conditions in the code | Rejected |
| C. Terraform workspaces | Workspaces are for copies of the same infrastructure, not for two different sets | Rejected |

Plain `resource` blocks, no community modules (`terraform-aws-modules/*`): the
infrastructure is small, and the user must be able to explain every line at the
defense.

## Decisions taken with the user

| Area | Decision |
|---|---|
| Account and region | Personal account, `eu-west-1` (Ireland); region is a variable with that default |
| Terraform state | Local files on the user's laptop, git-ignored. No S3 backend, no HCP Terraform. Nobody else needs the laptop: the app runs in AWS on its own, and CI (8b) deploys through the AWS API without the state. Losing the laptop means deleting leftovers by the tag `Project=project-hub`; keep it in a backup (Time Machine) |
| HTTPS | Self-signed certificate imported into ACM; ALB listens on 443, port 80 redirects to 443. The browser warns once |
| Lambda | No placeholder functions; 7a / 7b add theirs |
| CI access to AWS | GitHub OIDC, trust only `repo:MilaHalko/project-hub:ref:refs/heads/main` |
| Budget | $20 per month, emails at 50 %, 80 %, 100 % actual and 100 % forecast, counting cost before credits |
| Budget email | The user's personal address, only in the git-ignored `terraform.tfvars` |
| Frontend | Not deployed in 8a |
| Tooling | Terraform 1.17.2, tflint 0.66.0 with `tflint-ruleset-aws` 0.50.0, checkov 3.4.5 |

## Layout

```
infra/
  README.md                checkpoint runbook (addition 3)
  .tflint.hcl              aws ruleset, pinned
  persistent/              state: infra/persistent/terraform.tfstate (git-ignored)
    versions.tf providers.tf variables.tf outputs.tf
    network.tf security.tf iam.tf github.tf ecr.tf s3.tf ssm.tf ecs.tf budget.tf
    terraform.tfvars.example
    tests/*.tftest.hcl      (addition 2)
  ephemeral/               state: infra/ephemeral/terraform.tfstate (git-ignored)
    versions.tf providers.tf variables.tf outputs.tf
    lookup.tf rds.tf alb.tf service.tf
```

- Providers: `hashicorp/aws ~> 6.73`, `hashicorp/random ~> 3.9`,
  `hashicorp/tls ~> 4.4`; `required_version >= 1.11` (write-only arguments).
  `.terraform.lock.hcl` of each layer is committed with hashes for
  `darwin_arm64` (the user's laptop) and `linux_amd64` (CI), made with
  `terraform providers lock -platform=...`.
- `default_tags` on the provider: `Project = project-hub`,
  `ManagedBy = terraform`, `Layer = persistent | ephemeral`.
- Every name starts with `project-hub`.
- `.gitignore` gains `.terraform/`, `*.tfstate`, `*.tfstate.*`, `*.tfvars`
  (but not `*.tfvars.example`), `.terraform.tfstate.lock.info`.
- The ephemeral layer finds persistent resources with data sources by name or
  tag (`aws_vpc`, `aws_subnets`, `aws_security_group`, `aws_ecs_cluster`,
  `aws_iam_role`, `aws_ecr_repository`, `aws_cloudwatch_log_group`,
  `aws_s3_bucket`). SSM parameters are referenced by an ARN built from
  `aws_caller_identity`, the region and the name, never through
  `data "aws_ssm_parameter"`, which stores the value in the state. No
  `terraform_remote_state`: the layers share names, not state files.

## Persistent layer

**Network** (free):
- VPC `10.0.0.0/16`, DNS support and hostnames on.
- Two public subnets in two AZs (an ALB needs two), route to an internet
  gateway. Two private subnets in the same AZs (an RDS subnet group needs two),
  no route to the internet.
- **No NAT gateway** (about $35 a month) and no interface VPC endpoints (about
  $7 a month each): the API task runs in a public subnet with a public IP so it
  can reach ECR, SSM, S3 and CloudWatch; only the ALB can reach the task.
- The VPC's default security group is taken over with no rules.

**Security groups** (free, persistent because 7a's Lambda will need the DB rule
too). The groups reference each other, which inline rule blocks cannot express
(Terraform reports a dependency cycle), so every rule is its own
`aws_vpc_security_group_ingress_rule` / `aws_vpc_security_group_egress_rule`
and the groups have no inline rules:
- `project-hub-alb`: in 80 and 443 from `0.0.0.0/0` (this is the public door);
  out 8000 to `project-hub-app` only.
- `project-hub-app`: in 8000 from `project-hub-alb` only; out 443 to
  `0.0.0.0/0` (AWS APIs and ECR through the internet gateway) and 5432 to
  `project-hub-db`.
- `project-hub-db`: in 5432 from `project-hub-app` only; no egress.

**IAM**:
- `project-hub-ecs-execution` (used by ECS to start the task): `ecr:GetAuthorizationToken`
  on `*` (AWS allows nothing narrower), image pull actions on the
  `project-hub-api` repository only, `logs:CreateLogStream` / `logs:PutLogEvents`
  on the API log group only, `ssm:GetParameters` on
  `arn:aws:ssm:<region>:<account>:parameter/project-hub/*` only. Parameters use
  the AWS-managed `aws/ssm` key, which needs no extra KMS grant.
- `project-hub-api-task` (used by the app itself): `s3:PutObject`,
  `s3:GetObject`, `s3:DeleteObject` on `<bucket>/projects/*` only, which is
  exactly what epic 6's `S3FileStorage` calls (`put_object`, `get_object`,
  `delete_objects`).
- GitHub OIDC identity provider for `token.actions.githubusercontent.com`,
  audience `sts.amazonaws.com`.
- `project-hub-github-deploy` (for 8b), trusted only by
  `repo:MilaHalko/project-hub:ref:refs/heads/main` with
  `aud = sts.amazonaws.com`. Permissions: push to `project-hub-api` only;
  `ecs:UpdateService` and `ecs:DescribeServices` on the service
  `project-hub-api` in cluster `project-hub` only; `ecs:RegisterTaskDefinition`
  and `ecs:DescribeTaskDefinition` (AWS allows only `*`); `iam:PassRole` on the
  two ECS roles only, with `iam:PassedToService = ecs-tasks.amazonaws.com`. 8b may
  narrow or extend this with its own design.

**ECR**: repository `project-hub-api`, scan on push (basic, free), immutable
tags, AES-256 encryption, lifecycle rule keeping the newest 10 images,
`force_delete = true` (images are rebuilt by CI; without it a full teardown
fails).

**S3**: bucket `project-hub-documents-<8 random hex>` (bucket names are global;
a random suffix avoids collisions without putting the account id in the name).
All four public access blocks on, `BucketOwnerEnforced`, SSE-S3, a bucket
policy denying any request without TLS, lifecycle rule aborting unfinished
multipart uploads after 1 day, `force_destroy = true` (demo data only, never
the only copy). Versioning off: epic 6 rejected version history, and old
versions would cost money and outlive deletes. No CORS: uploads go through the
API (epic 6 decision), so the "Frontend requests" CORS row does not apply.

**SSM Parameter Store** (standard parameters are free), prefix `/project-hub/`:
- `/project-hub/jwt-secret`: SecureString, 48 random characters from an
  `ephemeral "random_password"`, written with `value_wo` and
  `value_wo_version = 1`, so the value is never in the state. Bumping the
  version rotates it (all tokens become invalid).
- `/project-hub/db-backend`: String, `orm` (addition 4).
- `/project-hub/database-url` is created by the ephemeral layer (it depends on
  the RDS endpoint).

**ECS**: cluster `project-hub`, Container Insights off (billed). Log group
`/ecs/project-hub-api`, retention 7 days.

**Budgets** (the first two budgets in an account are free):
- `project-hub-monthly`: $20 per month, cost types without credits and refunds,
  so it shows real spending while credits pay for it. Emails at 50 %, 80 %,
  100 % actual and 100 % forecasted.
- `project-hub-daily` (addition 1): $1 per day, email at 100 % actual. A
  forgotten ephemeral layer costs about $1.70 a day, so this fires the first day
  instead of after a week.

**Outputs**: VPC and subnet ids, ECR repository URL, bucket name, deploy role
ARN (8b puts it into a GitHub variable), cluster name.

## Ephemeral layer

**RDS PostgreSQL**:
- `db.t4g.micro`, engine `postgres`, major version 18 (same as local
  `postgres:18-alpine`), 20 GB gp3, single AZ, encrypted, not publicly
  accessible, subnet group from the two private subnets, `project-hub-db` SG.
- Database and user `project_hub`. Password from an `ephemeral "random_password"`
  (32 characters, letters and digits only, so the URL needs no escaping),
  passed with `password_wo` and `password_wo_version`; it is not in the state.
- `/project-hub/database-url`: SecureString
  `postgresql://project_hub:<password>@<endpoint>:5432/project_hub?sslmode=require`,
  written with `value_wo` in the same apply as the instance. Both write-only
  versions come from one local value so they always change together.
- Known limit: the ephemeral password is new on every run, and write-only
  values are sent only on create or a version change. If an apply creates the
  instance and then fails before the parameter is written, a retry writes a
  different password. The runbook rule: a failed ephemeral apply is followed by
  `destroy` and a fresh `apply` (the layer holds demo data only).
- `backup_retention_period = 1`, `skip_final_snapshot = true`,
  `deletion_protection = false`, `delete_automated_backups = true`,
  `apply_immediately = true`: the database holds demo data and must be
  destroyable in one command.

**ALB**:
- Internet-facing, two public subnets, `project-hub-alb` SG,
  `drop_invalid_header_fields = true`.
- Certificate: `tls_private_key` (RSA 2048) and `tls_self_signed_cert` with the
  ALB's DNS name as the subject alternative name, valid 30 days, imported into
  ACM. The private key of this throwaway certificate is in the local state; the
  state never leaves the laptop.
- Listener 80: redirect 301 to HTTPS. Listener 443:
  `ELBSecurityPolicy-TLS13-1-2-2021-06`, forwards to the target group.
- Target group: type `ip`, port 8000, health check `GET /health` expecting 200.
- The ALB forwards `Content-Length`, which epic 6's upload guard needs; the
  checkpoint confirms it.

**ECS service and task**:
- Task family `project-hub-api`: Fargate, Linux X86_64 (CI builds amd64 images),
  0.25 vCPU / 0.5 GB, `awsvpc` network mode, the two persistent roles.
- Image: `data "aws_ecr_image"` with `most_recent = true` in `project-hub-api`,
  referenced by digest. With an empty repository the apply stops with an error;
  `infra/README.md` shows how to push the first image by hand until 8b exists.
- Container `migrate`: same image, command
  `["python", "-m", "project_hub.db.migrate"]`, `essential = false`, secret
  `APP_DATABASE_URL`. Same as the `migrate` service in compose.
- Container `api`: `dependsOn migrate SUCCESS`, port 8000, read-only root
  filesystem with a writable task volume mounted at `/tmp` (uploads over 1 MB
  are spooled to a temporary file by the multipart parser), secrets from SSM: `APP_DATABASE_URL`, `APP_JWT_SECRET`,
  `APP_DB_BACKEND`; plain environment: `APP_S3_BUCKET`, `APP_S3_REGION`. Logs to
  the persistent log group. The two S3 settings and the three S3 actions come
  from epic 6, which is finished but not merged yet; until it is, `Settings`
  ignores the unknown variables (`extra="ignore"`). Epic 6 does not rely on
  `NoSuchKey` (every key comes from the `documents` table), so no
  `s3:ListBucket`.
- If the read-only root filesystem with the `/tmp` volume fails at the first
  checkpoint (the app runs as uid 1000), the fallback is a writable root
  filesystem; the change is one argument and is folded back into this epic. No code change in `src/`: the app already reads
  every `APP_*` variable.
- Service `project-hub-api`: desired count 1, regular Fargate (not Spot, which
  AWS may stop during a demo), public subnets with a public IP, `project-hub-app`
  SG, behind the target group, `health_check_grace_period_seconds = 120`
  (migrations run first), deployment circuit breaker with rollback,
  `wait_for_steady_state = true` so `apply` ends only when the API answers the
  health check.

**Outputs**: `https://<alb dns>` and the ALB DNS name.

How 8b's deploys and later ephemeral applies coexist (for example
`ignore_changes` on the service's task definition) is decided in 8b: in 8a every
ephemeral apply builds a fresh task definition from the newest image.

## Cost

Ephemeral layer, `eu-west-1`, per hour (approximate list prices, paid from
credits): ALB $0.025 + capacity units ~$0.008, RDS `db.t4g.micro` $0.018,
Fargate 0.25 vCPU / 0.5 GB $0.012, three public IPv4 (two ALB, one task)
$0.015. Total **about $0.08 an hour**: a two-hour checkpoint costs about
$0.20, a forgotten layer about $1.70 a day or $55 a month.
Persistent layer: a few cents a month (ECR storage, S3, CloudWatch Logs).

## Checks

Proven by commands that really run Terraform and the linters, never by reading
`.tf` files in a test:

- `terraform fmt -check -recursive infra`
- per layer: `terraform init -backend=false` and `terraform validate`
- `tflint --recursive --config infra/.tflint.hcl`
- `checkov -d infra --framework terraform`, every skipped check written next to
  its resource as `# checkov:skip=<id>: <reason>`. Expected skips, each a
  cost decision from this design: KMS customer keys (ECR, logs, SSM, S3,
  RDS), VPC flow logs, ALB and S3 access logs, Container Insights, RDS
  Multi-AZ / deletion protection / IAM auth / enhanced monitoring, S3
  versioning / replication / event notifications, log retention under a year,
  ALB deletion protection, WAF.
- `terraform test` in `infra/persistent` with `mock_provider "aws"` (addition
  2), only for security properties no other check catches.
- New CI job `terraform` in `.github/workflows/ci.yml`: runs all of the above,
  needs no AWS credentials; actions pinned by SHA like the rest of the file.
  It is not a required check until the user adds it to the `protect-main`
  ruleset.
- `terraform plan` against the real account: only if the user signs in and asks.

## Additions beyond the roadmap (need the user's yes)

| # | Addition | Why | Cost | Recommendation |
|---|---|---|---|---|
| 1 | Daily budget $1 / day | Catches a forgotten ephemeral layer on day one instead of day five | One resource; free (second budget) | Yes |
| 2 | `terraform test` guards for three security properties: deploy role trusts only `main` of `MilaHalko/project-hub`; the DB rule admits only the app SG; the app rule admits only the ALB SG | checkov flags a wildcard repo and open CIDRs, but not a widened branch or an extra SG source; these are the "config test guards a security property nothing else catches" exception in `CLAUDE.md` | One test file, runs offline in a second | Yes |
| 3 | `infra/README.md` checkpoint runbook: first-time setup, push the first image, apply / verify / destroy, cost, how to find leftovers by tag | The user drives every apply herself and defends it | One file, linked from the root README | Yes |
| 4 | `APP_DB_BACKEND` read from SSM | Switch `orm` / `sql` in the console and restart the service at the demo, which shows the swappable data layer live | One parameter | Yes |

## Rejected or postponed

| Item | Reason |
|---|---|
| NAT gateway, interface VPC endpoints | ~$35 and ~$7 a month each; public subnet + strict SGs give the same isolation for this app |
| Secrets Manager | Billed per secret; roadmap chose SSM |
| Customer-managed KMS keys | $1 a month each; AWS-managed keys encrypt the same data |
| VPC flow logs, ALB / S3 access logs, Container Insights, RDS enhanced monitoring | Billed; not needed for a demo |
| RDS Multi-AZ, Fargate Spot, ARM64 | Double cost; Spot can stop mid-demo; CI builds amd64 |
| CloudFront, own domain | Global service / domain purchase; self-signed chosen |
| S3 remote state, HCP Terraform | Laptop state chosen |
| Lambda placeholders | 7a / 7b add the real functions |
| Frontend container | Its own task after F6 |
| S3 gateway endpoint for private subnets | Free, but nothing in a private subnet needs S3 yet; 7a decides when its Lambda goes into the VPC |
| `terraform_remote_state` between layers | Couples the ephemeral layer to the state's location; name lookups are enough |

## Roadmap changes (same branch)

- Row 8a ticked when merged.
- "AWS sandbox rules" becomes "AWS account rules": personal Free plan account,
  `eu-west-1`, no company name, personal email only, state on the laptop,
  checkpoint cost guard. The four mentor questions are replaced by the answers
  above.
- "Frontend requests": the HTTPS row becomes **accepted** (self-signed in ACM);
  the S3 CORS row becomes **later / not needed** (uploads go through the API).

## Left to the builder

- File split inside each layer and resource names below the `project-hub-`
  prefix.
- Exact CIDRs of the subnets and which two AZs (any two of `eu-west-1a/b/c`).
- The exact list of checkov skips, as long as each one is a cost decision above
  or is explained next to its resource.

## Acceptance criteria

Offline (proven in this epic):

1. `terraform fmt -check -recursive infra` exits 0.
2. `terraform init -backend=false && terraform validate` exits 0 in
   `infra/persistent` and in `infra/ephemeral`.
3. `tflint --recursive` with the pinned aws ruleset reports no issues.
4. `checkov -d infra --framework terraform` reports 0 failed checks; every
   skip carries a reason next to its resource.
5. `terraform test` in `infra/persistent` passes: given the plan, the deploy
   role's trust policy allows only `repo:MilaHalko/project-hub:ref:refs/heads/main`
   with audience `sts.amazonaws.com`; the DB ingress rule is port 5432 from the
   app SG with no CIDR; the app ingress rule is port 8000 from the ALB SG with
   no CIDR. A widened CIDR anywhere is also caught by checkov (criterion 4).
6. `grep -rniE '<company name>' infra docs/superpowers/specs/2026-11-15-terraform-infra-design.md`
   finds nothing (run with the real name, which is not written here).
7. `git check-ignore` confirms `infra/*/terraform.tfstate`,
   `infra/*/terraform.tfvars` and `infra/*/.terraform/` are ignored, and the
   committed `terraform.tfvars.example` holds no real address.
8. The CI job `terraform` runs checks 1–5 and is green on the PR.

At the first checkpoint (proven by the user in her account, after merge):

9. Persistent `apply` succeeds in an account without project resources; the
   budget emails arrive at her address (AWS sends a confirmation).
10. After one image is in ECR, ephemeral `apply` finishes with the service
    steady; `curl -k https://<alb>/health` answers 200 and
    `curl -I http://<alb>/health` answers 301 to HTTPS.
11. Register, log in and create a project through the ALB: data lands in RDS.
12. Ephemeral `destroy` leaves only persistent resources (checked by the tag
    `Layer = ephemeral` in Resource Groups / Tag Editor finding nothing).
