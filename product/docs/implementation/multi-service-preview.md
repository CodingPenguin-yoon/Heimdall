# Multi-service Preview Deployment Plan

## Purpose

This document is the next implementation reference after the first real single-server Dockerfile preview deploy.

The current executor can deploy one Dockerfile as one image and one preview container. That is not enough for repositories that contain separate frontend and backend services and need independent image builds, container replacement, and rollback.

The target direction is:

```text
Project
-> multiple services
-> one repository checkout
-> one Docker network per project
-> one Docker image per service
-> one container per service
-> one release manifest containing all service images
-> project-level deploy and rollback
```

## Problem Statement

Many preview apps are not a single process.

Common repository layout:

```text
repo/
  frontend/
    Dockerfile
  backend/
    Dockerfile
```

The current single-service preview mode can only express:

```text
build_context_path
dockerfile_path
container_port
health_check_path
```

That forces teams to create one combined preview Dockerfile. It works, but it has real drawbacks:

- frontend and backend images cannot be built independently
- release records only have one image tag
- rollback cannot restore a frontend/backend image set
- service health cannot be tracked separately
- service dependency and internal networking are implicit

The next design should model services directly.

## Product Decision

Use a multi-service project model, not a raw container count model.

Do not ask the user only for:

```text
container_count = 2
```

Instead ask for named services:

```yaml
services:
  frontend:
    build_context_path: frontend
    dockerfile_path: frontend/Dockerfile
    container_port: 3000
    public: true
    health_check_path: /

  backend:
    build_context_path: backend
    dockerfile_path: backend/Dockerfile
    container_port: 8000
    public: false
    health_check_path: /health
```

A service is the unit of build/run/health. A release is the project-level set of service images built from the same commit.

Persistent per-service project volumes are separate planned work. See
[Docker Project Volume Support Implementation Plan](docker-project-volume-support.md).

## Initial Scope

Implement the next slice as local Dockerfile multi-service preview.

In scope:

- one repository per project
- multiple named services per project
- one Dockerfile build per service
- one container per service
- one project Docker network
- Docker network aliases based on service names
- one project release manifest containing service images
- project-level all-or-nothing deploy
- project-level all-or-nothing rollback direction
- exactly one public service in the first slice
- internal services reachable by Docker DNS name
- sectioned logs grouped by service

Out of scope for the first multi-service slice:

- docker-compose mode
- Kubernetes
- remote Docker hosts
- multiple public host ports per project
- production traffic routing
- service-by-service independent rollback
- database provisioning
- generated config commits back to the repository
- storing raw secret values in DB, logs, UI, or YAML

## Service Model

Each service should have:

```text
name
build_context_path
dockerfile_path
container_port
public
health_check_path
startup_order
build_env
runtime_env
required_secrets
```

Rules:

- `name` must be DNS-label safe: lowercase letters, digits, and hyphens.
- `build_context_path` and `dockerfile_path` must stay inside the repo workspace.
- `container_port` is the port the service listens on inside its own container.
- `public=true` means Heimdall publishes the service on the assigned preview host port.
- `public=false` means the service is internal to the project Docker network.
- First slice should require exactly one public service.
- `startup_order` can be an integer for the first slice; dependency graph support can come later.
- `build_env` and `runtime_env` can store non-secret values only.
- `required_secrets` stores secret names only, never values.

Example:

```yaml
version: 1

project:
  name: portfolio
  type: web

source:
  tracked_branch: main

deploy:
  mode: multi_service_dockerfile

services:
  frontend:
    build_context_path: frontend
    dockerfile_path: frontend/Dockerfile
    container_port: 80
    public: true
    health_check_path: /
    startup_order: 20
    build_env:
      VITE_API_BASE_URL: /api
    runtime_env: {}
    required_secrets: []

  backend:
    build_context_path: backend
    dockerfile_path: backend/Dockerfile
    container_port: 8000
    public: false
    health_check_path: /health
    startup_order: 10
    runtime_env:
      PORT: "8000"
    required_secrets:
      - DATABASE_URL
      - JWT_SECRET
```

## Networking

