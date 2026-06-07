# Heimdall Product Docs

Heimdall is a Git-based preview deployment manager. These docs are organized by product area instead of one-off goal notes.

## Read First

1. [Product Overview](product/overview.md)
2. [Single-server Preview Architecture](architecture/single-server-preview.md)
3. [Self-hosting Storage Architecture](architecture/self-hosting-storage.md)
4. [Docker Project Volume Support Implementation Plan](implementation/docker-project-volume-support.md)
5. [Nested Heimdall Child Deploy Implementation Plan](implementation/trusted-heimdall-child-mode.md)
6. [Self-hosting Docker Runbook](operations/self-hosting-docker.md)
7. [Nested Heimdall Operations](operations/nested-heimdall-operations.md)
8. [Data Model](architecture/data-model.md)
9. [Project Config YAML](config/project-yaml.md)
10. [Legacy UI Migration Plan](ui/legacy-ui-migration.md)
11. [Implementation Roadmap](implementation/roadmap.md)
12. [Preview Deployment Pipeline](implementation/preview-deployment-pipeline.md)
13. [Multi-service Preview Deployment Plan](implementation/multi-service-preview.md)

## Directory Map

```text
product/
  Product identity, scope, non-goals.

architecture/
  Runtime architecture, deployment flow, persistence model.

config/
  .heimdall/project.yaml schema and source-of-truth policy.

operations/
  Operator runbooks for Docker self-hosting.

ui/
  Web UI direction and legacy design migration.

implementation/
  Build order and near-term milestones.
```

## Current Product Boundary

In scope:

- GitHub/GitLab project registration
- tracked branch push handling
- single-server preview deployment
- real local Dockerfile deploys when `dry_run=false`
- explicit dry-run simulated deployments
- multi-service Dockerfile preview deployment
- deployment logs and history
- release tracking
- rollback control
- web UI control surface

Out of scope:

- VM/Proxmox lifecycle
- Gjallar dependency in MVP
- remote staging VM orchestration
- production hosting
- raw secret storage
- generated project bind mounts until the
  [implementation plan](implementation/docker-project-volume-support.md) is
  implemented
- Docker Compose deployment
- unrestricted shell execution

Self-hosted Docker operation requires operator-approved Heimdall API containers
with access to `/var/run/docker.sock`. That socket effectively grants control
of the VM Docker daemon and must never be mounted into normal user preview
containers.
