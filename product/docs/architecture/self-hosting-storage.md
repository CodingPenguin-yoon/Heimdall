# Self-hosting Storage Architecture

## Decision Summary

The supported self-hosting model is one operator-managed Heimdall API/Web
instance on a single VM.

Nested/child Heimdall is a deprecated legacy path. Normal product code no
longer creates, deploys, or operates child Heimdall instances. Existing child
runtime roots, if any, remain operator-owned data and are not deleted
automatically.

Current implementation:

- The API supports `HEIMDALL_RUNTIME_DIR`, `HEIMDALL_DATABASE_URL`,
  `HEIMDALL_PUBLIC_BASE_URL`, `HEIMDALL_PREVIEW_HOST`,
  `HEIMDALL_PREVIEW_PORT_START`, `HEIMDALL_PREVIEW_PORT_END`,
  provider token/webhook environment variables, `HEIMDALL_GITLAB_BASE_URL`,
  `HEIMDALL_REPO_ROOT`, `HEIMDALL_VOLUME_ROOT_HOST`, and
  `HEIMDALL_VOLUME_ROOT_CONTAINER`.
- `HEIMDALL_DATABASE_URL` defaults to `sqlite:///...` and also supports
  operator-managed `postgresql://...` or `postgres://...` for Heimdall control
  state only.
- The API image listens on `8000` and expects its runtime directory at
  `/var/lib/heimdall`.
- The Web image serves nginx on `80`, bakes `VITE_API_BASE_URL` at build time,
  and does not proxy `/api`.
- The product includes a single-VM operator Compose file for API, Web,
  `heimdall-postgres` control storage, and `project-postgres` for managed
  project application databases.
- A manual deploy with `dry_run=false` performs real local Dockerfile deploys.
- `build_env` values are passed as Docker build args. `runtime_env` values are
  passed as container environment variables.
- Uploaded service `.env` bundles are stored as secret files under
  `HEIMDALL_RUNTIME_DIR/secrets/env-bundles`; only metadata is stored in the
  control database and deployments inject them with Docker `--env-file`.
- Preview containers do not receive generated bind mounts today.
- The API has a logical project-volume DB/read/write model; UI, YAML
  import/export, and executor bind-mount generation remain pending.
- Project `deploy_mode=compose` is unsupported and rejected.

## Canonical VM Layout

Use `/srv/heimdall` as the Heimdall root:

```text
/srv/heimdall/
  config/
    api.env
  runtime/
    state/
      heimdall.db  # SQLite only; absent for PostgreSQL-backed Compose
    logs/
      deployments/
    workspaces/
    secrets/
      env-bundles/
  control-postgres/  # Heimdall control DB data for the product Compose path
  project-postgres/  # project app DB data for managed project DBs
```

Legacy child roots may still exist under `/srv/heimdall/children`. Treat them
as archived product-instance data: back them up before cleanup and delete them
only after explicit operator confirmation.

## Folder Roles

| VM path | Role | Container path | Backup policy |
| --- | --- | --- | --- |
| `/srv/heimdall/config` | Operator-owned env files and launch config. | Usually mounted as env files or read by Docker run options. | Back up after redacting secrets where copies are shared. |
| `/srv/heimdall/runtime` | Heimdall runtime root. | `/var/lib/heimdall` in the API container. | Back up for restore. |
| `/srv/heimdall/runtime/state` | SQLite database and durable API state when SQLite is used. | `/var/lib/heimdall/state` | Back up before upgrades and deletes. For control PostgreSQL, back up the database volume or use Postgres-native backups. |
| `/srv/heimdall/runtime/logs` | Deployment logs. | `/var/lib/heimdall/logs` | Back up if audit history matters. |
| `/srv/heimdall/runtime/workspaces` | Git workspaces used during deployment. | `/var/lib/heimdall/workspaces` | Disposable; can be repaired by refetching repos. |
| `/srv/heimdall/runtime/secrets` | Ignored runtime secret material, including managed DB passwords and env bundles. | `/var/lib/heimdall/secrets` | Back up securely, never commit. |
| `/srv/heimdall/runtime/secrets/env-bundles` | Service `.env` bundles uploaded through Heimdall. | `/var/lib/heimdall/secrets/env-bundles` | Back up securely; raw env values must not be copied into the control DB, API responses, UI state, or deployment logs. |
| `/srv/heimdall/control-postgres` | Product Compose Heimdall control Postgres data directory. | `/var/lib/postgresql/data` in `heimdall-postgres`. | Back up with Postgres-native backups or a coordinated stopped-volume backup. |
| `/srv/heimdall/project-postgres` | Product Compose project application Postgres data directory. | `/var/lib/postgresql/data` in `project-postgres`. | Back up with Postgres-native backups or a coordinated stopped-volume backup before purge or restore work. |

