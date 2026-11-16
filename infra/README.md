# Cloud infrastructure

Terraform for the Project Hub API on AWS (region `eu-west-1`), in two layers:

- `infra/persistent/` is cheap and stays up: network, ECR, ECS cluster, S3 bucket, SSM settings, IAM roles, budget alerts.
- `infra/ephemeral/` is billed by the hour: RDS PostgreSQL, the HTTPS load balancer and the ECS service. Bring it up for a checkpoint, then destroy it.

The ephemeral layer finds persistent resources by name and tag, so the two layers share no state.

## 1. Once: the persistent layer

1. `export PATH="$HOME/.local/bin:$PATH"` (terraform, tflint and checkov are installed in `~/.local/bin`)
2. Sign in to the AWS CLI yourself. Never paste keys into chat or files. Terraform uses the same AWS credentials as the CLI; if you use a named profile, run `export AWS_PROFILE=<profile>` before the terraform commands.
3. `cp infra/persistent/terraform.tfvars.example infra/persistent/terraform.tfvars` and put your own address in `alert_email`. The file is git-ignored.
4. `terraform -chdir=infra/persistent init && terraform -chdir=infra/persistent apply`
5. In the Billing console, open Budgets and check that both budgets list your address.

An AWS account can have only one OIDC provider for `token.actions.githubusercontent.com`. If one already exists, the apply fails. Then import it with `terraform -chdir=infra/persistent import aws_iam_openid_connect_provider.github <its ARN>`, or delete the unused one (preferred). After an import the persistent layer owns the provider: a persistent `destroy` deletes it and `apply` resets its `client_id_list`.

## 2. First image (only before the first deploy-on-merge run)

The ephemeral layer needs an image in ECR. Push one by hand:

```bash
aws ecr get-login-password --region eu-west-1 | docker login --username AWS --password-stdin <account id>.dkr.ecr.eu-west-1.amazonaws.com
TAG=manual-$(git rev-parse --short HEAD)-$(date +%Y%m%d%H%M%S)
docker build --platform linux/amd64 --provenance=false --sbom=false -t <ecr_repository_url>:$TAG .
docker push <ecr_repository_url>:$TAG
```

ECR tags are immutable, so the tag must be new each time. `--provenance=false --sbom=false` keeps Docker Desktop (containerd store) from pushing an index with an attestation manifest; the ephemeral layer picks the most recent image and ECS could fail to pull the attestation.

`ecr_repository_url` is an output of the persistent layer: `terraform -chdir=infra/persistent output -raw ecr_repository_url`.

## 3. Deploy on merge

`.github/workflows/deploy.yml` runs on every push to `main` (and by hand from the Actions tab, on `main` only). It signs in to AWS through the OIDC role `project-hub-github-deploy`, which trusts only `refs/heads/main`; there are no AWS keys in GitHub.

Set two **repository variables** (GitHub, Settings, Secrets and variables, Actions, tab Variables; variables, not secrets):

| Variable | Value | Effect |
|---|---|---|
| `AWS_DEPLOY_ROLE_ARN` | `terraform -chdir=infra/persistent output -raw github_deploy_role_arn` | Not set: the workflow does nothing. Set: every merge builds the image and pushes it to ECR. |
| `ECS_DEPLOY_ENABLED` | `true` while the ephemeral layer is up; delete it or set `false` otherwise | `true`: after the push, the ECS service is rolled out to the new image. |

Per checkpoint: after `terraform -chdir=infra/ephemeral apply` set `ECS_DEPLOY_ENABLED` to `true`; after `destroy` set it to `false`. If you forget, the run shows a warning and skips the rollout instead of failing.

On a merge the job:

1. builds the image for `linux/amd64` with `--provenance=false --sbom=false` and pushes it as `project-hub-api:<commit SHA>` (tags are immutable; a re-run finds the image already there and reuses it);
2. if `ECS_DEPLOY_ENABLED` is `true` and the service is active: copies the task definition the service runs now, replaces the image in the `migrate` and `api` containers with the new digest, registers it as a new revision, updates the service `project-hub-api` and waits until it is stable;
3. fails if ECS rolled the deploy back (circuit breaker), so a red run means the old version is still serving.

Terraform and the deploy:

- The ephemeral layer does not know about revisions registered by CI. On a normal checkpoint (`apply`, demo, `destroy`) there is no conflict: `apply` takes the newest ECR image and builds a fresh task definition.
- If you run `apply` on a layer that is already up, the plan shows the service's `task_definition` changing, because the service runs a CI revision. That is expected and safe: Terraform registers a revision with the newest ECR image, which is the one CI deployed.
- `ignore_changes` on the service was not added: it would stop Terraform from rolling out its own task definition changes.
- CI cannot tag or deregister task definitions (no permission, and the role was left as it is). Its revisions have no tags, stay `ACTIVE` after `destroy`, and cost nothing.
- Merges that follow each other quickly: GitHub keeps only the newest waiting run, so an in-between commit may not get its own image.

