# Heimdall Product Docs

Heimdall is a Git-based preview deployment manager. These docs are organized by product area instead of one-off goal notes.

## Read First

1. [Product Overview](product/overview.md)
2. [Single-server Preview Architecture](architecture/single-server-preview.md)
3. [Data Model](architecture/data-model.md)
4. [Project Config YAML](config/project-yaml.md)
5. [Legacy UI Migration Plan](ui/legacy-ui-migration.md)
6. [Implementation Roadmap](implementation/roadmap.md)
7. [Preview Deployment Pipeline](implementation/preview-deployment-pipeline.md)
8. [Multi-service Preview Deployment Plan](implementation/multi-service-preview.md)

## Directory Map

```text
product/
  Product identity, scope, non-goals.

architecture/
  Runtime architecture, deployment flow, persistence model.

config/
  .heimdall/project.yaml schema and source-of-truth policy.

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
- local Docker executor, currently dry-run
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
- unrestricted shell execution
