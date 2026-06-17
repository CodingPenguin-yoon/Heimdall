# Heimdall Product Docs

Heimdall is a Git-based preview deployment manager. These docs are organized by product area instead of one-off goal notes.

## Read First

1. [Single-server Preview Architecture](architecture/single-server-preview.md)
2. [Managed Project PostgreSQL](architecture/managed-project-postgresql.md)
3. [Self-hosting Storage Architecture](architecture/self-hosting-storage.md)
4. [Self-hosting Docker Runbook](operations/self-hosting-docker.md)
5. [Implementation Roadmap](implementation/roadmap.md)
6. [Project Config YAML](config/project-yaml.md)
7. [Product Overview](product/overview.md)
8. [Single Outer Heimdall Direction](implementation/single-outer-heimdall-direction.md)
9. [Docker Project Volume Support Implementation Plan](implementation/docker-project-volume-support.md)
10. [Env Bundle Support Specification](implementation/env-bundle-support-spec.md)
11. [Env Bundle Support Implementation Instructions](implementation/env-bundle-support-instructions.md)
12. [Data Model](architecture/data-model.md)
13. [Preview Deployment Pipeline](implementation/preview-deployment-pipeline.md)
14. [Multi-service Preview Deployment Plan](implementation/multi-service-preview.md)

## Legacy / Deprecated

These docs describe implemented or historical child Heimdall behavior. They are
not the primary supported self-hosting path for new work.

- [Nested Heimdall Operations](operations/nested-heimdall-operations.md)
- [Nested Heimdall Child Deploy Implementation Plan](implementation/trusted-heimdall-child-mode.md)
- [Nested Heimdall Child Deploy Handoff](implementation/trusted-heimdall-child-mode-handoff.md)
- [Single Outer Child Cleanup Instructions](implementation/single-outer-child-cleanup-instructions.md)
- [Legacy Child Removal Note](implementation/legacy-child-removal-note.md)

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
- Heimdall control DB backed by SQLite in local/dev or PostgreSQL in the
  product Compose path
- managed project PostgreSQL provisioning, deploy-time injection, retry,
  delete-orphan retention, purge, and UI lifecycle controls
- per-service env bundle upload, replacement, deletion, metadata-only API
  reads, secret-file storage under `runtime/secrets/env-bundles`, and
  deploy-time Docker `--env-file` injection

Out of scope:

- VM/Proxmox lifecycle
- Gjallar dependency in MVP
- remote staging VM orchestration
- production hosting
- raw secret storage in the control database, API responses, UI state, or
  deployment logs
- generated project bind mounts until the
  [implementation plan](implementation/docker-project-volume-support.md) is
  implemented
- project `deploy_mode=compose` deployment
- unrestricted shell execution
- managed project PostgreSQL backups, orphan inventory/adoption, password
  rotation, point-in-time restore, and HA beyond operator-managed workflows

Self-hosted Docker operation requires operator-approved Heimdall API containers
with access to `/var/run/docker.sock`. That socket effectively grants control
of the VM Docker daemon and must never be mounted into normal user preview
containers.

The primary self-hosting path is a single outer Heimdall API/Web instance.
Nested child Heimdall is legacy/deprecated for the near term.