Heimdall should create one Docker network per project:

```text
heimdall-preview-{project_slug}
```

Each service container joins that network with a stable alias:

```text
frontend -> http://frontend:{frontend_container_port}
backend  -> http://backend:{backend_container_port}
```

Example Docker run shape:

```text
docker network create heimdall-preview-portfolio

docker run -d
  --name heimdall-preview-portfolio-backend
  --network heimdall-preview-portfolio
  --network-alias backend
  --label heimdall.managed=true
  --label heimdall.project_id={project_id}
  --label heimdall.release_id={release_id}
  --label heimdall.service=backend
  heimdall/portfolio-backend:{short_commit}

docker run -d
  --name heimdall-preview-portfolio-frontend
  --network heimdall-preview-portfolio
  --network-alias frontend
  --label heimdall.managed=true
  --label heimdall.project_id={project_id}
  --label heimdall.release_id={release_id}
  --label heimdall.service=frontend
  -p {preview_host}:{preview_port}:80
  heimdall/portfolio-frontend:{short_commit}
```

Only the public service receives a host port in the first slice.

Internal services do not get host ports:

```text
browser cannot call http://backend:8000
frontend container can call http://backend:8000
```

## Frontend To Backend Routing

Browser-side JavaScript cannot use Docker network aliases.

This does not work in the browser:

```js
fetch("http://backend:8000/api")
```

The browser is outside the Docker network. It should call the public preview URL:

```js
fetch("/api")
```

Then the public service or gateway should proxy `/api` to the internal backend:

```text
browser
-> http://127.0.0.1:{preview_port}/api
-> public frontend container or gateway
-> http://backend:8000
```

Recommended first slice:

- Heimdall provides network aliases and non-secret env values.
- The frontend service image owns its nginx/proxy config.
- Frontend code uses a relative API base URL such as `/api`.
- Heimdall does not rewrite application source code.

Example frontend build env:

```yaml
services:
  frontend:
    build_env:
      VITE_API_BASE_URL: /api
```

Example internal backend discovery:

```yaml
services:
  frontend:
    runtime_env:
      BACKEND_INTERNAL_URL: http://backend:8000
```

If the app needs Heimdall to generate the proxy later, add a gateway mode:

```yaml
gateway:
  public: true
  routes:
    - path_prefix: /
      target_service: frontend
      target_port: 80
    - path_prefix: /api
      target_service: backend
      target_port: 8000
```

Gateway mode is a later enhancement. It should not block the first multi-service executor.

## Env And Secrets

Separate non-secret config from secret values.

Allowed in DB/YAML/UI:

```text
PORT=8000
NODE_ENV=production
VITE_API_BASE_URL=/api
BACKEND_INTERNAL_URL=http://backend:8000
required secret names
```

Forbidden in DB/YAML/UI/logs:

```text
DATABASE_URL value
JWT_SECRET value
provider token value
SSH key
raw .env value
```

The first secret implementation can use runtime environment naming conventions:

```text
HEIMDALL_SECRET_{PROJECT_SLUG}_{SERVICE_NAME}_{SECRET_NAME}
```

Example:

```text
HEIMDALL_SECRET_PORTFOLIO_BACKEND_DATABASE_URL
HEIMDALL_SECRET_PORTFOLIO_BACKEND_JWT_SECRET
```

The project config stores only:

```yaml
required_secrets:
  - DATABASE_URL
  - JWT_SECRET
```

Logs may show that a secret was provided by name, but never the value.

## Build Strategy

Fetch the repository once per deployment.

Build one image per service:

```text
docker build
  --file {repo}/{service.dockerfile_path}
  --tag heimdall/{project_slug}-{service_name}:{short_commit}
  {repo}/{service.build_context_path}
```

Rules:

- validate every service path at executor boundary
- reject path traversal and symlink escapes
- build services in a stable order
- record build output under service-specific log sections
- on any build failure, deployment fails and no release is marked current

Log shape:

```text
[workspace]
...

[build:backend]
...

[build:frontend]
...

[container:backend]
...

[container:frontend]
...

[health:backend]
...

[health:frontend]
...

[summary]
...
```

