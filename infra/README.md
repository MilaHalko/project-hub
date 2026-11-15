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

## 2. First image (until the deploy pipeline exists)

The ephemeral layer needs an image in ECR. Push one by hand:

```bash
aws ecr get-login-password --region eu-west-1 | docker login --username AWS --password-stdin <account id>.dkr.ecr.eu-west-1.amazonaws.com
TAG=manual-$(git rev-parse --short HEAD)-$(date +%Y%m%d%H%M%S)
docker build --platform linux/amd64 --provenance=false --sbom=false -t <ecr_repository_url>:$TAG .
docker push <ecr_repository_url>:$TAG
```

ECR tags are immutable, so the tag must be new each time. `--provenance=false --sbom=false` keeps Docker Desktop (containerd store) from pushing an index with an attestation manifest; the ephemeral layer picks the most recent image and ECS could fail to pull the attestation.

`ecr_repository_url` is an output of the persistent layer: `terraform -chdir=infra/persistent output -raw ecr_repository_url`.

## 3. Checkpoint

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

When the checkpoint is done, stop the billing:

```bash
terraform -chdir=infra/ephemeral destroy
```

## 4. If an ephemeral apply fails

Run `destroy`, then `apply` again. The database password is written only when the database is created, so a half-finished apply cannot be repaired in place.

### If the apply hangs

The service waits for a healthy task, so a broken task makes `apply` wait and then fail. Look at the CloudWatch log group `/ecs/project-hub-api` (streams `migrate/...` and `api/...`) and at the stopped-task reason in the ECS console (cluster `project-hub`, service `project-hub-api`, Tasks tab, Stopped).

If uploads over 1 MB fail because the root filesystem is read-only, set `readonlyRootFilesystem = false` on the `api` container in `infra/ephemeral/service.tf` and apply again.

## 5. Switch the data layer at the demo

```bash
aws ssm put-parameter --region eu-west-1 --name /project-hub/db-backend --value sql --overwrite
aws ecs update-service --region eu-west-1 --cluster project-hub --service project-hub-api --force-new-deployment
```

Use `orm` as the value to switch back.

To rotate the JWT secret, raise `value_wo_version` in `infra/persistent/ssm.tf`, apply the persistent layer and force a new deployment as above. Every issued token becomes invalid.

## 6. Cost

- Ephemeral layer: about $0.08 an hour while it is up, nothing after `destroy`.
- Persistent layer: a few cents a month.
- Budget alerts go to your email at $20 a month and $1 a day.

## 7. Leftovers

If you are unsure whether something is still running, open Resource Groups, then Tag Editor, and search by tag `Project = project-hub`. After a `destroy`, search `Layer = ephemeral`: the result should be empty apart from INACTIVE ECS task definition revisions: they keep the tag, are free and can be ignored.

## 8. State

Terraform state lives in `infra/*/terraform.tfstate` on this laptop only. Keep a backup and never commit it.
