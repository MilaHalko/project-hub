# Epic 8a Terraform Infrastructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Terraform code for a persistent and an ephemeral AWS layer that runs the Project Hub API on ECS Fargate, RDS and an HTTPS ALB in `eu-west-1`, checked offline locally and in CI.

**Architecture:** Two root modules, `infra/persistent` and `infra/ephemeral`, each with its own local state. The ephemeral layer finds persistent resources by name or tag and builds SSM ARNs from the account id. Plain `resource` blocks, no community modules.

**Tech Stack:** Terraform 1.17.2, providers `hashicorp/aws ~> 6.73`, `hashicorp/random ~> 3.9`, `hashicorp/tls ~> 4.4`, tflint 0.66.0 + `tflint-ruleset-aws` 0.50.0, checkov 3.4.5, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-11-15-terraform-infra-design.md`

## Global Constraints

- **Never** run `terraform apply`, `destroy`, `plan`, `import`, or any `aws` command against AWS. No AWS credentials are present; none are entered. `terraform test` runs only with `mock_provider "aws"`.
- Local binaries: `~/.local/bin/terraform`, `~/.local/bin/tflint`, `~/.local/bin/checkov` (prepend `$HOME/.local/bin` to `PATH` in every shell).
- `required_version = ">= 1.11"`; providers exactly `~> 6.73`, `~> 3.9`, `~> 4.4`.
- Region variable `region`, default `"eu-west-1"`. Provider `default_tags`: `Project = "project-hub"`, `ManagedBy = "terraform"`, `Layer = "persistent"` / `"ephemeral"`.
- Every AWS name starts with `project-hub`. The course provider's company name appears nowhere (files, names, tags, commit messages).
- IAM policies are written with `jsonencode(...)`, never `data "aws_iam_policy_document"`: the mock provider returns a random string for that data source's JSON, which breaks the tests.
- No comments. Allowed `#` lines: `#checkov:skip=<ID>:<reason>` inside the resource it skips, and a hidden-reason comment where the code looks safe to change but is not.
- Do not touch `src/`, `tests/` (Python), `frontend/`, `docker-compose.yml`, `Dockerfile`.
- Commit subjects: plain words, imperative, ≤ ~70 chars, 1–3 line body; **no `Co-Authored-By` trailer**. One commit per task (fixes folded in with `git commit --amend` before the next task starts).
- Lock files: after the first `terraform init` in a layer, run `terraform providers lock -platform=darwin_arm64 -platform=linux_amd64` and commit `.terraform.lock.hcl`.

Checks used by every task (run from the repo root, `export PATH="$HOME/.local/bin:$PATH"` first):

```bash
terraform fmt -check -recursive infra
terraform -chdir=infra/persistent init -backend=false -input=false && terraform -chdir=infra/persistent validate
terraform -chdir=infra/ephemeral init -backend=false -input=false && terraform -chdir=infra/ephemeral validate
tflint --init --config "$PWD/infra/.tflint.hcl" && tflint --recursive --config "$PWD/infra/.tflint.hcl" --chdir infra
checkov -d infra --framework terraform --quiet --compact --skip-path '\.terraform'
terraform -chdir=infra/persistent test
```

Expected: each exits 0; checkov prints `Failed checks: 0` (or no failed section); `terraform test` prints `Success! N passed, 0 failed.`

## Review Focus

1. **Cross-referencing security groups** — inline `ingress`/`egress` blocks between `alb`, `app` and `db` create a dependency cycle; every rule must be its own `aws_vpc_security_group_*_rule`. Task 1's test pins the two critical rules.
2. **Secrets leaking into state** — `data "aws_ssm_parameter"` and non-ephemeral `random_password` store values in state. Only `ephemeral "random_password"` + `*_wo` arguments may carry the JWT secret and DB password. Reviewers grep both layers for `data "aws_ssm_parameter"` and `resource "random_password"`.
3. **Ephemeral lookups that match nothing or several things** — every data source in `infra/ephemeral/lookup.tf` must use the exact name/tag Task 1–3 produce (listed in their Interfaces blocks). A mismatch only shows at the first real apply, so reviewers compare names character by character.
4. **The `/tmp` volume and read-only root** — uploads over 1 MB spool to `/tmp`; the `api` container must mount the `tmp` volume at `/tmp`.
5. **A forgotten ephemeral layer** — the daily budget is the only guard; Task 4 must set `time_unit = "DAILY"` with an `ACTUAL` notification (AWS does not forecast daily budgets).