## Container Replacement Strategy

Use Heimdall labels for all service containers:

```text
heimdall.managed=true
heimdall.project_id={project_id}
heimdall.release_id={release_id}
heimdall.service={service_name}
```

Container names:

```text
heimdall-preview-{project_slug}-{service_name}
```

First slice replacement behavior can be stop-old-then-run-new:

```text
find old containers by project/service labels
stop/remove old Heimdall-managed containers
run new containers on the project network
health check all services
mark release current only after all health checks pass
```

Safety rules:

- never stop containers by port alone
- never stop containers by name alone
- only stop/remove containers with Heimdall labels
- failed replacement can temporarily leave the preview unavailable

Blue/green replacement can be added later with temporary service names and a gateway switch, but it is not required for the first multi-service slice.

## Health Checks

Public service health:

```text
http://{preview_host}:{preview_port}{health_check_path}
```

Internal service health should be checked from inside the project Docker network.

Recommended approach:

```text
docker run --rm
  --network heimdall-preview-{project_slug}
  heimdall-healthcheck
  http://{service_name}:{container_port}{health_check_path}
```

The healthcheck helper can be:

- a small pinned image maintained by Heimdall
- a local Python/curl helper image
- a later optimization using Docker container health status

Do not rely on every user image having `curl`, `wget`, or shell tooling installed.

Success means HTTP 2xx or 3xx.

Failure means:

```text
deployment.status = failed
release is not current
project status = failed unless previous current preview remains valid
```

## Release Manifest

The current release model stores one image tag. Multi-service release needs a service image set.

Target release manifest:

```json
{
  "commit_sha": "879092bb4656a80b32442145596365b7cb992585",
  "services": {
    "frontend": {
      "image_tag": "heimdall/portfolio-frontend:879092b",
      "image_id": "sha256:...",
      "container_name": "heimdall-preview-portfolio-frontend",
      "public": true,
      "preview_url": "http://127.0.0.1:18001"
    },
    "backend": {
      "image_tag": "heimdall/portfolio-backend:879092b",
      "image_id": "sha256:...",
      "container_name": "heimdall-preview-portfolio-backend",
      "public": false,
      "internal_url": "http://backend:8000"
    }
  }
}
```

Prefer normalized tables over only JSON where practical:

```text
project_services
deployment_service_results
release_services
```

But storing a manifest JSON column can be acceptable as an interim bridge if the code keeps typed serialization around it.

## Data Model Direction

Add `project_services`:

```text
id
project_id
name
build_context_path
dockerfile_path
container_port
is_public
health_check_path
startup_order
build_env_json
runtime_env_json
required_secrets_json
run_as_heimdall_child
created_at
updated_at
```

Add `deployment_service_results`:

```text
id
deployment_id
service_name
status
status_message
image_tag
image_id
container_name
container_id
started_at
finished_at
duration_ms
```

Add `release_services`:

```text
id
release_id
service_name
image_tag
image_id
container_name
container_port
is_public
preview_url
internal_url
created_at
```

Keep existing single-service columns for backward compatibility during migration.

Existing single-service projects can be represented as one service:

```text
service_name = app
build_context_path = projects.build_context_path
dockerfile_path = projects.dockerfile_path
container_port = projects.container_port
public = true
health_check_path = projects.health_check_path
```

## API Direction

Keep the manual deploy endpoint:

```text
POST /api/projects/{project_id}/deployments
```

It should dispatch based on project deploy mode:

```text
dockerfile single-service
multi_service_dockerfile
dry_run explicit fallback
```

Project create/update should accept services:

```json
{
  "name": "Portfolio",
  "provider": "github",
  "repo_url": "https://github.com/org/repo.git",
  "tracked_branch": "main",
  "deploy_mode": "multi_service_dockerfile",
  "services": [
    {
      "name": "frontend",
      "build_context_path": "frontend",
      "dockerfile_path": "frontend/Dockerfile",
      "container_port": 80,
      "public": true,
      "health_check_path": "/",
      "build_env": {
        "VITE_API_BASE_URL": "/api"
      }
    },
    {
      "name": "backend",
      "build_context_path": "backend",
      "dockerfile_path": "backend/Dockerfile",
      "container_port": 8000,
      "public": false,
      "health_check_path": "/health",
      "required_secrets": ["DATABASE_URL"]
    }
  ]
}
```

