# Backend

The backend is a FastAPI control plane for Heimdall staging operations.

## Main domains

- `app/domains/deploy`
  - legacy compatibility boundary only
  - public `/api/deploy` must fail closed with HTTP 410 Gone
  - historical Terraform/post-clone/Ansible code remains for later archival, but Heimdall no longer owns VM provisioning
- `app/domains/staging`
  - staging host registry list and register APIs
  - pool grouping and live port preview
- `app/domains/gitlab`
  - inventory sync
  - project creation
  - environment-contract settings
  - `.heimdall/project.yaml` validation
  - manual `Deploy Staging` wrapper
- `app/domains/proxmox`
  - Proxmox inventory and lifecycle operations
- `app/domains/task`
  - task persistence, logs, SSE
- `app/domains/webhooks`
  - GitLab system hook ingress

## Current backend behavior

### Create Instance boundary

`POST /api/deploy` is a deprecated compatibility route. It no longer provisions VMs from Heimdall and must return HTTP 410 Gone with Gjallar ownership guidance. VM/Create Instance provisioning now belongs to Gjallar.

Historical note: `create_as_staging_host=true` belonged to the old Heimdall Create Instance flow. That flow is no longer active; worker/host capacity should be provisioned by Gjallar and then registered/observed by Heimdall.

Main files:

- `app/domains/deploy/router.py`
- `app/domains/deploy/service.py`
- `app/domains/staging/router.py`
- `app/domains/staging/service.py`

### GitLab deploy path

`POST /api/gitlab/projects/{project_id}/deploy/staging` now resolves a staging target from the saved environment contract.

Current contract fields:

- `deployment_environment`
- `deployment_pool_key`
- `requested_app_port`
- `database_required`

Current execution behavior:

- staging deploy rebuilds a live pool preview
- it selects a ready host from the chosen pool
- it skips Terraform for the app deploy path
- it deploys with the GitLab source archive + remote Docker Compose

Current limitation:

- production contracts can be stored, but production execution does not exist yet

## State and migration

- platform DB: `data/platform_state.db`
- task history import source: `data/task_history.json`
- migrations:

```bash
cd backend
. venv/bin/activate
alembic upgrade head
```

Current migration head:

- `20260426_0010`

## Run

From repo root:

```bash
pnpm backend
```

Directly:

```bash
cd backend
. venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The app loads the repo root `.env`.
