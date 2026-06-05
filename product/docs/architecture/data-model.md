# Data Model

## Core Tables

Current MVP foundation models:

- Project
- Deployment
- Release
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

Current dry-run deployment status:

```text
dry_run_success
```

This is intentionally separate from real deployment success.

## Release

Stores a runnable or simulated release candidate.

Current dry-run release status:

```text
simulated
```

Simulated releases:

- are useful for flow visibility
- are not real running previews
- are not marked current
- cannot be rollback targets

Real Docker releases will later use `available`, `current`, `superseded`, and `missing_image`.

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
