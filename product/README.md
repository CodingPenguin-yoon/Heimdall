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
