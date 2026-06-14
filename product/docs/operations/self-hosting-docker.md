# Self-hosting Docker Runbook

## Scope

This runbook covers the supported self-hosting path: one operator-managed
Heimdall API/Web instance on a single VM. Nested/child Heimdall is a deprecated
legacy path and is not configured through the normal product UI/API.

Existing child runtime roots, if any, are operator-owned data. Heimdall does not
delete `/srv/heimdall/children` or any child runtime/project-volume root
automatically.

## Docker Compose Quickstart

Use the product-level Compose file when you want Heimdall API, Web, the
Heimdall control database, and the prepared project database service on one VM.

From the repository root:

```bash
cd product
sudo install -d -m 0750 /srv/heimdall/runtime
sudo install -d -m 0750 /srv/heimdall/control-postgres
sudo install -d -m 0750 /srv/heimdall/project-postgres
cp .env.compose.example .env
```

Edit `product/.env` before starting:

- Replace `HEIMDALL_CONTROL_POSTGRES_PASSWORD` with a long random URL-safe
  password.
- Put the same control password in `HEIMDALL_DATABASE_URL`.
- Replace `HEIMDALL_PROJECT_POSTGRES_PASSWORD` with a different long random
  URL-safe password.
- Put the same project password in `HEIMDALL_PROJECT_DATABASE_ADMIN_URL`.
- Replace every `192.0.2.10` placeholder with the VM IP address reachable from
  browsers and from containers on the VM.
- Leave provider tokens blank until GitHub or GitLab integration is needed.

Start Heimdall:

```bash
docker compose --env-file .env -f compose.yaml up -d --build
```

Check service status:

```bash
docker compose --env-file .env -f compose.yaml ps
curl -fsS http://127.0.0.1:8000/health
```

Open the Web UI at `http://<vm-ip>:8080`. If you changed
`HEIMDALL_WEB_PORT`, use that port instead.

Important Compose settings:

- `HEIMDALL_DATABASE_URL` is the Heimdall control database URL only. In Compose
  it should use the service name `heimdall-postgres`, as in
  `postgresql://heimdall:<password>@heimdall-postgres:5432/heimdall`.
- `project-postgres` is the service for managed project application databases.
  Heimdall can create per-project databases and roles, inject generated
  `DATABASE_URL` values at deploy time, and purge resources after exact typed
  confirmation.
- `HEIMDALL_PROJECT_DATABASE_ADMIN_URL` is API-only provisioner config.
  It must never be injected into preview containers.
- Neither Postgres service is published on host port `5432`; only containers on
  the relevant Docker networks can reach them by default.
- `HEIMDALL_CONTROL_POSTGRES_*` and `HEIMDALL_PROJECT_POSTGRES_*` values are
  passed to the official Postgres image only when the corresponding data
  directory is initialized for the first time. Changing them later does not
  rewrite an existing database.
- `VITE_API_BASE_URL` is baked into the Web image during build and must be a
  browser-visible API URL. Do not set it to `http://api:8000`; browsers cannot
  resolve Compose service names. Rebuild Web after changing it.
- `HEIMDALL_PREVIEW_HOST` is used for Docker port publishing and browser preview
  URLs. When the API runs in Docker and cannot health-check that same host, set
  `HEIMDALL_PREVIEW_HEALTH_HOST` to the host name the API container can reach.
  On Docker Desktop, `HEIMDALL_PREVIEW_HOST=127.0.0.1` with
  `HEIMDALL_PREVIEW_HEALTH_HOST=host.docker.internal` keeps browser URLs local
  while allowing API-side health checks to reach published preview ports.
- Passwords embedded in database URLs must be URL-safe or URL-encoded. A simple
  alphanumeric password with `-`, `_`, `.`, or `~` avoids URL escaping mistakes.
- Heimdall creates its schema on API startup. It does not include automatic
  SQLite-to-PostgreSQL migration; migrate or re-create existing state manually
  before switching an existing instance.
