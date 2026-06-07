# Docker Project Volume Support Implementation Plan

## Status

In progress.

Current code performs real single-service Dockerfile deploys and multi-service
Dockerfile deploys when `dry_run=false`, but preview containers do not receive
generated project bind mounts. `HEIMDALL_VOLUME_ROOT_HOST` and
`HEIMDALL_VOLUME_ROOT_CONTAINER` are implemented as optional settings for API
logical volume validation and persistence; executor-generated bind mounts are
not implemented. `HEIMDALL_CHILD_RUNNER_ENABLED`,
`HEIMDALL_CHILD_ROOT_HOST`, and `HEIMDALL_CHILD_ROOT_CONTAINER` are implemented
for the separate nested child API minimum slice.

The architecture source of truth is
[Self-hosting Storage Architecture](../architecture/self-hosting-storage.md).
This document is the implementation plan for that storage contract.

## Goals

- Add per-service logical persistent volumes for single-service and
  multi-service Dockerfile preview deploys.
- Keep VM host paths out of UI, API input, and repo YAML.
- Generate bind source directories under the managed `project-volumes` root.
- Use explicit Docker `--mount type=bind` arguments instead of short `-v`
  syntax for generated project volumes.
- Preserve existing deploy behavior when no volumes are configured.

## Non-goals

- External database provisioning or managed external DB support.
- Docker Compose support.
- Arbitrary host path mounts.
- Mounting `docker.sock` into user preview containers.
- Child Heimdall instance auto-generation or child env-file generation.
- Nested child API deployment. The child runner may mount a
  `project-volumes` root into an inner Heimdall API, but that is not the same
  as mounting project volumes into user preview containers.
- Rollback of mounted application data.

## Boundary With Nested Heimdall Child Deploy

The nested child plan and this project-volume plan touch the same storage name
but at different layers:

- The nested child runner mounts
  `{HEIMDALL_CHILD_ROOT_HOST}/{project_id}/project-volumes` into the inner
  Heimdall API at `/host/project-volumes`.
- This volume plan later teaches the inner executor to mount generated
  `project-volumes/{project_id}/{service_id}/{volume_id}` directories into
  user preview containers with Docker `--mount type=bind`.
- Current completed volume work is DB/API/settings/validation only. User
  preview container runtime mounts remain Phase 3 executor work.

## Storage Model

Heimdall should keep three paths conceptually separate:

```text
VM host source path
  path passed to Docker as the bind mount src

API container management path
  path Heimdall uses to create, inspect, and delete source directories

Project container target path
  user-declared absolute path inside the preview container
```

Generated physical source paths must use immutable IDs rather than project
slugs, service names, or logical volume names:

```text
{HEIMDALL_VOLUME_ROOT_HOST}/{project_id}/{service_id}/{volume_id}
{HEIMDALL_VOLUME_ROOT_CONTAINER}/{project_id}/{service_id}/{volume_id}
```

Slugs and service names remain display and Docker naming inputs; they must not
determine persistent data placement. A project slug rename must not change the
physical volume path. A service or volume rename may retain data only when it is
an explicit rename of the same immutable service or volume ID; deleting and
recreating a service or volume with the same name must not silently reattach old
data.

## Data Model Proposal

Prefer new tables over adding columns to existing tables. The current SQLite
bootstrap uses `CREATE TABLE IF NOT EXISTS` statements and has no migration
framework; additive tables are safer than altering existing project, service,
release, or deployment rows in place.

Add `project_service_volumes`:

```text
id TEXT PRIMARY KEY
project_id TEXT NOT NULL
service_id TEXT NOT NULL
service_display_name_snapshot TEXT NOT NULL
name TEXT NOT NULL
target_path TEXT NOT NULL
read_only INTEGER NOT NULL DEFAULT 0
source_relative_path TEXT NOT NULL
status TEXT NOT NULL DEFAULT 'active'
created_at TEXT NOT NULL
updated_at TEXT NOT NULL

UNIQUE(project_id, service_id, name)
FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
```