---

### Task 1: Network and security groups, checked offline locally and in CI

Commit subject: `Build the VPC and security groups with Terraform, checked in CI`

**Files:**
- Modify: `.gitignore`
- Create: `infra/.tflint.hcl`
- Create: `infra/persistent/versions.tf`, `providers.tf`, `variables.tf`, `network.tf`, `security.tf`, `outputs.tf`, `.terraform.lock.hcl`
- Create: `infra/persistent/tests/network.tftest.hcl`
- Create: `infra/ephemeral/versions.tf`, `providers.tf`, `variables.tf`, `.terraform.lock.hcl` (providers only; resources come in Task 5)
- Modify: `.github/workflows/ci.yml` (new job `terraform`)

**Interfaces:**
- Produces (names the ephemeral layer looks up):
  - VPC tag `Name = "project-hub"`.
  - Subnets: tag `Tier = "public"` (two, `10.0.0.0/24`, `10.0.1.0/24`) and `Tier = "private"` (two, `10.0.10.0/24`, `10.0.11.0/24`), AZs from variable `availability_zones` (default `["eu-west-1a", "eu-west-1b"]`), `Name` tags `project-hub-public-a`, `-public-b`, `-private-a`, `-private-b`.
  - Security groups named `project-hub-alb`, `project-hub-app`, `project-hub-db`; resource addresses `aws_security_group.alb`, `.app`, `.db`.
  - Rule addresses: `aws_vpc_security_group_ingress_rule.alb_http`, `.alb_https`, `.app_from_alb`, `.db_from_app`; `aws_vpc_security_group_egress_rule.alb_to_app`, `.app_https`, `.app_to_db`.
  - Outputs `vpc_id`, `public_subnet_ids`, `private_subnet_ids`.

- [ ] **Step 1: Ignore state, plugins and real variables**

Append to `.gitignore`: `.terraform/`, `*.tfstate`, `*.tfstate.*`, `.terraform.tfstate.lock.info`, `*.tfvars`, `!*.tfvars.example`.

- [ ] **Step 2: Write the failing security test** `infra/persistent/tests/network.tftest.hcl`

```hcl
mock_provider "aws" {}

run "database_accepts_only_the_app" {
  command = apply
  assert {
    condition     = aws_vpc_security_group_ingress_rule.db_from_app.referenced_security_group_id == aws_security_group.app.id
    error_message = "The database must accept connections only from the app security group."
  }
  assert {
    condition     = aws_vpc_security_group_ingress_rule.db_from_app.from_port == 5432 && aws_vpc_security_group_ingress_rule.db_from_app.to_port == 5432
    error_message = "The database rule must open port 5432 only."
  }
  assert {
    condition     = aws_vpc_security_group_ingress_rule.db_from_app.cidr_ipv4 == null && aws_vpc_security_group_ingress_rule.db_from_app.cidr_ipv6 == null
    error_message = "The database rule must not admit any CIDR."
  }
}

run "app_accepts_only_the_load_balancer" {
  command = apply
  assert {
    condition     = aws_vpc_security_group_ingress_rule.app_from_alb.referenced_security_group_id == aws_security_group.alb.id
    error_message = "The API must accept connections only from the load balancer."
  }
  assert {
    condition     = aws_vpc_security_group_ingress_rule.app_from_alb.from_port == 8000 && aws_vpc_security_group_ingress_rule.app_from_alb.to_port == 8000
    error_message = "The API rule must open port 8000 only."
  }
  assert {
    condition     = aws_vpc_security_group_ingress_rule.app_from_alb.cidr_ipv4 == null && aws_vpc_security_group_ingress_rule.app_from_alb.cidr_ipv6 == null
    error_message = "The API rule must not admit any CIDR."
  }
}
```

