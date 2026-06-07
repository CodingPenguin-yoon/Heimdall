# Self-hosting Docker Runbook

## Scope

This runbook is for operating Heimdall with Docker on a single VM. The outer
Heimdall is started manually by the operator.

The nested child layout uses:

```text
/srv/heimdall
/srv/heimdall/children/{project_id}
```

Manual fallback examples may use a friendly child name such as
`heimdall-main`; that is not the outer-managed child ID model. Current
Heimdall does real Dockerfile preview deploys when `dry_run=false`, but it does
not generate bind mounts for project preview containers yet. Compose mode is
unsupported.

## Host Directory Setup

For current operation, create the outer runtime root on the VM host before
starting Heimdall.

Create the outer instance directories:

```bash
sudo install -d -m 0750 /srv/heimdall/config
sudo install -d -m 0750 /srv/heimdall/runtime/state
sudo install -d -m 0750 /srv/heimdall/runtime/logs/deployments
sudo install -d -m 0750 /srv/heimdall/runtime/workspaces
sudo install -d -m 0750 /srv/heimdall/runtime/secrets
sudo install -d -m 0750 /srv/heimdall/runtime/env
sudo install -d -m 0750 /srv/heimdall/children
```

If running an inner Heimdall manually today, create the manual
`heimdall-main` instance root:

```bash
sudo install -d -m 0750 /srv/heimdall/children/heimdall-main/config
sudo install -d -m 0750 /srv/heimdall/children/heimdall-main/runtime/state
sudo install -d -m 0750 /srv/heimdall/children/heimdall-main/runtime/logs/deployments
sudo install -d -m 0750 /srv/heimdall/children/heimdall-main/runtime/workspaces
sudo install -d -m 0750 /srv/heimdall/children/heimdall-main/runtime/secrets
sudo install -d -m 0750 /srv/heimdall/children/heimdall-main/runtime/env
sudo install -d -m 0750 /srv/heimdall/children/heimdall-main/project-volumes
```

For the outer UI child runner, do not pre-create a named
`heimdall-main` child. The outer API will create or check
`/host/children/{project_id}/runtime` and
`/host/children/{project_id}/project-volumes` when exactly one project service
is marked `run_as_heimdall_child=true`.

The outer API needs this root mapping in place:

```text
VM:
  /srv/heimdall/children

Outer API container:
  /srv/heimdall/children  # host-root validation path
  /host/children
```

The current API image runs with its image default user. If you run the container
as a specific non-root user, change ownership of the mounted runtime directories
to that UID/GID.

## API Env File

Use implemented API settings in production env files today. Child-runner
settings are required only on an outer instance that should deploy a child
Heimdall API. Project-volume roots are optional and required only for API
logical volume validation/use; generated preview bind mounts are still pending.

Example outer API env file at `/srv/heimdall/config/api.env`:

```env
HEIMDALL_RUNTIME_DIR=/var/lib/heimdall
HEIMDALL_DATABASE_URL=sqlite:////var/lib/heimdall/state/heimdall.db
HEIMDALL_PUBLIC_BASE_URL=https://outer-heimdall.example.com
HEIMDALL_PREVIEW_HOST=127.0.0.1
HEIMDALL_PREVIEW_PORT_START=18000
HEIMDALL_PREVIEW_PORT_END=18999
HEIMDALL_GITHUB_API_TOKEN=replace-me
HEIMDALL_GITHUB_WEBHOOK_SECRET=replace-me
HEIMDALL_GITLAB_BASE_URL=https://gitlab.example.com
HEIMDALL_GITLAB_API_TOKEN=replace-me
HEIMDALL_GITLAB_WEBHOOK_SECRET=replace-me
```

Outer child-runner env for the implemented minimum slice:

```env
HEIMDALL_CHILD_RUNNER_ENABLED=true
HEIMDALL_CHILD_ROOT_HOST=/srv/heimdall/children
HEIMDALL_CHILD_ROOT_CONTAINER=/host/children
```

Manual fallback inner API env file at
`/srv/heimdall/children/heimdall-main/config/api.env`:

