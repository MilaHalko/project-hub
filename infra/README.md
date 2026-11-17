# Cloud infrastructure

Terraform for the Project Hub API on AWS (region `eu-west-1`), in two layers:

- `infra/persistent/` is cheap and stays up: network, ECR, ECS cluster, S3 bucket, SSM settings, IAM roles, budget alerts.
- `infra/ephemeral/` is billed by the hour: RDS PostgreSQL, the HTTPS load balancer and the ECS service. Bring it up for a checkpoint, then destroy it.

The ephemeral layer finds persistent resources by name and tag, so the two layers share no state.

## 1. Once: the persistent layer

1. `export PATH="$HOME/.local/bin:$PATH"` (terraform, tflint and checkov are installed in `~/.local/bin`)
2. Sign in to the AWS CLI yourself. Never paste keys into chat or files. Terraform uses the same AWS credentials as the CLI; if you use a named profile, run `export AWS_PROFILE=<profile>` before the terraform commands.
3. `cp infra/persistent/terraform.tfvars.example infra/persistent/terraform.tfvars` and put your own address in `alert_email`, the sender in `mail_sender` and the people you will demo the share email to in `mail_recipients` (see section 6). The file is git-ignored.
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

The web app needs an image in its own repository too. Build it from `frontend/` the same way and push it to `$(terraform -chdir=infra/persistent output -raw web_ecr_repository_url):$TAG`. It runs as the `web` container in the same task as the API: the load balancer sends every request to it, and nginx passes `/api/` on to the API over `127.0.0.1:8000`. Deploy on merge does not build it yet; after a new web image, run the ephemeral `apply` again.

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

```bash
terraform -chdir=infra/ephemeral init
terraform -chdir=infra/ephemeral apply
```

This takes about 10 minutes. Then check:

```bash
curl -ksS -o /dev/null -w '%{http_code}\n' "$(terraform -chdir=infra/ephemeral output -raw url)/api/health"
curl -sS -o /dev/null -w '%{http_code} %{redirect_url}\n' "http://$(terraform -chdir=infra/ephemeral output -raw alb_dns_name)/api/health"
```

The first must print `200`, the second `301` with an `https://` address. The certificate is self-signed, so a browser shows a warning once; `curl -k` skips it.

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

**Once, after the persistent `apply`:**

1. AWS emails a verification link to `mail_sender` and to every address in `mail_recipients`. Open each inbox (check spam) and click the link. The identity stays "pending" until you do; check with `aws ses list-identities --region eu-west-1`.
2. A new SES account is in the **sandbox**: it sends only to verified addresses, so every person who must get a mail has to be in `mail_recipients` and must have clicked the link. To mail anyone, request production access in the SES console (Account dashboard, Request production access); AWS answers in about a day. Not needed for the demo.
3. To add a recipient later, add the address to `mail_recipients`, run the persistent `apply`, click the new link.

The persistent layer holds the identities (so verification survives `destroy` of the ephemeral layer), the `/project-hub/mail-from` parameter and the permission `ses:SendEmail` for the sender only. The ephemeral layer sets `APP_MAIL_BACKEND=ses`, `APP_MAIL_FROM` and `APP_PUBLIC_URL` / `APP_WEB_URL` (the load balancer URL), so the link in the mail opens the join page of the deployed web app. Apply the persistent layer before the ephemeral one: the task reads `mail-from` at start.

**At the demo**, share to a verified address:

- In the web app (`terraform -chdir=infra/ephemeral output -raw url`), open a project, go to the members panel and use "Send a link by email". Open the mail, click the link, sign in as that user and join.
- Or call the API with a token from `POST /api/login`: `curl -k -H "Authorization: Bearer $TOKEN" "$URL/api/project/<id>/share?with=friend@example.com"`.
- Swagger (`$URL/api/docs`) opens behind the load balancer, but its page fetches `/openapi.json` from the site root, where the web app answers instead of the API, so "Try it out" is not usable there. Use the web app or curl.

A recipient that is not verified gets no mail; the API log group `/ecs/project-hub-api` then has the line `share mail could not be sent` with the reason (`ClientError`).

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