Add `versions.tf` and `providers.tf` first (needed to init), then run `terraform -chdir=infra/persistent init -backend=false -input=false && terraform -chdir=infra/persistent test`.
Expected: FAIL, "Reference to undeclared resource" for the rules.

- [ ] **Step 3: Write the persistent layer's network** (`variables.tf`, `network.tf`, `security.tf`, `outputs.tf`)

- `aws_vpc.main`: `10.0.0.0/16`, `enable_dns_support`/`enable_dns_hostnames = true`.
- `aws_internet_gateway.main`; `aws_route_table.public` with route `0.0.0.0/0` → IGW; `aws_route_table.private` with no routes; associations for every subnet.
- `aws_subnet.public` / `.private` with `count = 2`, `map_public_ip_on_launch = false`.
- `aws_default_security_group.default` with no `ingress`/`egress` blocks.
- Security groups with **no inline rules**; rules: `alb_http` 80 and `alb_https` 443 from `0.0.0.0/0`; `alb_to_app` 8000 to `app`; `app_from_alb` 8000 from `alb`; `app_https` 443 to `0.0.0.0/0`; `app_to_db` 5432 to `db`; `db_from_app` 5432 from `app`. All `ip_protocol = "tcp"`.
- Checkov will flag the open port 80 and the egress to `0.0.0.0/0` on 443; skip each inline with its reason (80 only redirects to HTTPS; the task reaches AWS APIs over the internet gateway because there is no NAT or endpoint, by cost decision).

- [ ] **Step 4: Run the test**

Run: `terraform -chdir=infra/persistent test` — Expected: `Success! 2 passed, 0 failed.`

- [ ] **Step 5: Ephemeral layer skeleton**

`infra/ephemeral/versions.tf` (same three providers) and `providers.tf` (`Layer = "ephemeral"`), `variables.tf` with `region`. Init both layers, then `terraform providers lock -platform=darwin_arm64 -platform=linux_amd64` in each.

- [ ] **Step 6: tflint config** `infra/.tflint.hcl`

`plugin "terraform"` with `preset = "recommended"`; `plugin "aws"` with `version = "0.50.0"`, `source = "github.com/terraform-linters/tflint-ruleset-aws"`.

- [ ] **Step 7: CI job `terraform`** in `.github/workflows/ci.yml`

Parallel to `checks` and `docker`, `timeout-minutes: 10`, no `permissions` override, no secrets except `GITHUB_TOKEN` passed as env to `tflint --init` (rate limit). Steps: checkout (same pinned SHA, `persist-credentials: false`); `hashicorp/setup-terraform` pinned to a 40-char SHA with `terraform_version: 1.17.2` and `terraform_wrapper: false`; `terraform-linters/setup-tflint` pinned SHA with `tflint_version: v0.66.0`; `pipx install checkov==3.4.5`; then the six check commands from Global Constraints. Look up the SHAs with `gh api repos/<owner>/<repo>/git/ref/tags/<tag>` (dereference annotated tags) and put the version in a trailing comment as the file already does.

- [ ] **Step 8: Run every check** (Global Constraints block). Expected: all exit 0.

- [ ] **Step 9: Commit**

```bash
git add .gitignore infra .github/workflows/ci.yml
git commit -m "Build the VPC and security groups with Terraform, checked in CI" -m "Public and private subnets without a NAT gateway; the database and the API admit only their one caller. CI runs fmt, validate, tflint, checkov and terraform test offline."
```

---

### Task 2: Image registry and a GitHub deploy role trusted only from main

Commit subject: `Let CI on main push images to ECR through GitHub OIDC`

