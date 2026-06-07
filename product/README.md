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

## Non-goals

- VM or Proxmox lifecycle management
- Remote staging VM orchestration in the MVP
- Raw secret storage
- Production-grade hosting
- Unrestricted shell execution

## Docs

Start from the docs index:

- [Docs README](docs/README.md)
- [Self-hosting Storage Architecture](docs/architecture/self-hosting-storage.md)
- [Self-hosting Docker Runbook](docs/operations/self-hosting-docker.md)

## Self-hosting Notes

The API image listens on `8000` and expects persistent runtime storage at
`/var/lib/heimdall`. The Web image serves nginx on `80`, bakes
`VITE_API_BASE_URL` at build time, and does not proxy `/api`.

Mounting `/var/run/docker.sock` into the API container is high trust. It gives
Heimdall effective control of the VM Docker daemon and should only be used for a
trusted self-hosted controller.

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