- The Compose file mounts `/var/run/docker.sock` only into the API service. Do
  not add that mount to Web, Postgres, or project preview containers.

## Host Directory Setup

Create the outer instance directories before starting Heimdall:

```bash
sudo install -d -m 0750 /srv/heimdall/config
sudo install -d -m 0750 /srv/heimdall/runtime/state
sudo install -d -m 0750 /srv/heimdall/runtime/logs/deployments
sudo install -d -m 0750 /srv/heimdall/runtime/workspaces
sudo install -d -m 0750 /srv/heimdall/runtime/secrets
sudo install -d -m 0750 /srv/heimdall/runtime/env
sudo install -d -m 0750 /srv/heimdall/control-postgres
sudo install -d -m 0750 /srv/heimdall/project-postgres
```

## API Env File

Example `/srv/heimdall/config/api.env`:

```env
HEIMDALL_RUNTIME_DIR=/var/lib/heimdall
HEIMDALL_DATABASE_URL=sqlite:////var/lib/heimdall/state/heimdall.db
HEIMDALL_PUBLIC_BASE_URL=https://heimdall.example.com
HEIMDALL_PREVIEW_HOST=127.0.0.1
HEIMDALL_PREVIEW_PORT_START=18000
HEIMDALL_PREVIEW_PORT_END=18999
HEIMDALL_GITHUB_API_TOKEN=replace-me
HEIMDALL_GITHUB_WEBHOOK_SECRET=replace-me
HEIMDALL_GITLAB_BASE_URL=https://gitlab.example.com
HEIMDALL_GITLAB_API_TOKEN=replace-me
HEIMDALL_GITLAB_WEBHOOK_SECRET=replace-me
HEIMDALL_PROJECT_DATABASE_ADMIN_URL=postgresql://project_admin:replace-with-a-strong-password@project-postgres:5432/postgres
HEIMDALL_PROJECT_DATABASE_APP_HOST=project-postgres
HEIMDALL_PROJECT_DATABASE_APP_PORT=5432
HEIMDALL_PROJECT_DATABASE_NETWORK=heimdall-project-db
```

`HEIMDALL_DATABASE_URL` is only the Heimdall control database. Local/dev
instances can use SQLite. Self-hosted Compose uses `heimdall-postgres` for the
control database. Project application databases must use a separate project DB
service or external database; do not reuse `HEIMDALL_DATABASE_URL` as a project
`DATABASE_URL`.

Managed project PostgreSQL uses `HEIMDALL_PROJECT_DATABASE_ADMIN_URL` only in
the trusted API. The generated app password is stored under the ignored runtime
secret directory, and the app `DATABASE_URL` is assembled only during deploy.

`HEIMDALL_VOLUME_ROOT_HOST` and `HEIMDALL_VOLUME_ROOT_CONTAINER` are optional
and are required only when API logical project volumes are configured. Current
preview containers do not receive generated project bind mounts yet.

Use file permissions appropriate for secrets:

```bash
sudo chmod 0640 /srv/heimdall/config/api.env
```

## Control PostgreSQL Database For Plain Docker Run

Heimdall can use an operator-managed PostgreSQL database for its own control
state when not using the product Compose file. Example container:

```bash
docker run -d \
  --name heimdall-postgres \
  -e POSTGRES_DB=heimdall \
  -e POSTGRES_USER=heimdall \
  -e POSTGRES_PASSWORD=replace-with-a-strong-password \
  -v /srv/heimdall/control-postgres:/var/lib/postgresql/data \
  postgres:16
```

Set the API database URL to point at that container, for example:

```env
HEIMDALL_DATABASE_URL=postgresql://heimdall:replace-with-a-strong-password@heimdall-postgres:5432/heimdall
```

If the API container is started with plain `docker run`, put the API and
Postgres containers on the same Docker network or use a reachable host name.
Heimdall creates its schema at API startup. It does not include automatic
SQLite-to-PostgreSQL data migration; migrate or re-create existing state
manually before switching an existing instance.

## Project PostgreSQL Service