**Files:**
- Create: `infra/persistent/ecr.tf`, `infra/persistent/github.tf`
- Create: `infra/persistent/tests/github.tftest.hcl`
- Modify: `infra/persistent/variables.tf`, `outputs.tf`

**Interfaces:**
- Consumes: provider setup from Task 1.
- Produces: `aws_ecr_repository.api` named `project-hub-api`; `aws_iam_openid_connect_provider.github`; `aws_iam_role.github_deploy` named `project-hub-github-deploy`; variable `github_repository` (default `"MilaHalko/project-hub"`); outputs `ecr_repository_url`, `github_deploy_role_arn`. Role names used in its `iam:PassRole` statement (created in Task 3): `project-hub-ecs-execution`, `project-hub-api-task`. ECS names used in its policy: cluster `project-hub`, service `project-hub-api`.

- [ ] **Step 1: Write the failing trust test** `infra/persistent/tests/github.tftest.hcl`

```hcl
mock_provider "aws" {}

run "deploy_role_trusts_only_main" {
  command = apply
  assert {
    condition     = length(jsondecode(aws_iam_role.github_deploy.assume_role_policy).Statement) == 1
    error_message = "The deploy role must have exactly one trust statement."
  }
  assert {
    condition     = jsondecode(aws_iam_role.github_deploy.assume_role_policy).Statement[0].Condition.StringEquals["token.actions.githubusercontent.com:sub"] == "repo:MilaHalko/project-hub:ref:refs/heads/main"
    error_message = "Only the main branch of MilaHalko/project-hub may assume the deploy role."
  }
  assert {
    condition     = jsondecode(aws_iam_role.github_deploy.assume_role_policy).Statement[0].Condition.StringEquals["token.actions.githubusercontent.com:aud"] == "sts.amazonaws.com"
    error_message = "The deploy role must require the STS audience."
  }
  assert {
    condition     = !contains(keys(jsondecode(aws_iam_role.github_deploy.assume_role_policy).Statement[0].Condition), "StringLike")
    error_message = "The deploy role must not match subjects with wildcards."
  }
  assert {
    condition     = jsondecode(aws_iam_role.github_deploy.assume_role_policy).Statement[0].Principal.Federated == aws_iam_openid_connect_provider.github.arn
    error_message = "The deploy role must trust the GitHub OIDC provider."
  }
}
```

The test file needs the same `variables` as other test files once Task 4 adds `alert_email`; Task 4 adds a `variables { alert_email = "alerts@example.com" }` block to every test file.

Run: `terraform -chdir=infra/persistent test` — Expected: FAIL, undeclared `aws_iam_role.github_deploy`.

- [ ] **Step 2: ECR** (`ecr.tf`): `image_tag_mutability = "IMMUTABLE"`, `scan_on_push = true`, `encryption_type = "AES256"`, `force_delete = true`; `aws_ecr_lifecycle_policy` expiring images beyond the newest 10 (`tagStatus = "any"`, `countType = "imageCountMoreThan"`, `countNumber = 10`). Skip the KMS check inline (cost decision).

- [ ] **Step 3: OIDC provider and deploy role** (`github.tf`)

- Provider URL `https://token.actions.githubusercontent.com`, `client_id_list = ["sts.amazonaws.com"]`.
- Trust: one `Allow` statement, action `sts:AssumeRoleWithWebIdentity`, `Principal.Federated` = provider ARN, `Condition.StringEquals` with `:aud = sts.amazonaws.com` and `:sub = "repo:${var.github_repository}:ref:refs/heads/main"`.
- Inline policy `aws_iam_role_policy.github_deploy` (ARNs built from `data "aws_caller_identity" "current"` and `var.region`):
  - `ecr:GetAuthorizationToken` on `*`;
  - `ecr:BatchCheckLayerAvailability`, `ecr:InitiateLayerUpload`, `ecr:UploadLayerPart`, `ecr:CompleteLayerUpload`, `ecr:PutImage`, `ecr:BatchGetImage` on the repository ARN;
  - `ecs:UpdateService`, `ecs:DescribeServices` on `arn:aws:ecs:<region>:<account>:service/project-hub/project-hub-api`;
  - `ecs:RegisterTaskDefinition`, `ecs:DescribeTaskDefinition` on `*`;
  - `iam:PassRole` on the two role ARNs `arn:aws:iam::<account>:role/project-hub-ecs-execution` and `.../project-hub-api-task`, condition `StringEquals iam:PassedToService = ecs-tasks.amazonaws.com`.

