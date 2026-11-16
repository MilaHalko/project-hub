# Epic 8b: Deploy on merge

Date: 2026-11-16
Status: approved (decisions taken from the roadmap and the brief of the coordinator session; Mila is short on tokens)
Roadmap: [`docs/PRDs/roadmap.md`](../../PRDs/roadmap.md), epic 8b

## Goal

Spec: CI/CD with "pushing to registry / deploy to cloud on merge". Every push to `main` pushes the
API image to ECR; when the ephemeral layer is up, it also rolls the ECS service out to that image.

## Non-goals

- No frontend hosting, no Terraform change (the OIDC role already has every permission needed),
  no change to the jobs `checks`, `docker`, `package`, `terraform`.
- No `terraform apply`, no AWS keys in GitHub.

## Approaches

1. **Own workflow `deploy.yml`, one job, AWS CLI + `jq` (chosen).** Self-contained, so a separate
   CI job from the Lambda fork merges cleanly. `main` is protected by the required checks, so every
   commit that reaches `main` has already passed them.
2. A job in `ci.yml` with `needs: [checks, docker]`. Same result, but edits the file that other
   branches also edit. Rejected for merge safety.
3. `aws-actions/amazon-ecs-*` actions. Two more third-party actions to pin and trust for a handful of
   CLI calls. Rejected.

## Design

- Triggers: push to `main`, `workflow_dispatch`. The job runs only on `refs/heads/main` (the role
  trusts nothing else) and only when the repository variable `AWS_DEPLOY_ROLE_ARN` is set.
- The image is `project-hub-api:<commit SHA>` (ECR tags are immutable). A re-run reuses an existing
  tag instead of failing on the push.
- The deploy runs only when the variable `ECS_DEPLOY_ENABLED` is `true` and the service is `ACTIVE`.
  It copies the task definition the service runs now, swaps the image (by digest, as Terraform does)
  in every container of this repository, registers it, updates the service, waits for it to be
  stable and checks that the new revision is the completed primary deployment (the circuit breaker
  rolls back silently otherwise).
- Terraform drift is documented in `infra/README.md` section 3.

## Acceptance criteria and proof

| # | Criterion | Proof |
|---|---|---|
| 1 | On a push to `main` with `AWS_DEPLOY_ROLE_ARN` set, the image is pushed to ECR tagged with the commit SHA through OIDC | `actionlint`; the real run after the merge |
| 2 | Without the variable, a merge does not fail | `actionlint`; job `if` reasoning; the real run |
| 3 | With `ECS_DEPLOY_ENABLED=true` and the service up, the service runs the new image and the run is red if ECS rolls back | `jq` rewrite tried on a sample task definition; the real run |
| 4 | With `ECS_DEPLOY_ENABLED` unset or `false`, the deploy steps are skipped | `actionlint`; the real run |
| 5 | The variables and the Terraform drift are documented | `infra/README.md` section 3 |
