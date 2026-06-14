# Data Model

## Core Tables

Current MVP foundation models:

- Project
- ProjectService
- ProjectDatabase
- ProjectDatabaseBinding
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

Project settings are controlled through the UI/API. Repo YAML can import/export
build/runtime spec, but Heimdall keeps operational assignment state in its
control database. SQLite is available for local/dev control state; PostgreSQL
is supported when `HEIMDALL_DATABASE_URL` points at an operator-managed control
Postgres database. `HEIMDALL_DATABASE_URL` is not a project application
database URL.

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

## ProjectDatabase

Implemented model for managed project application PostgreSQL metadata.

The application database itself lives in the separate project PostgreSQL
service/cluster, not in Heimdall's control database. The control database
stores only metadata needed to provision, audit, inject, retain, orphan, or
purge the project database resource.

Key fields:

- project ID
- generated database name
- generated role/user name
- password secret reference
- app host and port used for deploy-time URL assembly
- Docker DB network name
- lifecycle status
- retention/orphan state
- provisioned timestamp
- last error

Generated database and role names are based on immutable project IDs, not
mutable slugs. Heimdall stores the exact generated identifier because
PostgreSQL truncates long identifiers and SQL must quote identifiers with
structured APIs.

Forbidden fields:

- raw project database password
- raw project `DATABASE_URL`
- provisioner/admin `DATABASE_URL`

## ProjectDatabaseBinding

Implemented model for mapping a managed project database to service env
injection.

Key fields:

- project database ID
- project ID
- optional service ID for multi-service projects
- env var name, usually `DATABASE_URL`
- required secret name, when imported from YAML dependency intent

The binding tells deployment which service receives a deploy-time assembled
`DATABASE_URL`. It must not store the assembled value.

There is no implemented project database audit-event table yet. Lifecycle
status and redacted last error live on `project_databases`.

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

This prevents duplicate preview ports across projects. Host ports belong to
Heimdall API database/runtime state, not repo YAML.

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