- [ ] **Step 4: Run every check.** Expected: `terraform test` → `Success! 3 passed, 0 failed.`; all others exit 0.

- [ ] **Step 5: Commit** `git add infra/persistent && git commit -m "Let CI on main push images to ECR through GitHub OIDC" -m "..."`

---

### Task 3: Cluster, roles, bucket and settings the API runs with

Commit subject: `Prepare the ECS cluster, S3 bucket and SSM settings for the API`

**Files:**
- Create: `infra/persistent/ecs.tf`, `iam.tf`, `s3.tf`, `ssm.tf`
- Modify: `infra/persistent/outputs.tf`

**Interfaces:**
- Consumes: `aws_ecr_repository.api` (Task 2), `data.aws_caller_identity.current` (Task 2).
- Produces (looked up by Task 5):
  - `aws_ecs_cluster.main` named `project-hub`, setting `containerInsights = "disabled"`.
  - `aws_cloudwatch_log_group.api` named `/ecs/project-hub-api`, `retention_in_days = 7`.
  - `aws_iam_role.ecs_execution` named `project-hub-ecs-execution`, `aws_iam_role.api_task` named `project-hub-api-task`; both trust `ecs-tasks.amazonaws.com` with `Condition.StringEquals aws:SourceAccount = <account>`.
  - Bucket `project-hub-documents-${random_id.bucket_suffix.hex}` (`byte_length = 4`).
  - SSM parameters: `/project-hub/jwt-secret` (SecureString), `/project-hub/db-backend` (String, `orm`), `/project-hub/s3-bucket` (String, the bucket name). Task 5 creates `/project-hub/database-url`.
  - Outputs `ecs_cluster_name`, `documents_bucket`.

- [ ] **Step 1: ECS cluster and log group** (`ecs.tf`). Skip inline: Container Insights (billed), log group KMS and one-year retention (cost).

- [ ] **Step 2: Roles** (`iam.tf`), policies inline with `jsonencode`:
  - execution: `ecr:GetAuthorizationToken` on `*`; `ecr:BatchCheckLayerAvailability`, `ecr:GetDownloadUrlForLayer`, `ecr:BatchGetImage` on the repository ARN; `logs:CreateLogStream`, `logs:PutLogEvents` on `"${aws_cloudwatch_log_group.api.arn}:*"`; `ssm:GetParameters` on `arn:aws:ssm:<region>:<account>:parameter/project-hub/*`.
  - task: `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject` on `"${aws_s3_bucket.documents.arn}/projects/*"`. Nothing else.

- [ ] **Step 3: Bucket** (`s3.tf`): `force_destroy = true`; `aws_s3_bucket_public_access_block` all four `true`; `aws_s3_bucket_ownership_controls` `BucketOwnerEnforced`; `aws_s3_bucket_server_side_encryption_configuration` `AES256`; `aws_s3_bucket_policy` denying `s3:*` on bucket and objects when `aws:SecureTransport = false`; `aws_s3_bucket_lifecycle_configuration` with `filter {}` and `abort_incomplete_multipart_upload { days_after_initiation = 1 }`. Skip inline: versioning, access logging, replication, event notifications, KMS (each a design decision; event notifications come with 7a/7b).

