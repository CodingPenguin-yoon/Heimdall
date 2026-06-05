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

The current executor is a safe dry-run implementation. It records the deployment flow without cloning, building, or starting real containers.

## Runtime Directories

Runtime state should stay outside source files.

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

In the current dry-run executor:

- deployment status becomes `dry_run_success`
- release status becomes `simulated`
- no real current release is activated
- rollback is explicitly unsupported for simulated releases

## Future Executor Path

Keep the executor boundary clean:

```text
local_docker dry-run
-> local_docker real Dockerfile mode
-> compose mode
-> ssh_docker
-> runner
-> optional Gjallar target discovery
```

Do not add remote target or Gjallar concepts before real single-server Docker deployment works.

## Safety Rules

- only execute known Git/Docker operations
- never expose arbitrary shell command execution in UI
- restrict file paths to repo/runtime boundaries
- reject path traversal
- validate ports against configured ranges
- maintain one active deployment per project
- dedupe webhook delivery IDs
- redact token-like values from logs