## Volume Roots

The future project-volume contract needs two roots because the Heimdall API
container and Docker daemon see paths from different namespaces.

```text
HEIMDALL_VOLUME_ROOT_HOST
= absolute directory on the VM host
= path passed to Docker as the bind mount source

HEIMDALL_VOLUME_ROOT_CONTAINER
= same storage as seen inside the Heimdall API container
= path the API process uses to create, inspect, and manage directories
```

For a generated physical relative source path:

```text
{project_id}/{service_id}/{volume_id}
```

Heimdall should translate it as:

```text
host source:
  {HEIMDALL_VOLUME_ROOT_HOST}/{project_id}/{service_id}/{volume_id}

API container management path:
  {HEIMDALL_VOLUME_ROOT_CONTAINER}/{project_id}/{service_id}/{volume_id}

project container target:
  user-declared absolute container path, for example /app/uploads
```

The current API validates and persists logical volume definitions. Executor
bind-mount generation remains pending.

## Trust Boundary

Mounting `/var/run/docker.sock` gives the Heimdall API process access to the VM
Docker daemon. A process with that access can create containers, mount host
paths into containers, publish ports, read container metadata, stop containers,
and often escalate to broad host control through Docker features.

Operational requirements:

- Mount the Docker socket only into the trusted Heimdall API container.
- Do not mount the Docker socket into user project preview containers.
- Do not allow repo YAML or UI inputs to specify arbitrary host source paths.
- Treat Docker socket access as VM-level administrative trust, not a narrow
  container-management permission.
- Run untrusted user workloads on a separate VM or with stronger isolation
  before accepting multi-tenant use.

## Backup And Delete Policy

Back up before upgrades:

- `config/`
- `runtime/state/`
- Control PostgreSQL backups instead of `runtime/state/` when
  `HEIMDALL_DATABASE_URL` points at Postgres. For the product Compose path, the
  data directory is `/srv/heimdall/control-postgres`.
- Project PostgreSQL backups from `/srv/heimdall/project-postgres` once
  managed project databases are enabled.
- `runtime/logs/` if audit history matters
- `runtime/secrets/`, including `runtime/secrets/env-bundles`
- future `project-volumes/` application data
- existing legacy child roots only when retaining or migrating them

Usually disposable:

- `runtime/workspaces/`
- failed temporary build outputs
- preview containers that can be recreated from a release image or a new deploy

Project delete should be explicit about data loss:

- stop/remove only Heimdall-managed containers and networks for the project
- remove release metadata and logs according to retention policy
- delete future `project-volumes/{project_id}` only after an explicit
  application-data confirmation
- retain managed project PostgreSQL databases by default and purge them only
  after exact typed application-data confirmation

## Current Gaps

- Preview containers do not receive generated bind mounts.
- Preview executors do not yet create generated user project-volume
  directories.
- The API model for logical project volumes exists; UI support is pending.
- There is no repo YAML parser/import flow for logical volumes.
- Project `deploy_mode=compose` is unsupported.
- The Web image does not proxy `/api`.
- Automatic SQLite-to-PostgreSQL data migration is not implemented.
- Managed project PostgreSQL live smoke tests, backups, orphan adoption,
  password rotation, PITR, and HA remain operator-managed or future work.

## Implementation Follow-ups

Track generated project-volume mounts in
[Docker Project Volume Support Implementation Plan](../implementation/docker-project-volume-support.md).
Track managed project application databases in
[Managed Project PostgreSQL](managed-project-postgresql.md).
The old nested child deploy plan remains only as deprecated historical context:
[Nested Heimdall Child Deploy Implementation Plan](../implementation/trusted-heimdall-child-mode.md).

- Use `HEIMDALL_VOLUME_ROOT_HOST` and `HEIMDALL_VOLUME_ROOT_CONTAINER` for
  generated project volumes.
- Continue validating both roots are absolute and mounted-storage consistency
  before executor use.
- Extend the project-volume model into UI/YAML flows.
- Reject host paths, relative target paths, path traversal, symlink escapes, and
  reserved Docker socket targets.
- Generate host source paths under `project-volumes`.
- Add executor support for `--mount type=bind`.
- Test root translation, mount generation, read-only mounts, delete behavior,
  and log redaction.