- [ ] **Step 4: Settings** (`ssm.tf`)
  - `ephemeral "random_password" "jwt_secret"`: `length = 48`, `special = false`.
  - `aws_ssm_parameter.jwt_secret`: `type = "SecureString"`, `value_wo = ephemeral.random_password.jwt_secret.result`, `value_wo_version = 1`.
  - `aws_ssm_parameter.db_backend`: `type = "String"`, `value = "orm"`, `lifecycle { ignore_changes = [value] }` with a one-line hidden-reason comment (the user flips it in the console at the demo; `apply` must not revert it).
  - `aws_ssm_parameter.s3_bucket`: `type = "String"`, `value = aws_s3_bucket.documents.bucket`.
  - Checkov may ask for a customer KMS key on the SecureString; skip inline (AWS-managed `aws/ssm` key, cost decision).

- [ ] **Step 5: Run every check.** Expected: all exit 0; `terraform test` still `3 passed`. Grep: `grep -rn 'data "aws_ssm_parameter"\|resource "random_password"' infra` prints nothing.

- [ ] **Step 6: Commit** `git add infra/persistent && git commit -m "Prepare the ECS cluster, S3 bucket and SSM settings for the API" -m "..."`

---

### Task 4: Budget alerts by email

Commit subject: `Email the owner when AWS spending passes the monthly or daily budget`

**Files:**
- Create: `infra/persistent/budget.tf`, `infra/persistent/terraform.tfvars.example`
- Modify: `infra/persistent/variables.tf`, both files in `infra/persistent/tests/`

**Interfaces:**
- Produces: variable `alert_email` (string, no default, `validation` with `can(regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", var.alert_email))`).

- [ ] **Step 1: Variable and example.** `terraform.tfvars.example` contains only `alert_email = "you@example.com"`. Add `variables { alert_email = "alerts@example.com" }` to both test files.

- [ ] **Step 2: Budgets** (`budget.tf`), both `budget_type = "COST"`, `limit_unit = "USD"`, `cost_types { include_credit = false, include_refund = false }`, subscriber `[var.alert_email]`:
  - `aws_budgets_budget.monthly`: name `project-hub-monthly`, `limit_amount = "20"`, `time_unit = "MONTHLY"`; notifications `GREATER_THAN` `PERCENTAGE` at 50, 80, 100 `ACTUAL` and 100 `FORECASTED`.
  - `aws_budgets_budget.daily`: name `project-hub-daily`, `limit_amount = "1"`, `time_unit = "DAILY"`; one notification 100 `ACTUAL`.

- [ ] **Step 3: Check the real address stays out of git.** Create `infra/persistent/terraform.tfvars` with `alert_email = "alerts@example.com"`, run `git check-ignore -v infra/persistent/terraform.tfvars infra/persistent/terraform.tfstate infra/persistent/.terraform` — Expected: three lines naming `.gitignore` rules. `git check-ignore infra/persistent/terraform.tfvars.example` — Expected: exit 1 (not ignored). Delete the scratch `terraform.tfvars` afterwards (the user writes the real one).

- [ ] **Step 4: Run every check.** Expected: all exit 0, `terraform test` `3 passed`.

- [ ] **Step 5: Commit** `git add infra/persistent && git commit -m "Email the owner when AWS spending passes the monthly or daily budget" -m "..."`

---

### Task 5: Ephemeral layer — the API on RDS behind HTTPS, with the checkpoint runbook

Commit subject: `Bring up the API on RDS behind an HTTPS load balancer for a checkpoint`

**Files:**
- Create: `infra/ephemeral/lookup.tf`, `rds.tf`, `alb.tf`, `service.tf`, `outputs.tf`
- Create: `infra/README.md`
- Modify: `README.md` (a short "Cloud" section linking `infra/README.md`; add `infra/` to "Layout")

**Interfaces:**
- Consumes: every name in the Interfaces blocks of Tasks 1–3.
- Produces: outputs `url` (`"https://${aws_lb.api.dns_name}"`) and `alb_dns_name`.

