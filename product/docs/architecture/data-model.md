# Data Model

## Core Tables

Current MVP foundation models:

- Project
- ProjectService
- Deployment
- Release
- ReleaseService
- PortAllocation
- WebhookEvent

Future models:

- ProviderConnection
- ProjectEnvironment
- ProjectConfigSpec

## Project

Stores registered repository and preview settings.

Key fields:

- provider: `github` or `gitlab`
- repo URL
- tracked branch
- deploy mode
- build context path
- Dockerfile path
- container port
- assigned preview host/port
- health check path/URL
- auto deploy flag
- status
- current real release reference

Project settings are controlled through the UI/API. Repo YAML can import/export build/runtime spec, but Heimdall keeps operational assignment state in SQLite.

## ProjectService

Stores per-service Dockerfile preview configuration for multi-service projects
and the synthesized `app` service for single-service compatibility.

Key fields:

- project ID
- service name
- build context path
- Dockerfile path
- container port
- public preview entry flag
- health check path
- startup order
- build/runtime environment JSON
- required secret names JSON
- `run_as_heimdall_child`, limited to at most one service per project

## Deployment

Stores one deployment attempt.

Key fields:

- project ID
- trigger type
- requested ref
- resolved commit
- image tag
- previous release
- target release
- status
- status message
- dry-run flag
- log path
- timestamps

Deployment statuses include real deployment states and explicit dry-run
simulation:

```text
queued
fetching
building
starting
health_checking
success
failed
cancelled
rollback_success
rollback_failed
dry_run_success
```

`dry_run_success` is intentionally separate from real deployment success.

## Release

Stores a runnable or simulated release candidate.

Release statuses include real image-backed releases and simulated dry-run
records:

```text
available
current
superseded
missing_image
disabled
simulated
```

Simulated releases:

- are useful for flow visibility
- are not real running previews
- are not marked current
- cannot be rollback targets

Real Docker releases use image-backed statuses such as `current` and
`superseded`. Simulated releases are not rollback targets.

## PortAllocation

Tracks preview host/port ownership.

This prevents duplicate preview ports across projects. Host ports belong to Heimdall DB/runtime state, not repo YAML.

## WebhookEvent

Stores received provider events for audit and idempotency.

Key fields:

- provider
- event type
- delivery ID
- project ID
- branch
- commit SHA
- status
- deployment ID
- error message

Webhook handlers should enqueue or record deployment work and return quickly.