## 4. Checkpoint

The ephemeral layer also deploys the storage usage Lambda (`project-hub-storage-usage`), which keeps each project's total file size up to date from S3 events (S3, EventBridge, SQS, Lambda). Before the first apply, and after every change in `src/project_hub/storage_usage/`:

1. Build the zip: `scripts/build_storage_usage_lambda.sh` (writes `dist/storage-usage-lambda.zip`; Terraform reads it from `../../dist/` by default, override with `-var storage_usage_zip=<path>`).
2. Apply the persistent layer first (it adds the bucket notification, the S3 gateway endpoint, the Lambda's role, security group and log group): `terraform -chdir=infra/persistent apply`.
3. Then the ephemeral layer, as below.

```bash
terraform -chdir=infra/ephemeral init
terraform -chdir=infra/ephemeral apply
```

This takes about 10 minutes. Then check:

```bash
curl -ksS -o /dev/null -w '%{http_code}\n' "$(terraform -chdir=infra/ephemeral output -raw url)/health"
curl -sS -o /dev/null -w '%{http_code} %{redirect_url}\n' "http://$(terraform -chdir=infra/ephemeral output -raw alb_dns_name)/health"
```

The first must print `200`, the second `301` with an `https://` address. The certificate is self-signed, so a browser shows a warning once; `curl -k` skips it.

To check the Lambda, upload or delete a file in a project, wait a few seconds, then:

```bash
aws logs tail /aws/lambda/project-hub-storage-usage --region eu-west-1 --since 15m
aws sqs get-queue-attributes --region eu-west-1 --attribute-names ApproximateNumberOfMessages \
  --queue-url "$(aws sqs get-queue-url --region eu-west-1 --queue-name project-hub-storage-usage-dlq --query QueueUrl --output text)"
```

The log group shows one run per batch of events, with a `storage usage counted` line for each project and its new total. A `storage usage not stored` line means the row was not written (the project was deleted, or a newer count was already stored); it is not an error. The dead-letter queue `project-hub-storage-usage-dlq` must stay at `0`: a message there is an event that failed five times (read it in the SQS console, then fix the cause). The ephemeral layer adds an SSM interface endpoint (about $0.01 an hour per subnet) for the Lambda; `destroy` removes it. Its private DNS sends every SSM call in the VPC through it, so it also admits the API tasks, which read their secrets from SSM when they start.

When the checkpoint is done, stop the billing:

```bash
terraform -chdir=infra/ephemeral destroy
```

## 5. If an ephemeral apply fails

Run `destroy`, then `apply` again. The database password is written only when the database is created, so a half-finished apply cannot be repaired in place.

### If the apply hangs

The service waits for a healthy task, so a broken task makes `apply` wait and then fail. Look at the CloudWatch log group `/ecs/project-hub-api` (streams `migrate/...` and `api/...`) and at the stopped-task reason in the ECS console (cluster `project-hub`, service `project-hub-api`, Tasks tab, Stopped).

If uploads over 1 MB fail because the root filesystem is read-only, set `readonlyRootFilesystem = false` on the `api` container in `infra/ephemeral/service.tf` and apply again.

## 6. Switch the data layer at the demo

```bash
aws ssm put-parameter --region eu-west-1 --name /project-hub/db-backend --value sql --overwrite
aws ecs update-service --region eu-west-1 --cluster project-hub --service project-hub-api --force-new-deployment
```

Use `orm` as the value to switch back.

To rotate the JWT secret, raise `value_wo_version` in `infra/persistent/ssm.tf`, apply the persistent layer and force a new deployment as above. Every issued token becomes invalid.

## 7. Cost

- Ephemeral layer: about $0.08 an hour while it is up, nothing after `destroy`.
- Persistent layer: a few cents a month.
- Budget alerts go to your email at $20 a month and $1 a day.

## 8. Leftovers

If you are unsure whether something is still running, open Resource Groups, then Tag Editor, and search by tag `Project = project-hub`. After a `destroy`, search `Layer = ephemeral`: the result should be empty apart from INACTIVE ECS task definition revisions: they keep the tag, are free and can be ignored.

## 9. State

Terraform state lives in `infra/*/terraform.tfstate` on this laptop only. Keep a backup and never commit it.
