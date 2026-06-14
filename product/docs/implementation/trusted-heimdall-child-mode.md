# Nested Heimdall Child Deploy Implementation Plan

> Deprecated legacy path. Nested/child Heimdall is historical context, not the
> supported self-hosting model. Current database direction is documented in
> [Managed Project PostgreSQL](../architecture/managed-project-postgresql.md)
> and [Single Outer Heimdall Direction](single-outer-heimdall-direction.md).

## Status

Minimum API-only child runner slice implemented.

The architecture source of truth is
[Self-hosting Storage Architecture](../architecture/self-hosting-storage.md).
This document defines the first operable slice for an outer Heimdall instance to
deploy an inner Heimdall API as a child project.

Related docs:

- [Docker Project Volume Support Implementation Plan](docker-project-volume-support.md)
- [Self-hosting Docker Runbook](../operations/self-hosting-docker.md)
- [Project Config YAML](../config/project-yaml.md)

## Current State

- Operators manually run the outer Heimdall API/Web today.
- Inner Heimdall can run manually when an operator mounts
  `/var/run/docker.sock`, a runtime root, and a project-volume root into the
  inner API container.
- Normal single-service and multi-service Dockerfile previews exist.
- Logical project volumes have DB/API validation and persistence; executor bind
  mounts for user preview containers are still pending.
- Nested child deploy support is implemented for one operator-marked inner
  Heimdall API service. Single-service projects use the project flag; a
  multi-service project must mark exactly one service as the child API service.

## Problem Statement

An inner Heimdall API must access the VM Docker daemon to deploy user preview
containers. If it is deployed as an ordinary preview container, it must not get
that access.

`/var/run/docker.sock` is equivalent to VM-level Docker control. Heimdall must
mount it only into the one operator-approved inner Heimdall API container and
must never mount it into normal user preview containers.

## Public And Implementation Names

Use simple child-runner names:

- UI label: `Heimdall API child`
- API/DB boolean: `run_as_heimdall_child` on the project summary and on the
  selected service
- server env gate: `HEIMDALL_CHILD_RUNNER_ENABLED`
- child root env:
  `HEIMDALL_CHILD_ROOT_HOST` and `HEIMDALL_CHILD_ROOT_CONTAINER`

Do not expose the old trusted child profile name as a public API, DB, UI, or
YAML value. The word trusted may appear in security explanations only.

## Goals

- Let the operator use the outer Heimdall UI to deploy the inner Heimdall API
  by marking exactly one service as `Heimdall API child`.
- Store the request as `run_as_heimdall_child=true` on that service, with the
  project-level boolean kept as a compatibility summary.
- Enforce a fail-closed server-side gate before accepting or executing that
  mode.
- Derive child paths from server-side roots plus immutable `project_id`.
- Mount Docker socket, child runtime, and child project-volume root only into
  the child API container.
- Keep ordinary user preview containers without Docker socket access.

## Non-goals

- Automatic outer Heimdall lifecycle management.
- Automatic inner Web deploy.
- Multi-service child API/Web lifecycle orchestration beyond selecting the one
  API service that receives the child runner mounts/env.
- Child env-file generation or full child lifecycle/env-file automation.
- Runtime project-volume mounts into user preview containers.
- Arbitrary host path mounts.
- User-provided Docker run options.
- General privileged container support.
- Mounting `/var/run/docker.sock` into user app preview containers.

## Minimum Operable Slice

The first slice is intentionally small:

- The operator starts and maintains the outer Heimdall manually.
- The operator registers the inner Heimdall API in the outer UI as either a
  single-service Dockerfile project or one service inside a multi-service
  Dockerfile project.
- The operator marks exactly one service as `Heimdall API child`.
- The API stores service-level `run_as_heimdall_child=true` and keeps the
  top-level project flag as a compatibility summary.
- The executor treats `child_id` as `project_id`.
- The executor adds the fixed child mounts/env only to that one inner API
  container.

