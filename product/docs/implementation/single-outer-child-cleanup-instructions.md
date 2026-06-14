# Single Outer Child Cleanup Instructions

> Completed archival instruction sheet. This described the first cleanup slice
> before full legacy child runtime/code removal. Current state is summarized in
> [Single Outer Heimdall Direction](single-outer-heimdall-direction.md) and
> [Legacy Child Removal Note](legacy-child-removal-note.md).

This instruction sheet was used for the first code cleanup goal after adopting the
[Single Outer Heimdall Direction](single-outer-heimdall-direction.md).

## Goal

Implement the first cleanup slice for moving nested/child Heimdall out of the
primary product path:

- freeze new child project creation
- hide child controls from normal UI flows
- keep existing child data readable
- do not remove child schema, executor code, or runtime roots yet

## Repository Context

- Repository: `/Users/yoon/03_projects/04_my_vm_proxmox/02_Heimdall`
- Branch: `main`
- Python commands and pytest must use `product/apps/api/venv/bin/python`.
- Local tool state such as `.codex`, `.serena`, and `.pnpm-store` is not part
  of the product change.

## Product Direction

The primary supported self-hosting model is a single operator-managed Heimdall
API/Web instance on one VM.

Nested/child Heimdall is a legacy compatibility path. The code still exists and
must remain readable during the cleanup window, but normal users should not be
guided into creating new child projects.

## Safety Rules

- Do not delete child schema columns in this slice.
- Do not delete child executor code in this slice.
- Do not delete `/srv/heimdall/children` or any child runtime/project-volume
  root automatically.
- Do not break list/detail/read paths for existing projects with
  `run_as_heimdall_child=true`.
- Normal preview services must never receive child Docker socket mounts, child
  runtime mounts, or provider token/webhook secret env.
- Repo YAML, `build_env`, and `runtime_env` must not contain secret values,
  VM host paths, Docker socket paths, child runner settings, privileged mount
  declarations, or Heimdall server-only env.

## Backend Work

Freeze new child writes:

- Reject new project create payloads with top-level
  `run_as_heimdall_child=true`.
- Reject new multi-service payloads where any service has
  `run_as_heimdall_child=true`.
- Reject project patch/update payloads that try to set top-level or service
  `run_as_heimdall_child=true`.
- Return a clear 422 message explaining that nested/child Heimdall is
  legacy/deprecated and new child project creation is disabled.

Preserve compatibility:

- Existing database rows with child flags must remain readable through list and
  detail endpoints.
- Existing child metadata must not be silently removed during unrelated updates.
- If a patch explicitly clears child flags, allow it only if the implementation
  can do so without deleting child runtime data or breaking read compatibility.
  Otherwise leave clearing for a later migration tool.

Keep executor safety:

- Normal single-service deploys must not receive child mounts/env.
- Normal multi-service deploys must not receive child mounts/env.
- Web or frontend services must not receive Docker socket mounts, child runtime
  mounts, provider tokens, or webhook secrets.

## Frontend Work

Remove child creation from normal UI:

- Hide or disable the `Heimdall API child` checkbox in project create/edit
  flows.
- Do not emit `run_as_heimdall_child` in generated YAML previews for new
  projects.
- If an existing project already has child metadata, show it as legacy/read-only
  status instead of an editable control.

Keep YAML safe:

- YAML preview/import should not encourage child mode.
- Project YAML must continue to forbid child runner settings and secret values.

## Tests

Backend focused tests should cover:

- create project with top-level `run_as_heimdall_child=true` rejects
- create multi-service project with service `run_as_heimdall_child=true`
  rejects
- patch project to set `run_as_heimdall_child=true` rejects
- existing DB row with child flags remains list/get readable
- normal single-service and multi-service create/update still works
- normal executor deploys do not inject Docker socket, child env, provider
  tokens, or webhook secrets into normal services

Frontend focused tests or build checks should cover:

- child controls are absent or disabled in normal create/edit flows
- YAML preview does not suggest child mode for new projects
- existing child state, if displayed, is read-only legacy status

## Validation

Run the focused backend checks first:

```bash
product/apps/api/venv/bin/python -m pytest product/apps/api/tests/test_projects.py product/apps/api/tests/test_executor_local_docker.py
```

Then run the broader backend suite when practical:

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

## Out Of Scope

- Removing child DB columns or indexes
- Removing child executor code
- Deleting child roots under `/srv/heimdall/children`
- Implementing child migration or backup tooling
- Implementing managed Postgres provisioning
- Implementing the full `required_secrets` resolver/injection path

The next major implementation after this cleanup slice should be the
`required_secrets` resolver/injection path for application secrets and external
database URLs.
