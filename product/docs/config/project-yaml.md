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

## Forbidden In YAML

- GitHub token
- GitLab token
- webhook secret
- SSH private key
- raw env values
- database password
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
