# Project Config YAML

## Decision

Use `.heimdall/project.yaml` as a repository-owned build/runtime specification.

Do not use it as Heimdall operational state.

```text
.heimdall/project.yaml
= how this app should be built and checked

Heimdall DB/runtime
= where this app is assigned, what ran, current release, logs, secrets
```

## UI-first Policy

The MVP should be UI-first.

```text
User registers repo in Web UI
-> Heimdall validates settings
-> Heimdall stores settings/state in SQLite
-> Heimdall can import/export .heimdall/project.yaml
```

This lets Heimdall prevent:

- duplicate preview ports
- invalid Dockerfile paths
- unsupported deploy modes
- unsafe path traversal
- invalid health checks
- accidental secret commits

## Recommended Schema

```yaml
version: 1

project:
  name: sample-preview
  type: web

source:
  tracked_branch: main

build:
  mode: dockerfile
  context: .
  dockerfile: Dockerfile

runtime:
  container_port: 3000
  health_check_path: /health
  startup_timeout_seconds: 60

services:
  frontend:
    path: frontend
    container_port: 3000
  backend:
    path: backend
    container_port: 8000
  database:
    required: false
    type: postgres
    env_prefix: DATABASE
```

## Allowed In YAML

- project name
- project type
- tracked branch
- deploy mode
- build context path
- Dockerfile path
- compose file path after compose support exists
- container internal port
- health check path
- startup timeout
- frontend/backend relative paths
- database requirement metadata
- required environment variable names
- future logical volume needs by `name`, `target_path`, and `read_only`

## Forbidden In YAML

- GitHub token
- GitLab token
- webhook secret
- SSH private key
- raw env values
- database password
- secret values of any kind
- VM host filesystem paths
- Docker socket paths such as `/var/run/docker.sock`
- Docker daemon configuration
- child runner settings such as `run_as_heimdall_child`
- privileged deploy profiles or privileged mount declarations
- raw `docker.sock`, host path, or privileged Docker mount declarations
- Heimdall runtime directories
- `HEIMDALL_RUNTIME_DIR`
- `HEIMDALL_DATABASE_URL`
- `HEIMDALL_REPO_ROOT`
- `HEIMDALL_VOLUME_ROOT_HOST`
- `HEIMDALL_VOLUME_ROOT_CONTAINER`
- `HEIMDALL_CHILD_RUNNER_ENABLED`
- `HEIMDALL_CHILD_ROOT_HOST`
- `HEIMDALL_CHILD_ROOT_CONTAINER`
- generated project-volume host sources
- assigned preview host port
- current commit
- current image tag
- deployment logs
- release history
- rollback state

## Port Rule

```text
container_port
= app internal port
= can be stored in YAML

preview_port / host_port
= Heimdall-assigned external port
= stored in DB
= should not be committed to repo config
```

## Storage Rule

Repo YAML must not store host paths or Docker privileges. It must never choose
where a bind mount source lives on the VM, request child-runner mode, set child
root env, declare privileged mounts, or request access to
`/var/run/docker.sock`.

DB/API logical volumes are the current Phase 1 source of truth. YAML
import/export for volumes remains future, and the current executor does not
generate project bind mounts. A future YAML shape may declare only logical
volume needs matching the API model:

```yaml
volumes:
  - name: uploads
    target_path: /app/uploads
    read_only: false
  - name: static-cache
    target_path: /app/.cache/static
    read_only: false
```

In that future YAML model, Heimdall generates the host source under its managed
`project-volumes` root and stores the generated mapping as operational state.
The repo supplies intent; Heimdall supplies placement.

The implementation plan for that future model is
[Docker Project Volume Support Implementation Plan](../implementation/docker-project-volume-support.md).

## Source Of Truth Phases

Phase 1:

```text
DB is source of truth.
YAML schema is documented and optional.
```

Phase 2:

```text
If YAML exists, import it and prefill the UI.
User reviews and saves into DB.
```

Phase 3:

```text
UI can generate YAML preview/export.
User approves before writing to repo.
```

Phase 4:

```text
Heimdall can create config update PR/MR.
Direct push to main is disabled by default.
```