Explicit exclusions for this slice:

- no automatic inner Web deployment
- no automatic multi-service child API/Web lifecycle orchestration
- no env-file automation for the child
- no user preview project-volume runtime mounts
- no automatic child deletion, upgrade, or lifecycle workflow

The slice makes existing no-volume preview deploys possible from the inner API
because the inner API receives Docker socket access. Volume-backed user previews
must still fail closed or remain hidden until project-volume executor mounts are
implemented.

## Outer Prerequisites

The outer API container must already be started by the operator with Docker
access and the child root mounted:

```text
/var/run/docker.sock:/var/run/docker.sock
{HEIMDALL_CHILD_ROOT_HOST}:{HEIMDALL_CHILD_ROOT_CONTAINER}
```

Example operator env for the outer API:

```env
HEIMDALL_CHILD_RUNNER_ENABLED=true
HEIMDALL_CHILD_ROOT_HOST=/srv/heimdall/children
HEIMDALL_CHILD_ROOT_CONTAINER=/host/children
```

These are server-only values. UI, API request payloads, and repo YAML must not
provide child root paths or Docker socket paths.

## Fail-closed Gate

When `run_as_heimdall_child=true`, the server must reject the project or deploy
unless all child-runner requirements pass:

- `HEIMDALL_CHILD_RUNNER_ENABLED=true`
- `HEIMDALL_CHILD_ROOT_HOST` is present, absolute, existing, and not a symlink
- `HEIMDALL_CHILD_ROOT_CONTAINER` is present, absolute, existing, and not a
  symlink
- generated child paths normalize under the configured child root
- multi-service child mode marks exactly one service as
  `run_as_heimdall_child`

Child root settings are optional for normal projects. The gate is evaluated
only when `run_as_heimdall_child` is requested.

Hardening phases can add sentinel/root mapping checks to prove that the host and
container roots point at the same storage. The minimum slice requires only the
root checks above plus generated path containment.

## Child Mount And Env Contract

For `child_id=project_id`, the outer executor creates/checks these
container-visible paths:

```text
{HEIMDALL_CHILD_ROOT_CONTAINER}/{project_id}/runtime
{HEIMDALL_CHILD_ROOT_CONTAINER}/{project_id}/project-volumes
```

Docker bind mount sources use VM host paths:

```text
{HEIMDALL_CHILD_ROOT_HOST}/{project_id}/runtime
{HEIMDALL_CHILD_ROOT_HOST}/{project_id}/project-volumes
```

Only the child API container receives:

```text
/var/run/docker.sock:/var/run/docker.sock
{HEIMDALL_CHILD_ROOT_HOST}/{project_id}/runtime:/var/lib/heimdall
{HEIMDALL_CHILD_ROOT_HOST}/{project_id}/project-volumes:/host/project-volumes
```

The child API receives these env values via Docker `--env` args:

```env
HEIMDALL_RUNTIME_DIR=/var/lib/heimdall
HEIMDALL_DATABASE_URL=sqlite:////var/lib/heimdall/state/heimdall.db
HEIMDALL_VOLUME_ROOT_HOST={HEIMDALL_CHILD_ROOT_HOST}/{project_id}/project-volumes
HEIMDALL_VOLUME_ROOT_CONTAINER=/host/project-volumes
```

When set on the outer API, these provider settings are also passed only to the
child API container and are omitted when unset:

```env
HEIMDALL_GITHUB_API_TOKEN
HEIMDALL_GITHUB_WEBHOOK_SECRET
HEIMDALL_GITLAB_BASE_URL
HEIMDALL_GITLAB_API_TOKEN
HEIMDALL_GITLAB_WEBHOOK_SECRET
```

The minimum slice does not create or pass a child env file.

## UI, API, And YAML Rules

UI behavior:

- show an operator-facing per-service checkbox labeled `Heimdall API child`
- selecting one child service clears the child flag from all other services
- submit only `run_as_heimdall_child`; never submit child roots or Docker socket
  paths
