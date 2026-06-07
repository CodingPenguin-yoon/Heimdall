# Nested Heimdall Operations

## Purpose

This runbook describes how to operate one Heimdall instance that deploys another
Heimdall instance.

The supported model is:

```text
VM Docker daemon
  Outer Heimdall API/Web
    Inner Heimdall project
      api service  -> marked as Heimdall API child
        deploys inner-managed preview containers
      web service  -> normal service, no Docker socket
```

The outer API remains operator-managed. Heimdall does not yet manage the full
outer lifecycle, child upgrades, child deletion, child env files, or automatic
webhook deployment workers.

## Operating Model

Use these trust boundaries:

- The outer API is trusted and receives `/var/run/docker.sock`.
- Exactly one service in the inner Heimdall project is marked
  `Heimdall API child`.
- Only that marked API service receives Docker socket access, child runtime
  storage, and child project-volume storage.
- The inner Web service is an ordinary service and must not receive the Docker
  socket or child root mounts.
- Normal user preview containers must not receive the Docker socket.

The child ID is always the outer project ID, not a user-provided name.

```text
/srv/heimdall/children/{outer_project_id}/runtime
/srv/heimdall/children/{outer_project_id}/project-volumes
```

## Current Limits

The current implementation is enough to run the nested API service safely, but
these items remain operator work:

- Inner Web/API routing is not automatic.
- The stock Web image does not proxy `/api`.
- `VITE_API_BASE_URL` is baked into the Web image at build time.
- The outer child runner does not generate a child `.env` file.
- Secret values such as provider API tokens cannot be entered through service
  `runtime_env`.
- Automatic deploy from webhooks still queues a deployment record only; it does
  not execute the deployment worker.
- Generated project-volume bind mounts into user preview containers are still
  pending.

## VM Directory Layout

Create the outer root and child root on the VM:

```bash
sudo install -d -m 0750 /srv/heimdall/config
sudo install -d -m 0750 /srv/heimdall/runtime/state
sudo install -d -m 0750 /srv/heimdall/runtime/logs/deployments
sudo install -d -m 0750 /srv/heimdall/runtime/workspaces
sudo install -d -m 0750 /srv/heimdall/runtime/secrets
sudo install -d -m 0750 /srv/heimdall/runtime/env
sudo install -d -m 0750 /srv/heimdall/children
```

Do not pre-create a friendly child name for outer-managed child projects. The
outer API creates or checks `{project_id}/runtime` and
`{project_id}/project-volumes`.

## Outer API Environment

Use an env file such as `/srv/heimdall/config/api.env` for the outer API.

Required baseline:

```env
HEIMDALL_RUNTIME_DIR=/var/lib/heimdall
HEIMDALL_DATABASE_URL=sqlite:////var/lib/heimdall/state/heimdall.db
HEIMDALL_PUBLIC_BASE_URL=https://outer-heimdall.example.com
HEIMDALL_PREVIEW_HOST=127.0.0.1
HEIMDALL_PREVIEW_PORT_START=18000
HEIMDALL_PREVIEW_PORT_END=18999
```

Child runner gate for the outer API:

```env
HEIMDALL_CHILD_RUNNER_ENABLED=true
HEIMDALL_CHILD_ROOT_HOST=/srv/heimdall/children
HEIMDALL_CHILD_ROOT_CONTAINER=/host/children
```

Provider integration, optional but needed for repository validation and webhook
registration:

```env
HEIMDALL_GITHUB_API_TOKEN=replace-me
HEIMDALL_GITHUB_WEBHOOK_SECRET=replace-me

HEIMDALL_GITLAB_BASE_URL=https://gitlab.example.com
HEIMDALL_GITLAB_API_TOKEN=replace-me
HEIMDALL_GITLAB_WEBHOOK_SECRET=replace-me
```

Use `HEIMDALL_PREVIEW_HOST=127.0.0.1` when an external reverse proxy on the same
VM forwards preview ports. If previews must bind directly to all interfaces,
use the host address intentionally and make sure firewall rules match that
choice.

## Outer Docker Run

The outer API must have Docker socket access and both child root views:

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

The read-only `/srv/heimdall/children:/srv/heimdall/children:ro` mount lets the
outer API validate host paths. The writable `/host/children` mount is where it
creates child runtime directories.

Build the outer Web with a browser-reachable outer API URL:

```bash
docker build \
  --build-arg VITE_API_BASE_URL=https://outer-heimdall.example.com \
  -t heimdall-web:local \
  product/apps/web
```

Then run it:

```bash
docker run -d \
  --name heimdall-outer-web \
  -p 8080:80 \
  heimdall-web:local
```

## Inner Project In The Outer UI

Create one multi-service project for the inner Heimdall stack.

Recommended service shape:

```text
Service api
  Dockerfile: product/apps/api/Dockerfile or repo-specific path
  Container port: 8000
  Heimdall API child: checked
  Public: depends on routing plan

Service web
  Dockerfile: product/apps/web/Dockerfile or repo-specific path
  Container port: 80
  Heimdall API child: unchecked
  Public: depends on routing plan
```

Exactly one service may be marked `Heimdall API child`. Saving with zero marked
services while project-level child mode is requested, or with more than one
marked service, is rejected.

The outer executor injects these values into the child API service only:

