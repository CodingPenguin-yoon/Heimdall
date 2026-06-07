# Preview Deployment Pipeline

## Purpose

This document is the implementation reference for real single-server preview
deployments. The first real Dockerfile deploy path is now implemented; keep
dry-run language here only for the explicit simulated mode.

The target user flow is:

```text
register repository
-> validate provider access
-> click Deploy preview
-> clone or fetch tracked branch
-> build Docker image from Dockerfile
-> replace preview container
-> run health check
-> expose preview URL
-> record deployment, logs, and current release
```

Webhook registration is useful for automatic deploys after push events, but it is not required for manual deploy. Manual deploy must work first.

## Current State

Already implemented:

- provider tokens and webhook secrets loaded from local `.env`
- GitHub/GitLab repository access validation
- GitHub/GitLab webhook registration and reuse
- GitHub/GitLab webhook secret verification
- project registration and preview port allocation
- manual deploy endpoint
- deployment history, logs, and release records
- dry-run local Docker executor for simulated deploys
- real local Dockerfile deploys when `dry_run=false`
- multi-service Dockerfile preview deploys

Current deploy behavior:

```text
manual deploy with dry_run=false
-> clone or fetch tracked branch
-> build Docker image from Dockerfile
-> replace preview container
-> health check
-> release status current on success

manual deploy with dry_run=true
-> dry-run log
-> deployment status dry_run_success
-> release status simulated
```

## Non-goals For The Next Implementation Goal

Do not add these to the local Dockerfile executor contract:

- Kubernetes
- Proxmox, VM, or LXC lifecycle
- Gjallar host allocation
- remote Docker hosts
- docker-compose mode
- arbitrary shell command execution from UI
- direct editing of repository files
- production traffic routing
- additional orchestration beyond the current Dockerfile and multi-service
  Dockerfile modes
- secret values in DB, logs, UI, YAML preview, or generated `.heimdall/project.yaml`

## Real Deploy Behavior

The real Dockerfile deployment mode should keep dry-run available as an
explicit simulated mode.

Minimum real deploy behavior:

```text
POST /api/projects/{project_id}/deployments
-> reject if another deployment is active
-> read project settings
-> resolve provider token for project provider
-> clone repository if workspace does not exist
-> fetch latest tracked branch if workspace exists
-> checkout target commit or tracked branch
-> resolve actual commit SHA
-> build Docker image
-> stop/remove previous preview container for the project
-> run new container bound to assigned preview host port
-> run health check
-> mark release current on success
-> supersede previous current release
-> write sectioned logs
-> return DeploymentResult
```

The UI button should become operationally clear:

```text
Deploy preview
```

The UI should still label dry-run/simulated records distinctly when they exist.

## Runtime Layout

Use the existing runtime root:

```text
product-runtime/
  state/
    heimdall.db
  logs/
    deployments/
  workspaces/
    {project_id}/
      repo/
  env/
  secrets/
```

Workspace path rules:

- each project gets one workspace under `workspaces/{project_id}/repo`
- never clone into user-provided paths
- never use repo URL path segments as filesystem paths
- delete or repair a workspace only when it is inside the project runtime directory

## Provider Clone Strategy

Use provider tokens only at runtime.

GitHub:

- source token: `HEIMDALL_GITHUB_API_TOKEN`
- validate repo through GitHub API before clone when possible
- clone/fetch over HTTPS with token-backed credentials

GitLab:

- source token: `HEIMDALL_GITLAB_API_TOKEN`
- validate project through GitLab API before clone when possible
- clone/fetch over HTTPS with token-backed credentials

Rules:

- do not store clone URLs containing tokens
- do not write tokenized remotes to `.git/config` if avoidable
- redact any token-like value before writing logs
- if a Git command fails, logs may include command names and exit code, but not credentials

Acceptable implementation options:

1. Use `git -c http.extraHeader=... clone/fetch` so the repository remote stays clean.
2. Use temporary credential environment variables and scrub logs.

Do not use shell interpolation with token values.

## Build Strategy

Only Dockerfile mode is in scope for the first real executor.

Inputs:

- `build_context_path`
- `dockerfile_path`
- `container_port`
- assigned `preview_host`
- assigned `preview_port`
- resolved commit SHA
- project slug

Build command shape:

```text
docker build
  --file {workspace}/repo/{dockerfile_path}
  --tag heimdall/{project_slug}:{short_commit}
  {workspace}/repo/{build_context_path}
```

Rules:

- validate paths before use
- ensure resolved Dockerfile and context stay inside workspace repo
- stream or capture build logs into deployment log
- on build failure, mark deployment `failed`
- do not create a release on build failure

## Container Strategy

Container name:

```text
heimdall-preview-{project_slug}
```

Run command shape:

