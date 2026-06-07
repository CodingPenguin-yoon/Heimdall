# Single-server Preview Architecture

## MVP Architecture

The MVP runs previews on the same server as Heimdall.

```text
GitHub/GitLab
  -> webhook
Heimdall API
  -> deployment record
Deployment worker/service
  -> workspace manager
  -> local Docker executor
Preview container on Heimdall server
```

The current executor performs real local Dockerfile deploys when
`dry_run=false`. Dry-run remains available as an explicit simulated deployment
mode.

## Runtime Directories

Runtime state should stay outside source files. In a source checkout this
defaults to `product-runtime/`. In the API image, the runtime directory is
`/var/lib/heimdall` and should be backed by a VM host bind mount.

```text
product-runtime/
  state/
    heimdall.db
  logs/
    deployments/
  workspaces/
  env/
  secrets/
```

Configurable environment variables:

```text
HEIMDALL_RUNTIME_DIR
HEIMDALL_DATABASE_URL
HEIMDALL_PUBLIC_BASE_URL
HEIMDALL_PREVIEW_HOST
HEIMDALL_PREVIEW_PORT_START
HEIMDALL_PREVIEW_PORT_END
```

For Docker self-hosting, nested Heimdall storage, host path mapping, and
`docker.sock` trust boundaries, see
[Self-hosting Storage Architecture](self-hosting-storage.md).

## Deployment Flow

Manual deploy is the first-class workflow.

```text
user clicks deploy
-> deployment row created
-> workspace step runs
-> build step runs
-> container step runs
-> health step runs
-> logs saved
-> release row created on success
```

When `dry_run=false`:

- the executor clones or fetches the repository workspace
- Dockerfile images are built with configured non-secret `build_env` values as
  build args
- preview containers are started with configured non-secret `runtime_env`
  values as environment variables
- health checks run against the preview target
- a successful deployment creates a non-dry-run current release

When `dry_run=true`:

- deployment status becomes `dry_run_success`
- release status becomes `simulated`
- no real current release is activated
- rollback is explicitly unsupported for simulated releases

Current limitations:

- preview containers do not receive generated bind mounts
- Compose mode is unsupported and rejected
- Docker bind mount source paths resolve on the Docker daemon host VM, not
  inside the Heimdall API container

## Executor Path

Keep the executor boundary clean:

```text
local_docker dry-run simulation
local_docker real Dockerfile mode
local_docker real multi-service Dockerfile mode
-> compose mode, future only
-> ssh_docker
-> runner
-> optional Gjallar target discovery
```

Do not add remote target or Gjallar concepts before the single-server Docker
contract remains stable.

## Safety Rules

- only execute known Git/Docker operations
- never expose arbitrary shell command execution in UI
- restrict file paths to repo/runtime boundaries
- reject path traversal
- validate ports against configured ranges
- maintain one active deployment per project
- dedupe webhook delivery IDs
- redact token-like values from logs
- treat `/var/run/docker.sock` as VM-level administrative trust when mounted
  into the API container
- never mount `/var/run/docker.sock` into user project preview containers