```env
HEIMDALL_RUNTIME_DIR=/var/lib/heimdall
HEIMDALL_DATABASE_URL=sqlite:////var/lib/heimdall/state/heimdall.db
HEIMDALL_PUBLIC_BASE_URL=https://inner-heimdall.example.com
HEIMDALL_PREVIEW_HOST=127.0.0.1
HEIMDALL_PREVIEW_PORT_START=19000
HEIMDALL_PREVIEW_PORT_END=19999
HEIMDALL_GITHUB_API_TOKEN=replace-me
HEIMDALL_GITHUB_WEBHOOK_SECRET=replace-me
HEIMDALL_GITLAB_BASE_URL=https://gitlab.example.com
HEIMDALL_GITLAB_API_TOKEN=replace-me
HEIMDALL_GITLAB_WEBHOOK_SECRET=replace-me
```

Manual fallback inner project-volume env for API logical volume validation/use;
generated preview bind mounts are still pending:

```env
HEIMDALL_VOLUME_ROOT_HOST=/srv/heimdall/children/heimdall-main/project-volumes
HEIMDALL_VOLUME_ROOT_CONTAINER=/host/project-volumes
```

`HEIMDALL_REPO_ROOT` is set to `/app` by the API Docker image. Do not override
it in normal Docker self-hosting.

Use file permissions appropriate for secrets. The child env file permission
command applies only if using the manual `heimdall-main` fallback:

```bash
sudo chmod 0640 /srv/heimdall/config/api.env
sudo chmod 0640 /srv/heimdall/children/heimdall-main/config/api.env
```

## Build Images

Build the API image:

```bash
docker build -t heimdall-api:local product/apps/api
```

Build the Web image with the API URL that browsers should call:

```bash
docker build \
  --build-arg VITE_API_BASE_URL=https://outer-heimdall.example.com \
  -t heimdall-web:local \
  product/apps/web
```

`VITE_API_BASE_URL` is baked into the Web image at build time. Changing it later
requires rebuilding the Web image. The nginx image serves static files on `80`
and does not proxy `/api`.

## Run Outer Heimdall

Run the outer API container:

```bash
docker run -d \
  --name heimdall-outer-api \
  --env-file /srv/heimdall/config/api.env \
  -p 8000:8000 \
  -v /srv/heimdall/runtime:/var/lib/heimdall \
  -v /srv/heimdall/children:/srv/heimdall/children:ro \
  -v /srv/heimdall/children:/host/children \
  -v /var/run/docker.sock:/var/run/docker.sock \
  heimdall-api:local
```

The `/host/children` mount is optional for ordinary previews, but it is
required for the outer UI child runner.

The outer API uses container paths to create/check child roots:

```text
/host/children/{project_id}/runtime
/host/children/{project_id}/project-volumes
```

Use VM host paths when passing bind mount sources to Docker, because those paths
are resolved by the VM Docker daemon:

```text
-v /srv/heimdall/children/{project_id}/runtime:/var/lib/heimdall
-v /srv/heimdall/children/{project_id}/project-volumes:/host/project-volumes
```

Run the outer Web container:

```bash
docker run -d \
  --name heimdall-outer-web \
  -p 8080:80 \
  heimdall-web:local
```

If Web and API are served under one public hostname, use an external reverse
proxy. The current Web image does not include an `/api` proxy.

## Run Inner Heimdall Manually

This is the manual fallback. It is not the outer UI child-runner flow.

Run the inner API container:

```bash
docker run -d \
  --name heimdall-main-api \
  --env-file /srv/heimdall/children/heimdall-main/config/api.env \
  -p 18080:8000 \
  -v /srv/heimdall/children/heimdall-main/runtime:/var/lib/heimdall \
  -v /var/run/docker.sock:/var/run/docker.sock \
  heimdall-api:local
```

Build a Web image for the inner API URL, then run it:

```bash
docker build \
  --build-arg VITE_API_BASE_URL=https://inner-heimdall.example.com \
  -t heimdall-web-inner:local \
  product/apps/web
```

```bash
docker run -d \
  --name heimdall-main-web \
  -p 18081:80 \
  heimdall-web-inner:local
```

Future
[generated project-volume support](../implementation/docker-project-volume-support.md)
or manual API logical-volume validation/use would add this API mount:

```text
-v /srv/heimdall/children/heimdall-main/project-volumes:/host/project-volumes
```

Do not assume that mount changes current preview behavior. Current preview
containers do not receive generated bind mounts.

## Outer UI Child Runner

The implemented minimum slice is tracked in
[Nested Heimdall Child Deploy Implementation Plan](../implementation/trusted-heimdall-child-mode.md).