```text
docker run -d
  --name heimdall-preview-{project_slug}
  --label heimdall.project_id={project_id}
  --label heimdall.release_id={release_id}
  --label heimdall.managed=true
  -p {preview_host}:{preview_port}:{container_port}
  {image_tag}
```

Generated project-volume bind mounts are a separate planned extension. See
[Docker Project Volume Support Implementation Plan](docker-project-volume-support.md).
Current no-volume Dockerfile deploys should not add generated `--mount`
arguments.

Replacement behavior:

1. create and start the new container
2. run health check
3. if healthy, stop/remove old Heimdall-managed container for the project
4. mark new release current

If blue/green replacement is too large for the first slice, a simpler stop-old-then-run-new flow is acceptable, but the document should be updated and the UI should make failed replacement risk clear.

Implementation note: the first real single-server slice uses stop-old-then-run-new for Heimdall-managed containers with the same project label. A failed replacement can leave the preview unavailable until the next successful deploy.

Safety rules:

- only stop/remove containers with Heimdall labels
- never stop arbitrary containers by port alone
- do not run user-provided shell commands
- do not pass raw env values from UI in the first slice

## Health Check Strategy

Health check URL:

```text
http://{preview_host}:{preview_port}{health_check_path}
```

If `health_check_url` is set, use it only if it passed existing validation and does not contain credentials.

Behavior:

- poll until success or timeout
- default timeout can start at 60 seconds
- success means HTTP 2xx or 3xx
- failure marks deployment `failed`
- logs should include attempts and final status code, not response bodies by default

## Deployment And Release State

Real deployment success:

```text
deployment.status = success
deployment.is_dry_run = false
release.status = current
release.is_current = true
release.is_dry_run = false
project.current_release_id = release.id
project.current_commit_sha = resolved_commit_sha
project.status = healthy
```

Previous current release:

```text
release.status = superseded
release.is_current = false
release.last_used_at = now
```

Real deployment failure:

```text
deployment.status = failed
deployment.is_dry_run = false
deployment.status_message = clear failure summary
project.status = failed or previous status, depending on whether old preview still runs
```

Do not mark a release current unless the container started and health check passed.

## Rollback Direction

Rollback should remain disabled for simulated dry-run releases.

Real rollback later means:

```text
select previous non-dry-run release
-> run container from existing image tag
-> health check
-> mark selected release current
-> supersede previous current release
```

Rollback does not need to be implemented in the first real deploy slice.

## Webhook Direction

Webhook registration is separate from real deployment.

Manual deploy should work without a webhook.

Webhook auto deploy should later reuse the same deployment service:

```text
provider push webhook
-> verify provider secret
-> find project by provider and repo URL
-> check tracked branch
-> enqueue or run deployment
```

Current webhook handler creates a queued deployment record. The real executor goal may leave this as-is and focus on manual deploy first.

## UI Requirements

Projects tab:

- selected project detail shows whether the latest preview is dry-run or real
- primary action says `Deploy preview`
- preview URL should be useful only when a real container is running
- dry-run records remain visibly labeled

Deployments tab:

- show real statuses: fetching, building, starting, health_checking, success, failed
- log panel streams or refreshes sectioned logs
- failed deployment should expose the failed phase clearly

Settings tab:

- keep provider readiness and repo validation
- keep `.heimdall/project.yaml` preview repo-safe
- YAML must still exclude preview port, token, webhook secret, deployment state, image tags, logs, releases, and rollback state

## Validation Gates

Required local validation after the next implementation goal:

```bash
cd product/apps/api
venv/bin/python -m pytest
```

```bash
cd product/apps/web
pnpm build
```

Manual validation with a small Dockerfile repo:

```text
1. register repo
2. validate access
3. click Deploy preview
4. deployment reaches success
5. logs show workspace/build/container/health sections
6. preview URL returns HTTP response
7. release is current and non-dry-run
8. second deploy replaces the previous preview without port conflict
```

## Test Coverage Required

Add or update API tests for:

- clone/fetch command construction does not expose token values
- path traversal rejection for Dockerfile/context at executor boundary
- successful real executor flow using mocked Git/Docker/HTTP health operations
- build failure marks deployment failed and creates no current release
- container start failure marks deployment failed
- health check failure marks deployment failed
- second successful deploy supersedes previous current release
- dry-run releases still cannot be rolled back

If Docker commands are wrapped in a local runner abstraction, tests should mock the runner instead of requiring Docker in CI.

## Implementation Order

Maintenance notes for this path:

1. Keep executor mode selection and dry-run tests passing.
2. Keep workspace clone/fetch token-safe.
3. Keep Docker command execution behind the runner abstraction.
4. Keep Dockerfile build and container replace/run behavior covered by tests.
5. Keep health check polling covered by tests.
6. Keep deployment/release/project state transitions covered for real
   success/failure.
7. Keep UI labels clear for dry-run and real preview records.
8. Run validation gates and a manual local Docker smoke test after changes.