```env
HEIMDALL_RUNTIME_DIR=/var/lib/heimdall
HEIMDALL_DATABASE_URL=sqlite:////var/lib/heimdall/state/heimdall.db
HEIMDALL_VOLUME_ROOT_HOST=/srv/heimdall/children/{project_id}/project-volumes
HEIMDALL_VOLUME_ROOT_CONTAINER=/host/project-volumes
```

When configured on the outer API, provider settings are also injected into the
child API service only. Unset values are omitted:

```env
HEIMDALL_GITHUB_API_TOKEN
HEIMDALL_GITHUB_WEBHOOK_SECRET
HEIMDALL_GITLAB_BASE_URL
HEIMDALL_GITLAB_API_TOKEN
HEIMDALL_GITLAB_WEBHOOK_SECRET
```

The outer executor also mounts these into the child API service only:

```text
/var/run/docker.sock:/var/run/docker.sock
/srv/heimdall/children/{project_id}/runtime:/var/lib/heimdall
/srv/heimdall/children/{project_id}/project-volumes:/host/project-volumes
```

## Inner API Runtime Values

The child runner injects storage, volume, and configured provider settings.
Other non-secret inner API operation values may be supplied through the API
service `runtime_env`:

```env
HEIMDALL_PUBLIC_BASE_URL=https://inner-api.example.com
HEIMDALL_PREVIEW_HOST=127.0.0.1
HEIMDALL_PREVIEW_PORT_START=19000
HEIMDALL_PREVIEW_PORT_END=19999
```

Do not try to provide these in service `runtime_env`; they are reserved and are
injected by the child runner:

```env
HEIMDALL_RUNTIME_DIR
HEIMDALL_DATABASE_URL
HEIMDALL_CHILD_RUNNER_ENABLED
HEIMDALL_CHILD_ROOT_HOST
HEIMDALL_CHILD_ROOT_CONTAINER
HEIMDALL_VOLUME_ROOT_HOST
HEIMDALL_VOLUME_ROOT_CONTAINER
```

Provider token and webhook secret values are not supported through service
`runtime_env`, because the project service model stores non-secret env values
only. Configure provider values on the outer API settings; the child runner
passes them to the inner API container through Docker `--env` args.

## Inner Web Routing

The stock Web image is static nginx:

- It does not proxy `/api`.
- `VITE_API_BASE_URL` is baked at image build time.
- The browser must be able to reach whatever URL is baked into
  `VITE_API_BASE_URL`.

Do not set `VITE_API_BASE_URL=http://api:8000` for the stock Web image unless
the browser can resolve that name. `api` is only a Docker network alias.

Workable routing options:

1. Make the inner API browser-reachable and run the Web separately with
   `VITE_API_BASE_URL` pointing to that public API URL.
2. Use a custom Web/nginx image that proxies `/api` to `http://api:8000`, make
   the Web service public, and build the Web with `VITE_API_BASE_URL=/api`.
3. Use an external reverse proxy that can reach both services and exposes a
   browser-reachable API URL.

The current multi-service preview model publishes exactly one public service.
If you need both the stock Web and API publicly reachable from the same inner
project, add a proxy service or external routing. Do not give the Web service
Docker socket access to solve routing.

## Smoke Checks

Outer health:

```bash
curl -fsS http://127.0.0.1:8000/health
```

After deploying the inner project, check child directories on the VM:

```bash
sudo find /srv/heimdall/children -maxdepth 3 -type d | sort
```

Check that only the child API service received privileged mounts:

```bash
docker inspect heimdall-preview-{slug}-api \
  --format '{{json .Mounts}}'
```

Expected API mounts include:

```text
/var/run/docker.sock
/var/lib/heimdall
/host/project-volumes
```

Check the Web service does not have Docker socket access:

```bash
docker inspect heimdall-preview-{slug}-web \
  --format '{{json .Mounts}}' | grep -q docker.sock && echo "bad"
```

Inner API health depends on how it is exposed. If it is published or proxied:

```bash
curl -fsS https://inner-api.example.com/health
```

## Backup And Restore

Back up these paths before upgrades:

```text
/srv/heimdall/runtime/state
/srv/heimdall/runtime/logs
/srv/heimdall/children/{project_id}/runtime/state
/srv/heimdall/children/{project_id}/runtime/logs
/srv/heimdall/children/{project_id}/project-volumes
```

Workspaces are disposable and can be refetched from Git.

## Failure Handling

If a child deploy fails partway through, inspect and remove only
Heimdall-managed containers for that project:

```bash
docker ps -a \
  --filter label=heimdall.managed=true \
  --filter label=heimdall.project_id={project_id}
```

Do not remove `/srv/heimdall/children/{project_id}` unless you intend to delete
the inner Heimdall state.

## Security Rules

- Treat `/var/run/docker.sock` as VM-level admin access.
- Mount Docker socket only into Heimdall API containers that are operator
  approved.
- Never mount Docker socket into Web or normal preview containers.
- Do not allow repo YAML to set child roots, Docker socket, host paths,
  privileged flags, or raw Docker arguments.
- Keep provider tokens and webhook secrets in outer operator-owned settings;
  do not put them in project service `runtime_env`.
- Use separate infrastructure for untrusted multi-tenant workloads.
