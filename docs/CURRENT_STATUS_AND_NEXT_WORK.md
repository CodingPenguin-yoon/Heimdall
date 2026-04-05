# Current Status And Next Work

This document captures the current shipped runtime behavior and the recommended next execution order. It is intentionally separate from roadmap and architecture docs, which include future intent.

## What Exists Now

- GitLab inventory, namespace lookup, and project creation exist.
- New GitLab repos created from Heimdall can seed a bootstrap draft `.heimdall/project.yaml` when `README` initialization is enabled.
- GitLab manifest validation now enforces the app deployment contract consumed by manual staging app deploy:
  - `deploy.strategy == docker-compose`
  - non-empty `deploy.compose_file`
  - positive integer `deploy.app_port`
  - non-empty `deploy.healthcheck_path` starting with `/`
  - `database.engine == postgres` when DB is required
- GitLab project settings exist, including staging readiness flags and staging infrastructure profile fields.
- GitLab System Hook ingress exists, but it currently updates inventory/readiness only.
- `Deploy Staging` already exists as a manual action.
- The current `Deploy Staging` path now performs manual staging infra plus app deployment:
  - template-clone VM creation
  - optional post-clone CPU/memory adjustment
  - SSH readiness wait
  - Ansible package/role post-processing
  - backend-side GitLab archive download for `deploy_branch`
  - remote archive extraction and `docker compose up -d --build`
  - HTTP healthcheck verification against `127.0.0.1:<app_port><healthcheck_path>`

## What Is Not Implemented Yet

- Bootstrap automation as a real execution flow
  - no bootstrap MR generation for existing repos
  - no direct-commit bootstrap execution from `bootstrap_strategy`
- Automatic deploy trigger from GitLab merge/webhook
- DB provisioner / automatic `DATABASE_URL` injection
- Production environment workflow
- Reverse-proxy / domain / TLS automation

## Current Safe Operating Model

Today the safe model is:

1. Discover or create the GitLab repo.
2. Ensure `.heimdall/project.yaml` exists and passes the runtime contract, including compose file, app port, and healthcheck path.
3. Save the staging infrastructure profile in GitLab Workspace.
4. Use manual `Deploy Staging` to create the environment and roll out the app bundle.
5. Treat merge/webhook events as readiness signals only, not deploy triggers.

This means the current platform is suitable for:

- onboarding projects into Heimdall
- creating the first staging VM/environment manually
- validating the staging app deployment path end-to-end

It is not yet the final model of “merge to branch -> app auto-redeploys”.

## Prioritized Remaining Work

1. Add DB automation.
   - Postgres provisioning and application connection injection.

2. Add webhook-driven staging redeploys.
   - Only after manual first-environment creation and manual app deployment are stable.

3. Add production workflow.
   - With stricter approval rules than staging.

## Recommended Execution Order

Recommended order for the next work is:

1. Keep first-environment creation manual.
2. Validate one project end-to-end in staging with the new app rollout path.
3. Only then add webhook-driven staging redeploys for already-prepared environments.
4. Add DB automation.
5. Add production flow last.

## Decision Rules

- Today, merge and webhook must not start deployment automatically.
- First environment creation stays manual.
- A future webhook trigger should only redeploy an already-prepared environment.
- Production should not inherit staging’s trigger rules by default; it should require stricter approval.

## Related Documents

- [README.md](../README.md)
- [GITLAB_BOOTSTRAP_STAGING_GUIDE.md](GITLAB_BOOTSTRAP_STAGING_GUIDE.md)
- [LOCAL_RUN_GUIDE.md](LOCAL_RUN_GUIDE.md)
- [platform/03_PROJECT_MANIFEST_SPEC.md](platform/03_PROJECT_MANIFEST_SPEC.md)