- [ ] **Step 1: Lookups** (`lookup.tf`): `aws_caller_identity`, `aws_region`; `aws_vpc` by tag `Name = "project-hub"`; `aws_subnets` `public` / `private` by `vpc-id` filter plus tag `Tier`; `aws_security_group` `alb` / `app` / `db` by `name` and `vpc_id`; `aws_ecs_cluster` `project-hub`; `aws_iam_role` `project-hub-ecs-execution` / `project-hub-api-task`; `aws_ecr_repository` `project-hub-api`; `aws_ecr_image` with `repository_name = "project-hub-api"`, `most_recent = true`; `aws_cloudwatch_log_group` `/ecs/project-hub-api`. A `local.ssm_arn_prefix = "arn:aws:ssm:${region}:${account_id}:parameter/project-hub"`. No `data "aws_ssm_parameter"`.

- [ ] **Step 2: Database** (`rds.tf`)
  - `aws_db_subnet_group.main` `project-hub`, private subnets.
  - `ephemeral "random_password" "db"`: `length = 32`, `special = false`.
  - `locals { db_password_version = 1 }`.
  - `aws_db_instance.main`: identifier `project-hub`, `engine = "postgres"`, `engine_version = "18"`, `instance_class = "db.t4g.micro"`, `allocated_storage = 20`, `storage_type = "gp3"`, `db_name = "project_hub"`, `username = "project_hub"`, `password_wo` / `password_wo_version = local.db_password_version`, `vpc_security_group_ids = [db sg]`, `publicly_accessible = false`, `multi_az = false`, `storage_encrypted = true`, `backup_retention_period = 1`, `skip_final_snapshot = true`, `deletion_protection = false`, `delete_automated_backups = true`, `apply_immediately = true`, `auto_minor_version_upgrade = true`, `copy_tags_to_snapshot = true`.
  - `aws_ssm_parameter.database_url`: `/project-hub/database-url`, SecureString, `value_wo = "postgresql://project_hub:${ephemeral.random_password.db.result}@${aws_db_instance.main.address}:5432/project_hub?sslmode=require"`, `value_wo_version = local.db_password_version`.
  - Skip inline: Multi-AZ, deletion protection, IAM auth, enhanced monitoring, Performance Insights, log exports, KMS CMK (cost / demo decisions).

- [ ] **Step 3: Load balancer** (`alb.tf`)
  - `aws_lb.api` `project-hub`, `load_balancer_type = "application"`, `internal = false`, public subnets, `alb` SG, `drop_invalid_header_fields = true`.
  - `tls_private_key.alb` RSA 2048; `tls_self_signed_cert.alb` `subject { common_name = "project-hub" }`, `dns_names = [aws_lb.api.dns_name]`, `validity_period_hours = 720`, `allowed_uses = ["key_encipherment", "digital_signature", "server_auth"]`; `aws_acm_certificate.alb` with `private_key` / `certificate_body`.
  - `aws_lb_target_group.api` `project-hub-api`, port 8000, HTTP, `target_type = "ip"`, VPC, `deregistration_delay = 30`, health check `path = "/health"`, `matcher = "200"`.
  - `aws_lb_listener.http` 80 → redirect `HTTPS` / `443` / `HTTP_301`; `aws_lb_listener.https` 443, `ssl_policy = "ELBSecurityPolicy-TLS13-1-2-2021-06"`, certificate, forward to the target group.
  - Skip inline: access logs, deletion protection, WAF.