`source_relative_path` should be generated once as
`{project_id}/{service_id}/{id}` and never recomputed from slugs or names.
`service_id` must be an immutable logical service ID. For single-service
Dockerfile projects, Heimdall can synthesize service `app`, but that synthesis
still needs a stable service identity before volumes are created.

Add a release-time mount manifest, for example
`release_service_volume_mounts`:

```text
id TEXT PRIMARY KEY
release_id TEXT NOT NULL
release_service_id TEXT
project_id TEXT NOT NULL
service_id TEXT NOT NULL
project_service_volume_id TEXT NOT NULL
service_display_name_snapshot TEXT NOT NULL
volume_name_snapshot TEXT NOT NULL
target_path TEXT NOT NULL
read_only INTEGER NOT NULL DEFAULT 0
source_relative_path TEXT NOT NULL
host_source_path TEXT NOT NULL
container_source_path TEXT NOT NULL
created_at TEXT NOT NULL

UNIQUE(release_id, project_service_volume_id)
FOREIGN KEY(release_id) REFERENCES releases(id) ON DELETE CASCADE
FOREIGN KEY(project_service_volume_id) REFERENCES project_service_volumes(id)
```

The release manifest records what was mounted at deploy time. It is also the
minimum state needed to explain rollback behavior later. API reads can expose
logical volume fields and generated metadata such as IDs, status, and relative
source paths where appropriate, but must not accept arbitrary host source input.

## API And Schema Proposal

Project create/update accepts logical volumes under each service:

```json
{
  "services": [
    {
      "name": "api",
      "build_context_path": "api",
      "dockerfile_path": "api/Dockerfile",
      "container_port": 8000,
      "public": true,
      "volumes": [
        {
          "name": "uploads",
          "target_path": "/app/uploads",
          "read_only": false
        }
      ]
    }
  ]
}
```

For single-service Dockerfile projects, the API can synthesize a service named
`app` so the same volume model applies:

```json
{
  "volumes": [
    {
      "name": "uploads",
      "target_path": "/app/uploads",
      "read_only": false
    }
  ]
}
```

The write schema must not include fields such as `source`, `src`,
`host_path`, `host_source`, `bind_source`, `volume_root`, or Docker mount
options. Read schemas may include generated IDs and relative source metadata
for audit/debugging, but generated absolute host paths should stay out of
normal UI/API responses unless a later operator-only surface explicitly needs
them.

## Settings Proposal

Add optional settings:

```text
HEIMDALL_VOLUME_ROOT_HOST
HEIMDALL_VOLUME_ROOT_CONTAINER
```

Both settings are optional when no project uses volumes. If any active project
or deployment request uses volumes, Heimdall must fail closed when either value
is missing, non-absolute, symlinked, outside the expected mounted root, or
inconsistent with the other root.

Validation can only be best-effort because the API process cannot prove every
Docker daemon namespace detail from inside the container. Heimdall should:

- require both roots to be absolute paths
- reject symlinked roots
- create/check source directories only through the container root path
- pass Docker only the VM host root-derived path
- optionally write/read a root sentinel file through the container path and
  verify the operator configured the matching VM path

Operators remain responsible for mounting the same storage at both roots.

## Validation Rules

Project volume validation must reject:

- logical names that are not DNS-ish labels using lowercase letters, digits,
  and hyphens, with alphanumeric start and end characters
- logical names containing `/`, `.`, `..`, or empty segments
- duplicate logical names per service
- duplicate target paths per service
- container targets that are not absolute POSIX paths
- target path traversal after normalization
- target paths equal to or under `/var/run/docker.sock`
- target paths equal to or under `/proc`, `/sys`, `/dev`, or
  `/var/lib/docker`
- target paths equal to or under Heimdall runtime, secret, or env paths such as
  `/var/lib/heimdall`, `/var/lib/heimdall/secrets`, or
  `/var/lib/heimdall/env`
