# Single Outer Heimdall Direction

## Decision

The supported self-hosting model is one operator-managed Heimdall API/Web
instance running on one VM. This Heimdall owns project registration, webhook
handling, preview deployment, release state, logs, and rollback control.

Nested or child Heimdall is no longer a supported product path. Normal product
code no longer exposes, creates, updates, deploys, or displays child Heimdall
projects.

## Why

The child model adds a second Heimdall control plane with its own database,
routing, secrets, Web image build-time API URL, Docker socket trust boundary,
backup policy, and cleanup lifecycle. That complexity competes with the product
goal of a reliable single-VM preview manager.

The near-term gap is better app dependency configuration: managed project
PostgreSQL, app secrets, and safe runtime injection. Solving that in the single
outer instance benefits every project without multiplying control planes.

## Current Operating Model

- Operators run one trusted Heimdall API container and one Web container.
- The API may mount `/var/run/docker.sock`; Web and normal preview containers
  must not.
- `HEIMDALL_DATABASE_URL` is Heimdall's control database only. It can use
  SQLite in local/dev or PostgreSQL in self-hosted operation.
- Project repo YAML must not contain secret values, VM host paths, Docker
  socket paths, child runner settings, privileged mounts, or Heimdall runtime
  directories.
- `build_env` and `runtime_env` remain non-secret project configuration and
  should continue to reject secret-looking or server-only values.
- `required_secrets` names are declaration-only today. They are not yet a
  resolver, storage mechanism, or injection path.
- Existing child runtime roots under `/srv/heimdall/children`, if any, are not
  deleted automatically.
- Existing SQLite legacy child columns may remain as DB-only cleanup until a
  future table-rebuild migration is explicitly worth the risk.

## DB And Secret Strategy

The next useful database slice is managed project PostgreSQL inside the single
outer Heimdall control plane:

- Keep repo YAML limited to required secret names and dependency intent.
- Keep Heimdall control DB state separate from project application DB data.
- Store managed project DB metadata and secret references in the control DB,
  never raw `DATABASE_URL` values.
- Resolve generated app DB passwords from first-class secret storage.
- Inject assembled app `DATABASE_URL` values into preview containers only at
  deploy time.
- Keep the provisioner/admin credential API-only and never inject it into
  preview containers.
- Attach DB-backed preview containers to the project DB network, never to
  `heimdall-control`.

The implementation source of truth is
[Managed Project PostgreSQL](../architecture/managed-project-postgresql.md).
Automatic SQLite-to-PostgreSQL migration for the control DB is not included.

## Legacy Cleanup State

The runtime/code removal is complete for the normal product path:

- Public create/update/read schemas no longer include `run_as_heimdall_child`.
- The Web form, YAML preview, and normal detail views no longer include child
  controls or status displays.
- Project persistence and deployment loading ignore legacy child flags.
- The local Docker executor no longer has child deployment gates, child root
  creation, Docker socket mounts for preview containers, child runtime mounts,
  provider token injection, or webhook secret injection.
- DB initialization no longer creates child columns or the legacy child-service
  uniqueness index. It drops the legacy index if present.

Remaining cleanup is operational or DB-only:

- Do not delete `/srv/heimdall/children` automatically.
- Back up and explicitly confirm before removing any legacy child runtime state
  or project-volume data.
- Leave existing SQLite legacy child columns ignored unless a future migration
  rebuilds the affected tables.

See [Legacy Child Removal Note](legacy-child-removal-note.md) for the recorded
preflight result and cleanup boundary.

## Validation Expectations

Current validation should focus on the supported single-outer path:

- Normal single-service and multi-service project create/list/detail/update
  still work.
- Deploy, release, log, rollback, provider, webhook, and project-volume behavior
  still work for normal projects.
- Payloads containing removed child fields reject as unknown fields.
- Normal preview containers do not receive Docker socket mounts, child runtime
  mounts, child project-volume mounts, provider token env, or webhook secret
  env.
- Repo YAML import should continue to reject child runner settings, host paths,
  Docker socket paths, secret values, and server-only Heimdall env vars.