The managed project PostgreSQL design uses a separate project application DB
service or cluster. In the product Compose path this service is
`project-postgres`, with data under `/srv/heimdall/project-postgres` and a
shared Docker network named `heimdall-project-db`.

Current status:

- Compose starts the service and network.
- Heimdall provisions one database and one app role per enabled project.
- Heimdall injects generated project `DATABASE_URL` values only into bound
  preview containers at deploy time.
- DB-backed single-service previews join `heimdall-project-db`; DB-backed
  multi-service containers keep their project-private network and also join
  `heimdall-project-db`.
- Preview containers must not join `heimdall-control`.
- Purge terminates sessions and drops the managed database and role. Back up
  `project-postgres` before testing purge outside disposable data.

The implementation source of truth is
[Managed Project PostgreSQL](../architecture/managed-project-postgresql.md).

## Build Images

Build the API image:

```bash
docker build -t heimdall-api:local product/apps/api
```

Build the Web image with the browser-visible API URL:

```bash
docker build \
  --build-arg VITE_API_BASE_URL=https://heimdall.example.com \
  -t heimdall-web:local \
  product/apps/web
```

`VITE_API_BASE_URL` is baked into the Web image at build time. Rebuild the Web
image when it changes.

## Run Heimdall

Run the API container:

```bash
docker run -d \
  --name heimdall-api \
  --env-file /srv/heimdall/config/api.env \
  -p 8000:8000 \
  -v /srv/heimdall/runtime:/var/lib/heimdall \
  -v /var/run/docker.sock:/var/run/docker.sock \
  heimdall-api:local
```

Run the Web container:

```bash
docker run -d \
  --name heimdall-web \
  -p 8080:80 \
  heimdall-web:local
```

If Web and API are served under one public hostname, use an external reverse
proxy. The current Web image does not include an `/api` proxy.

## Docker Socket Warning

The API container needs Docker access for real local deploys. Mounting
`/var/run/docker.sock` gives the API process effective control of the VM Docker
daemon.

Operator rules:

- Mount the socket only into the trusted Heimdall API container.
- Do not mount the socket into Web containers.
- Never mount the socket into normal user project preview containers.
- Do not expose arbitrary host path selection to users or repo YAML.
- Isolate untrusted or multi-tenant workloads on separate infrastructure.

## Manual Smoke Checklist

API health:

```bash
curl -fsS http://127.0.0.1:8000/health
```

Web/API connectivity:

- Open the Web URL.
- Confirm browser requests go to the `VITE_API_BASE_URL` baked into the Web
  image.
- If Web and API are behind one public hostname, confirm the external reverse
  proxy handles that routing.

Deployment:

- Register a small Dockerfile project.
- Run an explicit dry-run deploy and confirm it is marked simulated.
- Run a real deploy with `dry_run=false`.
- Confirm logs include workspace, build, container, health, and summary
  sections.
- Confirm preview containers have Heimdall labels.
- For a disposable managed PostgreSQL project, enable the database in UI,
  deploy, confirm only the intended services receive DB injection, and test
  purge only after a project Postgres backup or with disposable data.

## Backup Checklist

Back up:

- `/srv/heimdall/config`
- `/srv/heimdall/runtime/state` for SQLite-backed instances, or the PostgreSQL
  data volume/backups for control PostgreSQL-backed instances
- `/srv/heimdall/runtime/logs` when logs are part of audit history
- `/srv/heimdall/runtime/secrets` and `/srv/heimdall/runtime/env` if used
- `/srv/heimdall/control-postgres` through Postgres-native backups or a
  coordinated stopped-volume backup when using product Compose
- `/srv/heimdall/project-postgres` through Postgres-native backups or a
  coordinated stopped-volume backup before upgrades, restore work, or purge
  tests
- existing `/srv/heimdall/children` data only when retaining legacy child
  instances

Usually do not back up:

- runtime workspaces
- stopped preview containers
- images that can be rebuilt from source, unless rollback policy requires them