- [ ] **Step 4: Service** (`service.tf`)
  - `aws_ecs_task_definition.api`: family `project-hub-api`, `requires_compatibilities = ["FARGATE"]`, `network_mode = "awsvpc"`, `cpu = "256"`, `memory = "512"`, `runtime_platform { operating_system_family = "LINUX", cpu_architecture = "X86_64" }`, both role ARNs, `volume { name = "tmp" }`.
  - Image for both containers: `"${data.aws_ecr_repository.api.repository_url}@${data.aws_ecr_image.api.image_digest}"`.
  - Container `migrate`: `essential = false`, `command = ["python", "-m", "project_hub.db.migrate"]`, secret `APP_DATABASE_URL` from `${local.ssm_arn_prefix}/database-url`, awslogs (group, region, `awslogs-stream-prefix = "migrate"`).
  - Container `api`: `essential = true`, `dependsOn = [{ containerName = "migrate", condition = "SUCCESS" }]`, `portMappings = [{ containerPort = 8000, protocol = "tcp" }]`, `readonlyRootFilesystem = true`, `mountPoints = [{ sourceVolume = "tmp", containerPath = "/tmp" }]`, secrets `APP_DATABASE_URL` (`/database-url`), `APP_JWT_SECRET` (`/jwt-secret`), `APP_DB_BACKEND` (`/db-backend`), `APP_S3_BUCKET` (`/s3-bucket`); environment `APP_S3_REGION = data.aws_region.current.region`; awslogs prefix `api`.
  - `aws_ecs_service.api`: name `project-hub-api`, cluster, `desired_count = 1`, `launch_type = "FARGATE"`, network in public subnets with `app` SG and `assign_public_ip = true`, `load_balancer` to the target group / `api` / 8000, `health_check_grace_period_seconds = 120`, `deployment_circuit_breaker { enable = true, rollback = true }`, `wait_for_steady_state = true`, `depends_on = [aws_lb_listener.https]`.

- [ ] **Step 5: Runbook** `infra/README.md` (English, plain, short sections):
  1. Once: `export PATH="$HOME/.local/bin:$PATH"`; sign in to the AWS CLI yourself (never paste keys into chat or files); `cp infra/persistent/terraform.tfvars.example infra/persistent/terraform.tfvars` and put the personal address in it; `terraform -chdir=infra/persistent init && terraform -chdir=infra/persistent apply`; confirm the AWS Budgets subscription email.
  2. First image until 8b exists: `aws ecr get-login-password --region eu-west-1 | docker login --username AWS --password-stdin <registry host>`; `docker build --platform linux/amd64 -t <ecr_repository_url>:manual-$(git rev-parse --short HEAD) .`; `docker push ...`.
  3. Checkpoint: `terraform -chdir=infra/ephemeral init && terraform -chdir=infra/ephemeral apply` (about 10 minutes); verify `curl -k "$(terraform -chdir=infra/ephemeral output -raw url)/health"` → 200 and `curl -I http://<alb_dns_name>/health` → 301; then `terraform -chdir=infra/ephemeral destroy`.
  4. If an ephemeral apply fails: `destroy`, then `apply` again (the DB password is written only on create).
  5. Switch the data layer at the demo: `aws ssm put-parameter --name /project-hub/db-backend --value sql --overwrite` and `aws ecs update-service --cluster project-hub --service project-hub-api --force-new-deployment`.
  6. Cost: ephemeral about $0.08 an hour; persistent a few cents a month; budgets $20 / month and $1 / day.
  7. Leftovers: Resource Groups → Tag Editor, tag `Project = project-hub` (or `Layer = ephemeral` after a destroy).
  8. State lives in `infra/*/terraform.tfstate` on this laptop only; keep it in a backup; never commit it.

- [ ] **Step 6: Run every check.** Expected: all exit 0. Grep `grep -rn 'data "aws_ssm_parameter"\|resource "random_password"' infra` → nothing; `grep -rniE '<company name>' infra README.md` → nothing (the controller runs this with the real name).

- [ ] **Step 7: Commit** `git add infra README.md && git commit -m "Bring up the API on RDS behind an HTTPS load balancer for a checkpoint" -m "..."`

---

## Criteria → task

| Criterion (design) | Task |
|---|---|
| 1 fmt, 2 validate, 3 tflint, 4 checkov | every task, set up in 1 |
| 5 terraform test guards | 1 (SG rules), 2 (trust) |
| 6 no company name | every task, checked in 5 and in final verification |
| 7 git-ignored state and tfvars | 1 (`.gitignore`), proven in 4 |
| 8 CI job green | 1, proven on the PR |
| 9–12 checkpoint | 5 (code + runbook); proven by the user after merge |