Validation rules:

- service names unique per project
- first slice requires exactly one public service
- public service uses project assigned preview host/port
- internal services cannot request host ports
- env names must be valid env keys
- env values must be marked non-secret
- required secrets are names only
- path validation still happens at API and executor boundary

## UI Direction

Registration form:

```text
Source
Build mode: Dockerfile / Multi-service Dockerfile
Services
  + Add service
    name
    build context
    Dockerfile path
    container port
    public toggle
    health path
    startup order
    build env non-secret values
    runtime env non-secret values
    required secret names
```

Project detail:

```text
Project status
Preview URL
Current commit
Services table:
  service
  public/internal
  image tag
  container status
  health
  internal URL
```

Deployment detail:

```text
deployment status
service statuses
sectioned logs grouped by service
failed service and phase
```

Release table:

```text
commit
release status
service image set
current marker
rollback action
```

YAML preview must still exclude:

- assigned preview host port
- current commit
- image tags
- deployment logs
- release history
- secret values

## Rollback Direction

Rollback should be project-level, not service-level, in the first implementation.
When generated project volumes are introduced, image rollback must not imply
application data rollback; the volume-specific policy is tracked in
[Docker Project Volume Support Implementation Plan](docker-project-volume-support.md).

Do this:

```text
rollback release R
-> read release_services for R
-> stop current project service containers
-> run every service from R's image tags
-> health check every service
-> mark R current if all services pass
```

Avoid this in the first slice:

```text
rollback frontend only
rollback backend only
```

Service-level rollback can create compatibility bugs when frontend and backend were built from different commits. Project-level rollback keeps the release as a coherent image set.

## Implementation Order

Recommended next goal order:

1. Update docs/YAML schema for multi-service project config.
2. Add DB tables for project services and release service manifests.
3. Add API schemas and validation for service definitions.
4. Update Web UI registration/edit forms for services.
5. Preserve existing single-service project behavior.
6. Add multi-service executor request/result types.
7. Build service images from one fetched workspace.
8. Create/reuse project Docker network.
9. Run internal services first, then public service.
10. Health check internal and public services.
11. Record service-level deployment results and release manifest.
12. Add project-level rollback from release manifest.
13. Add real two-service smoke test.

## Test Coverage Required

API tests:

- create multi-service project
- reject duplicate service names
- reject zero public services
- reject multiple public services in first slice
- reject path traversal per service
- reject invalid env names
- reject raw secret values in service config
- preserve old single-service project behavior

Executor tests:

- one repo fetch for multiple service builds
- builds each service with correct context/Dockerfile
- creates project network
- runs containers with service labels and aliases
- publishes only public service host port
- does not stop arbitrary containers
- checks internal service health through project network
- records per-service logs
- fails all deployment on one service build failure
- fails all deployment on one service health failure
- creates release manifest only on full success

Smoke test:

```text
repo/
  frontend/Dockerfile
  backend/Dockerfile

Deploy preview
-> backend image built
-> frontend image built
-> backend container internal only
-> frontend container public on assigned preview port
-> browser calls preview URL
-> /api path reaches backend
-> release current with frontend/backend image tags
```

## Open Decisions

These should be settled before implementation starts:

1. Should first slice require the public frontend image to own `/api` proxying, or should Heimdall generate a gateway container?
2. Should `startup_order` be enough initially, or do we need explicit `depends_on`?
3. Should service env values be stored directly if marked non-secret, or should all env values move to runtime env files?
4. Should internal health checks use a pinned Heimdall healthcheck image or Docker native health status?
5. Should multiple public services be postponed until after the single-public-service flow is stable?

Recommended answers for the first implementation:

```text
frontend image owns /api proxying
startup_order only
store non-secret env values, store secret names only
use a pinned Heimdall healthcheck helper for internal HTTP checks
allow exactly one public service
```
