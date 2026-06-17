# Env Bundle Support Specification

## Purpose

Add project service environment bundle support so Heimdall can manage app
runtime environment files without storing raw values in the control database.

The first target app is Gjallar, which needs many runtime values including
Proxmox tokens. Operators should be able to upload or replace a service `.env`
file and let Heimdall inject it at deploy time.

## Current State

Implemented today:

- `runtime_env` and `build_env` exist for non-secret values.
- Secret-looking `runtime_env` and `build_env` values are rejected.
- Managed project PostgreSQL stores generated database passwords under
  `settings.secrets_dir` and injects `DATABASE_URL` only at deploy time.
- Heimdall Compose already mounts
  `${HEIMDALL_RUNTIME_DIR_HOST:-/srv/heimdall/runtime}` to
  `/var/lib/heimdall`.

Missing today:

- Generic app secret injection.
- Service-level `.env` bundle upload and deploy-time injection.
- A control DB model that stores only env bundle refs, keys, and checksums.
- UI for replacing or deleting an uploaded env bundle.

## Goals

- Store uploaded `.env` bundle files under the existing Heimdall secret root.
- Keep raw env values out of the control database, API responses, UI state, and
  deployment logs.
- Add per-service env bundle metadata using stable project and service IDs.
- Inject env bundles into preview containers with Docker `--env-file`.
- Keep PostgreSQL-only self-hosting env setup clear and documented.
- Preserve current behavior for projects that do not configure env bundles.

## Non-goals

- External secret managers.
- Per-key secret editing in the first slice.
- Showing saved env values back to the UI.
- Storing raw env values in `runtime_env_json`.
- Adding a new env bundle root setting before there is a real override need.
- Docker Compose project deployment support.
- Production-grade secret rotation or audit events.

## Canonical Storage

Do not add a new `HEIMDALL_ENV_BUNDLE_ROOT` setting in the first slice.

Derive the env bundle root from existing runtime settings:

```text
API container path:
  {settings.secrets_dir}/env-bundles
  /var/lib/heimdall/secrets/env-bundles

VM host path:
  /srv/heimdall/runtime/secrets/env-bundles
```

Use immutable IDs for physical placement:

```text
env-bundles/
  projects/
    {project_id}/
      services/
        {service_id}/
          current.env
          versions/
            {bundle_id}.env
```

Project names, slugs, and service names are display values only. They must not
determine the physical file path.

## PostgreSQL-only Env Cleanup

Document and keep the supported PostgreSQL self-hosting env shape focused on:

```text
HEIMDALL_RUNTIME_DIR_HOST=/srv/heimdall/runtime
HEIMDALL_CONTROL_POSTGRES_DATA_DIR=/srv/heimdall/control-postgres
HEIMDALL_PROJECT_POSTGRES_DATA_DIR=/srv/heimdall/project-postgres
HEIMDALL_DATABASE_URL=postgresql://...
HEIMDALL_PROJECT_DATABASE_ADMIN_URL=postgresql://...
HEIMDALL_PROJECT_DATABASE_APP_HOST=project-postgres
HEIMDALL_PROJECT_DATABASE_APP_PORT=5432
HEIMDALL_PROJECT_DATABASE_NETWORK=heimdall-project-db
HEIMDALL_PUBLIC_BASE_URL=...
HEIMDALL_PREVIEW_HOST=...
HEIMDALL_PREVIEW_HEALTH_HOST=...
HEIMDALL_PREVIEW_PORT_START=18000
HEIMDALL_PREVIEW_PORT_END=18999
VITE_API_BASE_URL=...
HEIMDALL_API_PORT=8000
HEIMDALL_WEB_PORT=8080
provider token and webhook settings
```

`runtime/state` is not required for the control database when PostgreSQL is
used, but `runtime/secrets`, `runtime/logs`, and `runtime/workspaces` remain
required.

## Data Model

Add an additive table:

```text
project_service_env_bundles
  id TEXT PRIMARY KEY
  project_id TEXT NOT NULL
  service_id TEXT NOT NULL
  active_ref TEXT NOT NULL
  key_names_json TEXT NOT NULL DEFAULT '[]'
  checksum_sha256 TEXT NOT NULL
  created_at TEXT NOT NULL
  updated_at TEXT NOT NULL

  UNIQUE(project_id, service_id)
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
  FOREIGN KEY(service_id) REFERENCES project_services(id) ON DELETE CASCADE
```

`active_ref` is a relative secret-store ref, for example:

```text
env-bundles/projects/{project_id}/services/{service_id}/current.env
```

The table must not include raw env values.

## Env File Validation

The first slice should support normal line-oriented `.env` files:

```text
KEY=value
KEY="value"
KEY='value'
export KEY=value
blank lines
comment lines beginning with #
```

Reject:

- invalid env names
- duplicate keys
- multiline values
- lines without `=`
- `NUL` bytes
- files above a conservative size limit, for example 64 KiB

Preserve values as Docker-compatible env-file lines after validation. The API
may normalize quoting, but must not log or return values.

## API

Add service-level endpoints:

```text
POST   /api/projects/{project_id}/services/{service_id}/env-bundle
GET    /api/projects/{project_id}/services/{service_id}/env-bundle
DELETE /api/projects/{project_id}/services/{service_id}/env-bundle
```

The POST endpoint can accept raw `.env` text in the first slice. Multipart file
upload can be added if the Web UI needs it.

Read response shape:

```json
{
  "id": "envbundle_...",
  "project_id": "project_...",
  "service_id": "service_...",
  "configured": true,
  "key_names": ["GJALLAR_ENV", "PROXMOX_API_TOKEN_SECRET"],
  "checksum_sha256": "...",
  "updated_at": "..."
}
```

No response returns env values.

## Deploy Behavior

During deployment, load service env bundle metadata with project services.

For each service with an env bundle:

```text
docker run --env-file /var/lib/heimdall/secrets/env-bundles/.../current.env ...
```

The Docker CLI runs inside the Heimdall API container, so the env-file path
should be the API container path. Docker receives the resulting env values from
the CLI.

Conflict policy:

- If a key appears in both an env bundle and `runtime_env`, fail the deployment
  before starting containers.
- Managed database injection may intentionally set a secret env such as
  `DATABASE_URL`. If the env bundle also contains that same key, fail closed and
  tell the operator to remove one source.

Deployment logs may include:

```text
env bundle configured: true
env bundle keys: GJALLAR_ENV, PROXMOX_API_TOKEN_SECRET
env bundle checksum: ...
```

Logs must not include values.

## Web UI

Add an Env Bundle section per project service.

Display:

- configured or not configured
- key names
- checksum
- updated timestamp

Actions:

- Upload or replace `.env`
- Delete env bundle

Do not display saved values. Replacement is the recovery path.

## Operations

PostgreSQL-only VM layout:

```text
/srv/heimdall/
  config/
  runtime/
    logs/
    workspaces/
    secrets/
      env-bundles/
  control-postgres/
  project-postgres/
```

Do not use `/srv/heimdall/children` for this feature. It is legacy nested
Heimdall state.

Back up `runtime/secrets/env-bundles` securely. Treat it like provider tokens
and project database passwords.

## Acceptance Criteria

- Existing projects without env bundles deploy exactly as before.
- Env bundle upload stores a `0600` file under `settings.secrets_dir`.
- Env bundle metadata stores only ref, key names, checksum, and timestamps.
- GET response never includes values.
- Deployment uses `--env-file` for configured services.
- Duplicate or conflicting env keys fail before Docker containers are started.
- Logs and API responses do not include uploaded env values.
- Docs explain PostgreSQL-only folders and env variables.