- API or YAML host source fields
- symlinked roots or generated source directories
- reserved Docker mount propagation flags, privileged flags, or other raw
  Docker run options
- shell interpolation or shell-built Docker command strings

Executor validation must repeat the filesystem checks at the Docker boundary.
API validation protects users; executor validation protects the host.

## Executor Behavior

When a service has configured volumes:

1. Resolve the generated relative path from immutable IDs.
2. Create the source directory using the API container management root.
3. Verify the created directory is not a symlink and remains under the
   container root.
4. Derive the Docker host source from `HEIMDALL_VOLUME_ROOT_HOST`.
5. Add explicit Docker mount arguments:

```text
--mount type=bind,src={host_source},dst={target_path}
```

If `read_only=true`, append the Docker `readonly` option:

```text
--mount type=bind,src={host_source},dst={target_path},readonly
```

The same mount assembly must be used by both single-service
`_replace_container` and multi-service `_replace_service_container`. Existing
label-scoped container and network cleanup must remain unchanged; volume
directories are not removed as part of normal container replacement.

Logs should prefer logical volume name, service name, target path, and generated
volume ID. If a command log includes generated host sources, the root and full
source path should be redacted consistently with existing token redaction.

## UI And YAML Behavior

The UI should ask only for:

- logical volume name
- service
- container mount target
- read-only toggle

It must not show a host path field.

Repo YAML may later declare logical intent only:

```yaml
services:
  api:
    volumes:
      - name: uploads
        target_path: /app/uploads
        read_only: false
```

YAML must exclude generated source paths, volume roots, root environment
variables, secret values, assigned ports, deployment logs, release history,
rollback state, delete/purge state, and any arbitrary Docker mount options.

## Delete And Rename Policy

Project delete should retain volume data by default. Purge requires an explicit
application-data confirmation separate from project metadata/container cleanup.

Purge must be symlink-safe:

- resolve the configured container root
- compute the project subtree from immutable project ID
- refuse deletion if any path component is a symlink
- refuse deletion unless the final path remains under the configured root
- delete only the immutable project ID subtree

A project slug rename must not change the physical volume path. A project
delete/recreate must receive a new project ID and must not attach old data
silently, even if the slug is reused.

Service and volume renames must preserve data only when the same immutable ID is
renamed through an explicit update flow. If the implementation cannot
distinguish rename from delete/create, it should block the operation or require
an explicit user choice rather than silently reattaching data by name.

## Rollback Policy

Image rollback does not roll back mounted application data. Until the release
mount manifest and UI messaging are implemented, rollback should remain
disabled for releases that use generated project volumes.

If rollback is enabled later, Heimdall must:

- read the release-time mount manifest
- recreate containers with the same volume mount set
- clearly message that mounted data remains at its current state
- avoid promising point-in-time data restore

## Phased Implementation Plan

### Phase 1: Settings And Schema

Add optional settings, root validation helpers, `project_service_volumes`, and
release-time mount manifest tables.

Current code implements the optional volume-root settings, fail-closed root
helper, and additive volume tables.

Acceptance criteria:

- existing databases start without manual migration steps
- no-volume projects work when volume roots are unset
- projects with volumes fail closed when either root is missing or invalid
- project volume records use immutable IDs for source paths

Tests:

- config roots optional without volumes
- missing/inconsistent roots fail with volumes
- schema creates new tables on an existing DB
- slug rename does not change generated relative source path

### Phase 2: API Validation And Reads

Add request/read schemas and service-volume persistence.

Current code implements project logical volume request/read validation and DB
persistence; generated executor mount use remains in Phase 3.

Acceptance criteria:

- single-service Dockerfile projects can use synthesized service `app`
- multi-service projects can attach volumes to specific services
- API rejects host source fields and unsafe targets
- reads return logical volume state and generated IDs without accepting host
  source input

Tests:

