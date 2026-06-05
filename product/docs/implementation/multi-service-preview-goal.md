# Multi-Service Preview Deploy Goal

This document is the implementation brief for extending Heimdall's current
single-service Dockerfile preview deployment into a multi-service Dockerfile
preview deployment.

It is not the design source of truth. Keep the existing source-of-truth and
supporting documents authoritative for architecture, pipeline behavior, and
configuration semantics.

## Source Of Truth

- `product/docs/implementation/multi-service-preview.md`

## Supporting References

- `product/docs/implementation/preview-deployment-pipeline.md`
- `product/docs/architecture/single-server-preview.md`
- `product/docs/config/project-yaml.md`
- `product/apps/api/app/services/deployments.py`
- `product/apps/api/app/services/executor_local_docker.py`
- `product/apps/api/app/db.py`
- `product/apps/api/app/schemas.py`
- `product/apps/web/src/App.jsx`

## Goal

Extend Heimdall's existing single-service Dockerfile preview deploy so that a
project can define and manually deploy multiple Dockerfile-based services.

The existing single-service Dockerfile deploy path must continue to work.

## Scope

- Primary implementation scope is `product/apps/api`.
- Change `product/apps/web` only as needed for multi-service project
  registration, status display, and deployment confirmation.
- Webhook-triggered automatic deployment is out of scope.
- Docker Compose, Kubernetes, remote Docker, Proxmox, Gjallar, VM, and LXC
  deployment are out of scope.
- Secret values must not be stored or exposed in the database, logs, UI, API
  responses, or YAML preview.

## Required Implementation

### Project Services

Allow a project to define multiple services. Each service must support:

- `name`
- `build_context_path`
- `dockerfile_path`
- `container_port`
- `public`
- `health_check_path`
- `startup_order`
- non-secret `build_env`
- non-secret `runtime_env`
- `required_secrets` names only

### Public Service Constraint

For the first implementation slice, require exactly one public service.

- Only the public service is published to the assigned preview host and port.
- Internal services must not receive host ports.

### Deploy Mode

Add `multi_service_dockerfile` as a deploy mode.

- Preserve the existing `dockerfile` single-service deploy mode.
- Preserve the existing dry-run fallback behavior.

### Manual Deploy Preview

Manual deploy preview must perform a multi-service deployment:

- Clone or fetch the repository once.
- Check out the tracked branch.
- Resolve the actual commit SHA.
- Build each service Dockerfile.
- Create a project-specific Docker network.
- Run one container per service.
- Add Heimdall labels to each service container:
  - `heimdall.managed=true`
  - `heimdall.project_id`
  - `heimdall.release_id`
  - `heimdall.service`
- Use the service name as the Docker network alias.
- Replace only existing Heimdall-managed containers for the same project
  services.
- Run health checks per service.
- On full success, mark the deployment successful, the release current, and the
  project healthy.

### Release Manifest

Record releases as a service image set. The manifest should be designed so a
future rollback implementation can use it, even though rollback is out of scope
for this slice.

For each service, record:

- image tag
- image ID
- container name
- public/internal visibility
- preview URL for the public service
- internal URL for internal services

### Service Communication

Service-to-service communication must use Docker network aliases.

- A backend service should be reachable from peer containers through an
  internal URL such as `http://backend:8000`.
- Browser-side frontend code must not use Docker network aliases directly.
- For the first slice, assume the frontend image handles `/api` proxying or uses
  `VITE_API_BASE_URL=/api`.
- Heimdall gateway generation is out of scope.

### Web UI

Keep the Web UI changes minimal:

- Project create/edit can add and edit services.
- Exactly one service can be selected as public.
- Deployment/release status can show service-level image and status details.
- YAML preview shows the `services` structure.
- YAML preview must not include secret values.

## Definition Of Done

- Existing single-service deploy tests still pass.
- A multi-service project can be registered.
- Duplicate service names are rejected.
- Zero or multiple public services are rejected.
- Invalid paths are rejected.
- Invalid environment values are rejected.
- Secret values are rejected anywhere only secret names are allowed.
- Deploy preview builds one Docker image per service.
- A project Docker network is created.
- Internal services are reachable through Docker network aliases.
- Only the public service runs with the assigned preview host port.
- Health checks run per service.
- Deployment logs include entries for:
  - `workspace`
  - `build:<service>`
  - `container:<service>`
  - `health:<service>`
  - `summary`
- A successful non-dry-run deployment creates a current release with a service
  image manifest.
- Token and secret values are not exposed in logs, database responses, UI, or
  YAML preview.
- API tests pass.
- New multi-service executor and API tests are added.
- Web build passes.
- A manual smoke test with a small frontend/backend Dockerfile repository
  passes.

## Validation

Run:

```sh
cd product/apps/api && venv/bin/python -m pytest
cd product/apps/web && pnpm build
```

## Manual Smoke Test

Use a small repository containing frontend and backend Dockerfiles.

1. Register the project.
2. Validate access.
3. Deploy preview.
4. Confirm frontend and backend images were both built.
5. Confirm the backend container is internal only.
6. Confirm the frontend container uses the assigned preview port.
7. Confirm the preview URL returns HTTP 200.
8. Confirm the frontend `/api` route reaches the backend.
9. Confirm the release contains the service image manifest.
