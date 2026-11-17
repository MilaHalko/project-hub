# Cloud infrastructure

Terraform for the Project Hub API on AWS (region `eu-west-1`), in two layers:

- `infra/persistent/` is cheap and stays up: network, ECR, ECS cluster, S3 bucket, SSM settings, IAM roles, budget alerts.
- `infra/ephemeral/` is billed by the hour: RDS PostgreSQL, the HTTPS load balancer and the ECS service. Bring it up for a checkpoint, then destroy it.

The ephemeral layer finds persistent resources by name and tag, so the two layers share no state.

## 1. Once: the persistent layer

1. `export PATH="$HOME/.local/bin:$PATH"` (terraform, tflint and checkov are installed in `~/.local/bin`)
2. Sign in to the AWS CLI yourself. Never paste keys into chat or files. Terraform uses the same AWS credentials as the CLI; if you use a named profile, run `export AWS_PROFILE=<profile>` before the terraform commands.
3. `cp infra/persistent/terraform.tfvars.example infra/persistent/terraform.tfvars` and put your own address in `alert_email`, and the address the share email is sent from in `mail_sender` (see section 6). The file is git-ignored.
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

The web app needs an image in its own repository too. Build it from `frontend/` the same way and push it to `$(terraform -chdir=infra/persistent output -raw web_ecr_repository_url):$TAG`. It runs as the `web` container in the same task as the API: the load balancer sends every request to it, and nginx passes `/api/` on to the API over `127.0.0.1:8000`. Deploy on merge builds and pushes it too (section 3); the manual push is only for the very first checkpoint.

## 3. Deploy on merge

`.github/workflows/deploy.yml` runs on every push to `main` (and by hand from the Actions tab, on `main` only). It signs in to AWS through the OIDC role `project-hub-github-deploy`, which trusts only `refs/heads/main`; there are no AWS keys in GitHub.

Set two **repository variables** (GitHub, Settings, Secrets and variables, Actions, tab Variables; variables, not secrets):

| Variable | Value | Effect |
|---|---|---|
| `AWS_DEPLOY_ROLE_ARN` | `terraform -chdir=infra/persistent output -raw github_deploy_role_arn` | Not set: the workflow does nothing. Set: every merge builds the API and web images and pushes them to ECR. |
| `ECS_DEPLOY_ENABLED` | `true` while the ephemeral layer is up; delete it or set `false` otherwise | `true`: after the push, the ECS service is rolled out to the new image. |

Per checkpoint: after `terraform -chdir=infra/ephemeral apply` set `ECS_DEPLOY_ENABLED` to `true`; after `destroy` set it to `false`. If you forget, the run shows a warning and skips the rollout instead of failing.

On a merge the job:

1. builds the image for `linux/amd64` with `--provenance=false --sbom=false` and pushes it as `project-hub-api:<commit SHA>`; does the same for `frontend/` as `project-hub-web:<commit SHA>` (tags are immutable; a re-run finds the image already there and reuses it);
2. if `ECS_DEPLOY_ENABLED` is `true` and the service is active: copies the task definition the service runs now, replaces the image in the `migrate` and `api` containers with the new API digest and the one in the `web` container with the new web digest, registers it as a new revision, updates the service `project-hub-api` and waits until it is stable;
3. fails if ECS rolled the deploy back (circuit breaker), so a red run means the old version is still serving.

Terraform and the deploy:

- The ephemeral layer does not know about revisions registered by CI. On a normal checkpoint (`apply`, demo, `destroy`) there is no conflict: `apply` takes the newest ECR image and builds a fresh task definition.
- If you run `apply` on a layer that is already up, the plan shows the service's `task_definition` changing, because the service runs a CI revision. That is expected and safe: Terraform registers a revision with the newest ECR image, which is the one CI deployed.
- `ignore_changes` on the service was not added: it would stop Terraform from rolling out its own task definition changes.
- If the service was started before the `web` container existed, the first deploy-on-merge run fails at the task definition step (it expects both images). Run the ephemeral `apply` once, then the next merge deploys normally.
- CI cannot tag or deregister task definitions (no permission, and the role was left as it is). Its revisions have no tags, stay `ACTIVE` after `destroy`, and cost nothing.
- Merges that follow each other quickly: GitHub keeps only the newest waiting run, so an in-between commit may not get its own image.

## 4. Checkpoint

```bash
terraform -chdir=infra/ephemeral init
terraform -chdir=infra/ephemeral apply
```

This takes about 10 minutes. Then check:

```bash
curl -ksS -o /dev/null -w '%{http_code}\n' "$(terraform -chdir=infra/ephemeral output -raw url)/api/health"
curl -sS -o /dev/null -w '%{http_code} %{redirect_url}\n' "http://$(terraform -chdir=infra/ephemeral output -raw alb_dns_name)/api/health"
```