- valid volume create/update
- duplicate names and target paths rejected
- target traversal and reserved paths rejected
- host path/source fields rejected

### Phase 3: Executor Mounts

Create source directories and add Docker `--mount type=bind` arguments in both
single-service and multi-service run paths.

Acceptance criteria:

- no-volume Docker argv remains unchanged
- volume Docker argv uses `--mount type=bind,src=...,dst=...`
- `readonly` is added only for read-only volumes
- label-scoped cleanup behavior is unchanged
- generated host source values are redacted from logs

Tests:

- `_replace_container` argv with and without volumes
- `_replace_service_container` argv with and without volumes
- source directory creation through container root
- symlinked roots/source dirs rejected
- log redaction covers generated host sources

### Phase 4: Delete, Purge, And Rename

Add explicit purge flow and rename semantics.

Acceptance criteria:

- project delete retains volume data by default
- purge requires explicit confirmation
- purge deletes only immutable project ID subtree
- project delete/recreate does not reattach old data
- service/volume rename behavior is explicit and tested

Tests:

- delete retains sources
- purge removes expected subtree
- purge refuses symlink/path traversal
- slug rename keeps path
- recreate with same slug gets new path

### Phase 5: UI And YAML Intent

Add UI controls and, later, YAML logical intent import/export.

Acceptance criteria:

- UI has no host path field
- UI submits only logical volume name, service, target path, and read-only
- YAML preview/import excludes generated sources and operational state
- YAML remains repo-safe

Tests:

- UI payload excludes host paths
- YAML export excludes roots, sources, secrets, ports, logs, releases, rollback,
  and delete/purge state
- YAML import rejects host source fields

### Phase 6: Rollback Messaging

Keep rollback disabled for volume-backed releases until mount manifests and
clear user messaging are available.

Acceptance criteria:

- releases with volumes either cannot be rolled back or are rolled back with the
  recorded mount manifest
- UI/API message says mounted data is not rolled back

Tests:

- rollback disabled behavior for volume-backed releases
- release mount manifest stored on successful deploy
- rollback response includes data-state warning if enabled

## Test Matrix

| Area | Coverage |
| --- | --- |
| Config | roots optional without volumes; both required with volumes; non-absolute, missing, symlinked, or inconsistent roots fail closed |
| Project validation | logical name rules; duplicate volume names; duplicate targets; reserved targets; host source fields rejected |
| Executor argv | no-volume regression; single-service `--mount`; multi-service `--mount`; `readonly`; no shell interpolation |
| Migration | new tables created for existing DBs; existing project rows unchanged; no migration framework assumptions hidden |
| Delete/purge | delete retains data; explicit purge confirmation; symlink-safe purge; project delete/recreate isolation |
| YAML exclusion | generated sources, roots, secrets, assigned ports, logs, releases, rollback, and delete/purge state omitted |
| UI payload | service, logical name, target path, and read-only only; no host path field |
| Single/multi-service regression | existing no-volume single-service and multi-service deploys keep current behavior |
| Missing roots | volume-backed deploy fails before Docker run when roots are unset or inconsistent |
| Symlink/path traversal | root symlinks, source symlinks, target traversal, and host source escape attempts rejected |
| Logs/redaction | generated host roots and source paths redacted; logical volume details remain useful |
| Rollback | image rollback does not claim data rollback; volume-backed releases disabled or manifest-backed with warning |

## Open Decisions

- Root mapping sentinel: should Heimdall require a sentinel file to prove the
  host and container roots point at the same storage, or keep this as
  best-effort validation plus operator responsibility?
- Log redaction vs operator-only logs: should generated host source paths always
  be redacted, or can an operator-only log view show them?
- Stable service IDs: should `project_services` stop using replace-on-update
  semantics, or should a new immutable service identity table back persistent
  volumes?
- Purge UX timing: should purge be offered during project delete, after delete
  from an archived project view, or as a separate application-data action?