- do not show host path, Docker socket, child root, privileged, or raw Docker
  option fields

API behavior:

- default `run_as_heimdall_child` to `false`
- persist the service boolean and keep the project boolean as a summary for
  compatibility
- reject `run_as_heimdall_child=true` unless the server gate passes
- for multi-service projects, reject child mode unless exactly one service is
  marked `run_as_heimdall_child=true`
- forbid fields such as `host_path`, `child_root`, `docker_sock`,
  `docker_args`, `mounts`, `volumes_from`, `privileged`, or raw bind sources

Repo YAML must not declare the child runner, privileged deploy profiles, child
root env, Docker socket access, host paths, or raw Docker options.

## Interaction With Project Volumes

Nested child API roots and user preview project-volume mounts are separate.

The child runner gives the inner Heimdall API:

- Docker daemon access
- its own runtime root
- its own project-volume root
- `HEIMDALL_VOLUME_ROOT_HOST`
- `HEIMDALL_VOLUME_ROOT_CONTAINER`

That does not mean user preview containers receive project-volume bind mounts.
The inner executor still needs the managed `--mount type=bind` implementation
described in
[Docker Project Volume Support Implementation Plan](docker-project-volume-support.md).

## Phased Implementation Plan

### Phase 1: Settings, Boolean, And Guardrails

- Add server-only child root settings.
- Add `HEIMDALL_CHILD_RUNNER_ENABLED` config gating.
- Add API/project-summary and service persistence for `run_as_heimdall_child`.
- Default the boolean to `false`.
- Reject child mode when the config flag is disabled or child roots are missing
  or invalid.
- Reject host path and raw Docker option fields.

### Phase 2: Minimum Child API Executor

- Use `project_id` as `child_id`.
- Create/check generated child directories through
  `HEIMDALL_CHILD_ROOT_CONTAINER`.
- Build Docker mounts from `HEIMDALL_CHILD_ROOT_HOST`.
- Add Docker socket, runtime, and project-volume root mounts only for the child
  API container.
- Inject child env with Docker `--env` args and do not create an env file.
- In multi-service projects, add the child mounts/env only to the one marked
  service and reject zero-or-many child selections.
- Preserve normal preview argv when `run_as_heimdall_child=false`.

### Later Phases

- Add authenticated operator-only controls after the env gate.
- Add sentinel/root mapping hardening.
- Decide whether and how to automate inner Web deployment.
- Connect inner child volume roots to managed preview volume mounts after the
  project-volume executor phase exists.
- Add child lifecycle operations only after the single-service API slice works.

## Acceptance Criteria And Tests

Minimum operable acceptance:

- `run_as_heimdall_child=true` requires the enabled server gate and valid child
  roots.
- `child_id == project_id`.
- The executor creates/checks child directories under the container root and
  uses host-root paths as Docker bind mount sources.
- The child API Docker argv includes only the approved Docker socket, runtime,
  project-volume root, and env values.
- No `--env-file` is generated or used for the child.
- Normal project Docker argv is unchanged.
- Multi-service child projects require exactly one marked child API service;
  unmarked services and health helper containers do not receive child mounts/env.
- Ordinary user preview containers never receive `/var/run/docker.sock`.
- No test asserts that user preview project-volume mounts work yet.

Suggested tests:

- settings validation accepts a complete child-runner configuration
- settings validation rejects missing or invalid child roots when the boolean is
  requested
- API schema accepts and defaults `run_as_heimdall_child`
- project and service persistence roundtrip `run_as_heimdall_child`
- project validation rejects child mode when server config is disabled
- project validation rejects multi-service child mode with zero or multiple
  marked child services
- request schema rejects host path and raw Docker option fields
- child executor argv includes the fixed approved mounts/env only on the marked
  child API service and no env file
- normal single-service and multi-service argv stay unchanged
- symlinked roots and generated child path escapes are rejected