The first must print `200`, the second `301` with an `https://` address. The same address serves the site (`/`), the API (`/api/...`) and Swagger (`/docs`); Swagger sends its requests through `/api`. The certificate is self-signed, so a browser shows a warning once; `curl -k` skips it.

When the checkpoint is done, stop the billing:

```bash
terraform -chdir=infra/ephemeral destroy
```

## 5. If an ephemeral apply fails

Run `destroy`, then `apply` again. The database password is written only when the database is created, so a half-finished apply cannot be repaired in place.

### If the apply hangs

The service waits for a healthy task, so a broken task makes `apply` wait and then fail. Look at the CloudWatch log group `/ecs/project-hub-api` (streams `migrate/...` and `api/...`) and at the stopped-task reason in the ECS console (cluster `project-hub`, service `project-hub-api`, Tasks tab, Stopped).

If uploads over 1 MB fail because the root filesystem is read-only, set `readonlyRootFilesystem = false` on the `api` container in `infra/ephemeral/service.tf` and apply again.

## 6. Share by email (Amazon SES)

In AWS the API sends the share email through the SES API with the task role: no SMTP password and no keys anywhere. Locally and in CI it still goes over SMTP to Mailpit (`APP_MAIL_BACKEND` defaults to `smtp`).

AWS denied production access, so the account stays in the SES **sandbox**: SES delivers only to addresses it has verified. The app handles that itself, only in SES mode.

**Once, after the persistent `apply`:** AWS emails a verification link to `mail_sender`. Open it (check spam) and click it. Until you do, nothing can be sent. Check with `aws ses list-identities --region eu-west-1`. Apply the persistent layer before the ephemeral one: the task reads `mail-from` at start.

**What the app does when the owner shares to an address:**

1. It asks SES whether the address is a verified identity (`GetEmailIdentity`).
2. Verified: the invitation is sent right away, as locally.
3. Not known to SES: the app asks SES to verify it (`CreateEmailIdentity`), and AWS sends that person a verification email. The share link is created and stored, but no invitation is mailed yet. The API answer has a `message` field and the web app shows it: the recipient must first click the AWS email, then the owner shares again. A repeated share replaces the old link, so the second one is mailed.
4. Known but not yet clicked: the same message, no new AWS email.

**At the demo:**

1. Open the web app (`terraform -chdir=infra/ephemeral output -raw url`), a project, the members panel, "Send a link by email".
2. For a new address, the web app says to ask the person to click the AWS email. Once they have, share again: the invitation arrives, and the link opens the join page of the deployed web app.
3. To avoid waiting on stage, share to the demo addresses and let them click the AWS email beforehand.
4. Without the web app: `curl -k -H "Authorization: Bearer $TOKEN" "$URL/api/project/<id>/share?with=friend@example.com"` with a token from `POST /api/login`.
5. Swagger (`$URL/api/docs`) opens behind the load balancer, but its page fetches `/openapi.json` from the site root, where the web app answers instead of the API, so "Try it out" is not usable there.

**Permissions of the task role:** `ses:SendEmail` / `ses:SendRawEmail` only with the sender as From address (condition `ses:FromAddress`), plus `ses:GetEmailIdentity` and `ses:CreateEmailIdentity`. SES identity permissions can only be limited to "any identity in this account and region", because the recipients are not known in advance. The role can neither delete nor change identities.

**Limits and leftovers:**

- Identities created by the app stay in SES (and are free). They are not in Terraform: remove them in the SES console, Identities, if you want a clean account.
- A verification link is valid for 24 hours. If a recipient let it expire, delete their identity in the SES console and share again.
- Any signed-in project owner can make AWS send a verification email to any address (a project holds at most 10 pending links). Accepted for the demo; a public product would need a stricter limit.
- When an address is not verified, the API log group `/ecs/project-hub-api` has no error: that is a normal answer. A real SES failure logs `share mail could not be sent` with the reason (`ClientError`).

## 7. Switch the data layer at the demo

```bash
aws ssm put-parameter --region eu-west-1 --name /project-hub/db-backend --value sql --overwrite
aws ecs update-service --region eu-west-1 --cluster project-hub --service project-hub-api --force-new-deployment
```

Use `orm` as the value to switch back.

To rotate the JWT secret, raise `value_wo_version` in `infra/persistent/ssm.tf`, apply the persistent layer and force a new deployment as above. Every issued token becomes invalid.

## 8. Cost

- Ephemeral layer: about $0.08 an hour while it is up, nothing after `destroy`.
- Persistent layer: a few cents a month.
- Budget alerts go to your email at $20 a month and $1 a day.

## 9. Leftovers

If you are unsure whether something is still running, open Resource Groups, then Tag Editor, and search by tag `Project = project-hub`. After a `destroy`, search `Layer = ephemeral`: the result should be empty apart from INACTIVE ECS task definition revisions: they keep the tag, are free and can be ignored.

## 10. State

Terraform state lives in `infra/*/terraform.tfstate` on this laptop only. Keep a backup and never commit it.
