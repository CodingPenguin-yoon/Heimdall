# Legacy Child Removal Instructions

> Archived instruction sheet. It records the legacy child-removal scope and may
> mention items that were out of scope for that cleanup. Use
> [Single Outer Heimdall Direction](single-outer-heimdall-direction.md) and
> [Managed Project PostgreSQL](../architecture/managed-project-postgresql.md)
> for current direction.

Use this instruction sheet for the next cleanup goal after
[Single Outer Child Cleanup Instructions](single-outer-child-cleanup-instructions.md).

## Goal

Remove the remaining nested/child Heimdall product surface now that new child
creation is frozen and the supported direction is one operator-managed outer
Heimdall instance.

This cleanup should make the normal codebase lighter by removing child runner
configuration, API fields, UI state, executor injection, and tests/docs that
exist only for creating or running child Heimdall projects.

## Suggested Goal Prompt

Implement legacy nested/child Heimdall removal using
`product/docs/implementation/legacy-child-removal-instructions.md`. Remove child
runner config, API/schema fields, executor child mounts/env injection, normal
Web child state/UI, and child-specific tests/docs from the supported product
path. Preserve normal single-outer project/deploy/provider/webhook/volume
behavior, do not delete `/srv/heimdall/children` automatically, and run the
documented validation.

## Repository Context

- Repository: `/Users/yoon/03_projects/04_my_vm_proxmox/02_Heimdall`
- Branch: `main`
- Python commands and pytest must use `product/apps/api/venv/bin/python`.
- Local tool state such as `.codex`, `.serena`, and `.pnpm-store` is not part
  of the product change.
- Phase 1 already freezes new `run_as_heimdall_child=true` writes and hides the
  normal Web child control.

## Product Direction

The supported self-hosting model is a single trusted Heimdall API/Web instance
on one VM.

Nested/child Heimdall is no longer a supported product path for this project.
Remove the code paths that keep the application prepared to create, deploy, or
operate child Heimdall instances.

## Preflight Inventory

Before destructive cleanup, inspect the current operator state:

- Query projects with `projects.run_as_heimdall_child=1`.
- Query services with `project_services.run_as_heimdall_child=1`.
- Check whether `/srv/heimdall/children` or environment-specific child roots
  contain data that the operator wants to keep.
- If child rows or roots exist, record them in the implementation notes and do
  not delete runtime data automatically.

If this repo is being used only for the single-outer instance and child data is
confirmed unused, it is acceptable to remove product code compatibility and
leave any runtime directory deletion as a manual operator action.

## Safety Rules

- Do not automatically delete `/srv/heimdall/children` or any child runtime or
  project-volume root.
- Do not remove non-child preview deployment, release, log, rollback, webhook,
  provider, or project-volume behavior.
- Normal preview services must never receive Docker socket mounts, child
  runtime mounts, child project-volume mounts, provider tokens, or webhook
  secrets.
- Repo YAML, `build_env`, and `runtime_env` must continue to reject secret
  values, VM host paths, Docker socket paths, privileged mount declarations,
  child runner settings, and Heimdall server-only env.
- If a DB schema simplification is too risky for one slice, prefer removing
  runtime/code usage first and leave explicit DB column removal to a migration
  follow-up.

## Backend Work

Remove child API and service behavior:

- Remove `run_as_heimdall_child` from public create/update request schemas.
- Remove `run_as_heimdall_child` from normal project/service response schemas
  if no compatibility response is required.
- Remove project normalization logic that reads, derives, validates, preserves,
  or writes child flags.
- Remove child write-freeze helper code added only to guard
  `run_as_heimdall_child=true` writes once the field is gone.
- Remove child runner validation from project create/update/deploy paths.
- Keep normal single-service and multi-service create/update behavior intact.

Remove child config behavior:

- Remove `HEIMDALL_CHILD_RUNNER_ENABLED`,
  `HEIMDALL_CHILD_ROOT_HOST`, and `HEIMDALL_CHILD_ROOT_CONTAINER` settings.
