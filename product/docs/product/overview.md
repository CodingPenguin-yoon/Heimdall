# Product Overview

## Definition

Heimdall is a Git-based preview deployment manager.

Existing GitHub or GitLab repositories are registered in Heimdall. Heimdall tracks the configured branch, receives webhook events, builds and runs preview deployments, records deployment history, and exposes logs, releases, and rollback controls through the web UI.

## Goal

The first useful flow is:

```text
register repo
-> deploy manually
-> inspect preview status and logs
-> trigger deploy from main branch webhook
-> rollback to a previous release
```

The product is meant for fast development feedback, not production hosting.

## Scope

Heimdall owns:

- project registration
- repository metadata
- webhook receiving
- local workspace management
- preview deployment execution
- Docker image/release history
- deployment logs
- rollback control
- project settings UI

## Non-goals

Heimdall does not own:

- Proxmox VM/LXC lifecycle
- server provisioning
- Gjallar host allocation in the MVP
- Kubernetes
- production-grade traffic routing
- provider-wide admin automation
- repository deletion or permission management

## Boundary With Gjallar

Gjallar is the infrastructure lifecycle tool.

Heimdall is the project preview deployment tool.

Future integration can let Heimdall discover or request deployment hosts from Gjallar, but the MVP must work without Gjallar.

## Security Direction

Use the smallest provider permissions possible.

Avoid:

- admin/root provider tokens
- broad personal access tokens
- storing raw tokens, generated database passwords, or raw `DATABASE_URL`
  values in the control database
- logging tokens, webhook secrets, database passwords, or raw `DATABASE_URL`
  values

Prefer:

- repository/project-scoped tokens
- token and credential references in the control database
- values stored in `.env`, ignored runtime secret storage, or an equivalent
  server-side secret provider
- read-only clone access plus webhook management permission
