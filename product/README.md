# Heimdall Product

Heimdall is a Git-based preview deployment manager.

GitHub or GitLab projects are registered in Heimdall. When the tracked branch is updated, Heimdall builds and runs the project on the Heimdall server as a Docker-based preview deployment. The web UI tracks current preview status, deployment history, logs, release images, and rollback actions per project.

## Scope

- GitHub and GitLab project registration
- Webhook handling for tracked branch pushes
- Local clone/fetch workspace management
- Docker image build and container execution on the Heimdall server
- Project preview URL management
- Deployment logs and history
- Docker image based rollback
- Web UI control for project status, manual deploy, auto deploy, and rollback
- Managed project PostgreSQL provisioning, deploy-time `DATABASE_URL`
  injection, retry, delete-orphan retention, and explicit purge

## Non-goals

- VM or Proxmox lifecycle management
- Remote staging VM orchestration in the MVP
- Raw secret storage
- Production-grade hosting
- Unrestricted shell execution

## Docs

Start from the docs index:

- [Docs README](docs/README.md)
- [Managed Project PostgreSQL Design](docs/architecture/managed-project-postgresql.md)
- [Self-hosting Storage Architecture](docs/architecture/self-hosting-storage.md)
- [Self-hosting Docker Runbook](docs/operations/self-hosting-docker.md)

## Self-hosting Notes

The API image listens on `8000` and expects persistent runtime storage at
`/var/lib/heimdall`. The Web image serves nginx on `80`, bakes
`VITE_API_BASE_URL` at build time, and does not proxy `/api`.

Mounting `/var/run/docker.sock` into the API container is high trust. It gives
Heimdall effective control of the VM Docker daemon and should only be used for a
trusted self-hosted controller.

## Docker Compose

For single-VM self-hosting with API, Web, Heimdall control Postgres, and the
prepared project Postgres service:

```bash
cd product
sudo install -d -m 0750 /srv/heimdall/runtime
sudo install -d -m 0750 /srv/heimdall/control-postgres
sudo install -d -m 0750 /srv/heimdall/project-postgres
cp .env.compose.example .env
# Edit .env: set URL-safe Postgres passwords and replace 192.0.2.10 with the VM IP.
docker compose --env-file .env -f compose.yaml up -d --build
```

`HEIMDALL_DATABASE_URL` is the Heimdall control database only and points at
`heimdall-postgres` in Compose. `project-postgres` is the target service for
managed project application databases. Heimdall provisions one database and
role per enabled project, stores the generated password only under the ignored
runtime secret store, and injects an assembled `DATABASE_URL` only at deploy
time.

Both Postgres services are internal to Docker networks and are not published on
host port `5432`. The Web image bakes `VITE_API_BASE_URL` at build time, so set
it to the browser-visible API URL and rebuild after changing it. If the API runs
in Docker and cannot health-check browser preview URLs directly, set
`HEIMDALL_PREVIEW_HEALTH_HOST` to the host name reachable from the API container.

See the [Self-hosting Docker Runbook](docs/operations/self-hosting-docker.md)
for settings, health checks, and caveats.

## Run

API uses a local Python virtual environment.

```bash
cd product/apps/api
python3 -m venv venv
venv/bin/pip install -r requirements.txt
venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 18080
```

Web uses pnpm.

```bash
cd product/apps/web
pnpm install
VITE_API_BASE_URL=http://127.0.0.1:18080 pnpm exec vite --host 127.0.0.1 --port 15173
```

## Validate

```bash
cd product/apps/api
venv/bin/python -m pytest
```

```bash
cd product/apps/web
pnpm build
```

## Docker Build

Build the API image:

```bash
docker build -t heimdall-api:local product/apps/api
```

Run the API image with access to the host Docker engine:

```bash
docker run --rm -p 8000:8000 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v "$PWD/product-runtime:/var/lib/heimdall" \
  heimdall-api:local
```

Build the Web image:

```bash
docker build -t heimdall-web:local product/apps/web
```

The Web image bakes in `VITE_API_BASE_URL` at build time. Override it when the
API is not available from the browser at `http://127.0.0.1:8000`.

```bash
docker build \
  --build-arg VITE_API_BASE_URL=http://127.0.0.1:8000 \
  -t heimdall-web:local \
  product/apps/web
```

Run the Web image:

```bash
docker run --rm -p 8080:80 heimdall-web:local
```