The operator still runs the outer Heimdall manually. The implemented flow is:

- register the inner Heimdall API as a Dockerfile project in the outer UI
- mark exactly one service as `Heimdall API child`
- persist service-level `run_as_heimdall_child=true`
- let the outer executor add the fixed child API mounts/env

Outer prerequisites:

```env
HEIMDALL_CHILD_RUNNER_ENABLED=true
HEIMDALL_CHILD_ROOT_HOST=/srv/heimdall/children
HEIMDALL_CHILD_ROOT_CONTAINER=/host/children
```

Outer API mounts:

```text
/var/run/docker.sock:/var/run/docker.sock
/srv/heimdall/children:/host/children
```

For `child_id=project_id`, only the inner Heimdall API container receives:

```text
/var/run/docker.sock:/var/run/docker.sock
/srv/heimdall/children/{project_id}/runtime:/var/lib/heimdall
/srv/heimdall/children/{project_id}/project-volumes:/host/project-volumes
```

The child API env is injected with Docker `--env` args:

```env
HEIMDALL_RUNTIME_DIR=/var/lib/heimdall
HEIMDALL_DATABASE_URL=sqlite:////var/lib/heimdall/state/heimdall.db
HEIMDALL_VOLUME_ROOT_HOST=/srv/heimdall/children/{project_id}/project-volumes
HEIMDALL_VOLUME_ROOT_CONTAINER=/host/project-volumes
```

This minimum slice does not automate inner Web lifecycle, child env files, or
project-volume mounts into user preview containers. Multi-service projects are
allowed only when exactly one service is marked as the child API service.

## Docker Socket Warning

The API container needs Docker access for real local deploys. Mounting
`/var/run/docker.sock` gives the API process effective control of the VM Docker
daemon.

Operator rules:

- Mount the socket only into operator-approved Heimdall API containers.
- Do not mount the socket into Web containers.
- Never mount the socket into normal user project preview containers.
- Do not expose arbitrary host path selection to users or repo YAML.
- Do not let repo YAML request the child runner, child roots, privileged mounts,
  raw Docker options, or Docker socket access.
- Isolate untrusted or multi-tenant workloads on separate infrastructure.

Docker bind mount source paths are resolved by the Docker daemon on the VM host.
For example, `/srv/heimdall/children/{project_id}/runtime` in a `docker run -v`
argument is a VM path, not a path inside the outer or inner Heimdall container.

## Manual Smoke Checklist

API health:

```bash
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:18080/health
```

Web/API connectivity:

- Open the Web URL.
- Confirm browser requests go to the `VITE_API_BASE_URL` that was baked into
  the Web image.
- If the Web and API are behind one public hostname, confirm the external
  reverse proxy handles that routing.

Provider readiness:

- Confirm provider token and webhook secret env vars are configured.
- Confirm `HEIMDALL_PUBLIC_BASE_URL` is the API URL providers can call for
  webhook registration.

Deployment:

- Register a small Dockerfile project.
- Run an explicit dry-run deploy and confirm it is marked simulated.
- Run a real deploy with `dry_run=false`.
- Confirm logs include workspace, build, container, health, and summary
  sections.
- Confirm preview containers have Heimdall labels.
- Confirm no generated `--mount`, `-v`, or `--volume` is expected for project
  preview containers today.

Persistence:

- Restart the API container.
- Confirm the SQLite database and deployment logs remain under the mounted
  runtime directory.
- Confirm workspaces can be deleted and recreated without deleting the database
  or logs.

## Backup Checklist

Back up:

- `/srv/heimdall/config`
- `/srv/heimdall/runtime/state`
- `/srv/heimdall/runtime/logs` when logs are part of audit history
- `/srv/heimdall/runtime/secrets` and `/srv/heimdall/runtime/env` if used
- manual fallback `/srv/heimdall/children/heimdall-main/config` if used
- manual fallback `/srv/heimdall/children/heimdall-main/runtime/state` if used
- manual fallback `/srv/heimdall/children/heimdall-main/runtime/logs` if needed
- child `/srv/heimdall/children/{project_id}/runtime/state`
- child `/srv/heimdall/children/{project_id}/runtime/logs` when needed
- child `/srv/heimdall/children/{project_id}/project-volumes`

Usually do not back up:

- runtime workspaces
- stopped preview containers
- images that can be rebuilt from source, unless rollback policy requires them