- Remove child path derivation helpers and validation routines.
- Keep normal runtime, preview port, provider, and project-volume settings.

Remove child executor behavior:

- Remove child project/service detection.
- Remove Docker socket, child runtime, child project-volume, provider token,
  and webhook secret injection for child containers.
- Remove child directory creation/checking code.
- Keep normal local Docker single-service and multi-service deploy behavior.
- Keep normal project volume mount behavior separate from the removed child
  runner path.

Database cleanup:

- Preferred final state: remove `run_as_heimdall_child` columns from `projects`
  and `project_services`, and remove
  `idx_project_services_one_child_per_project`.
- SQLite column removal may require table rebuild migration logic. If that
  would make the slice too large, document the remaining DB-only cleanup and
  leave unused legacy columns ignored by application code.
- Do not use DB cleanup as a reason to preserve child executor/config/UI code.

## Frontend Work

Remove remaining child UI/state:

- Remove `run_as_heimdall_child` from form defaults, loaded form state, and
  service form models.
- Remove read-only legacy child badges/callouts from normal project detail and
  edit flows.
- Ensure project save payloads cannot emit child flags.
- Ensure YAML previews do not mention child mode.
- Keep normal project create/edit, service editor, preview entry selection, and
  YAML preview behavior intact.

## Tests

Backend tests should be updated to prove:

- Normal single-service project create/list/get/update still works.
- Normal multi-service project create/list/get/update still works.
- Project volume create/update/deploy behavior still works.
- Normal executor single-service deploy does not include Docker socket mounts,
  child runtime mounts, child project-volume mounts, provider token env, or
  webhook secret env.
- Normal executor multi-service deploy does not include child mounts/env on any
  app or helper container.
- Provider/webhook/deployment suites still pass without child runner config.
- Request payloads containing removed child fields are rejected as unknown
  fields if schemas still use `extra="forbid"`.

Remove or rewrite tests that exist only to prove child runner creation,
child-specific env injection, child root validation, child deploy behavior, or
legacy child row read compatibility.

Frontend validation should cover or, if no test runner exists, build-check:

- No normal create/edit child controls or legacy child status UI remain.
- Save payload construction has no `run_as_heimdall_child` field.
- YAML preview has no child mode output.
- The Web build succeeds.

## Documentation Work

Update product docs so they describe the single-outer model only:

- Mark old nested/child implementation docs as archived or remove links from
  normal docs navigation.
- Remove runbook instructions that tell operators how to create or configure
  child Heimdall through the product UI/API.
- Keep any historical child docs clearly labeled as deprecated/archival if they
  remain in the repository.
- Keep the single-outer direction and project YAML safety rules.
- Keep explicit notes that runtime child roots are not deleted automatically.

## Validation

Run the focused backend checks first:

```bash
product/apps/api/venv/bin/python -m pytest product/apps/api/tests/test_projects.py product/apps/api/tests/test_executor_local_docker.py
```

Then run the broader backend suite:

```bash
product/apps/api/venv/bin/python -m pytest product/apps/api/tests
```

Run the Web build after frontend changes:

```bash
cd product/apps/web
pnpm build
```

Always finish with:

```bash
git diff --check
```

## Completion Checklist

- Child create/update/deploy code paths are gone from normal product code.
- Child runner environment settings are gone or no longer read by the app.
- Child Docker socket/runtime/provider-secret injection code is gone.
- Web child state/control/read-only legacy display is gone from normal UI.
- Tests no longer protect child runner behavior as a supported feature.
- Normal project, deployment, provider, webhook, and volume behavior still pass.
- Runtime child roots are not automatically deleted.
- Any leftover DB-only or archival-doc cleanup is explicitly documented.

## Out Of Scope

- Automatically deleting `/srv/heimdall/children`.
- Building a child migration or restore tool.
- Implementing managed Postgres provisioning.
- Implementing the full `required_secrets` resolver/injection path.
- Changing Heimdall's own database support beyond existing SQLite behavior.
