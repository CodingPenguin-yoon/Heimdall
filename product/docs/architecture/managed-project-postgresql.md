# Managed Project PostgreSQL

## Decision Summary

Heimdall must keep its control database separate from project application
databases.

The control database is Heimdall-owned state only. It stores projects,
deployments, releases, port allocations, webhook events, project service
configuration, project volume metadata, and managed database metadata. It is
configured through `HEIMDALL_DATABASE_URL`.

Project application data belongs in a separate PostgreSQL service or cluster.
The target product-managed model is one shared project PostgreSQL cluster with
one generated database and one generated login role per project. Application
containers receive a deploy-time `DATABASE_URL` assembled by Heimdall. The raw
URL, database password, and provisioner/admin credential must not be stored in
repo YAML, `runtime_env`, logs, normal API responses, or the Web UI.

## Current Status

Implemented today:

- Heimdall can use SQLite or PostgreSQL for its own control database through
  `HEIMDALL_DATABASE_URL`.
- The product Compose topology includes `heimdall-postgres` for control state.
- The product Compose topology also includes `project-postgres` and
  `heimdall-project-db` as the target app-database service/network.
- API config and redaction for managed project database settings.
- Control DB metadata tables for managed database resources and service
  bindings.
- Server-side generated password storage under the ignored runtime secret
  directory.
- PostgreSQL provision/retry behavior for one database and one login role per
  project.
- Deploy-time `DATABASE_URL` assembly and injection into bound containers only.
- Local Docker network attachment for DB-backed single-service and
  multi-service previews.
- Default project delete marks managed DB metadata `orphaned` and retains data.
- Explicit purge terminates sessions, drops the database and role, deletes the
  secret after SQL success, and marks the resource `purged`.
- Web UI controls show redacted lifecycle metadata and expose retry/purge
  actions.

Still operator-managed or future work:

- Live disposable PostgreSQL/Docker smoke coverage beyond unit/integration
  tests.
- Backups, point-in-time restore, orphan inventory/adoption, password rotation,
  HA, and production database operations.

## Terminology And Plane Separation

Control plane:

- The Heimdall API and Web UI.
- The trusted API container with Docker socket access.
- The Heimdall control database configured by `HEIMDALL_DATABASE_URL`.
- Operator-owned env files and secret stores.

Data plane:

- Project preview containers.
- Project application database roles and databases.
- Generated project volumes.
- Project Docker networks.

The control plane can reach the project PostgreSQL service for provisioning.
Project preview containers must never join the `heimdall-control` network.
They should reach application databases only through the dedicated project DB
network.

## Target Compose Topology

The product Compose path should run four logical services:

```text
heimdall-postgres
  control DB for Heimdall state
  network: heimdall-control
  no host 5432 publish

project-postgres
  shared project app DB cluster
  networks: heimdall-control, heimdall-project-db
  no host 5432 publish

api
  trusted Heimdall API
  network: heimdall-control
  Docker socket mounted

web
  static Web UI
  network: heimdall-control
```

DB-backed preview containers join:

```text
single-service project:
  heimdall-project-db

multi-service project:
  project-private preview network
  heimdall-project-db, only for services that require the app database
```

Preview containers must not join `heimdall-control`. `project-postgres` should
not publish host port `5432` by default. Operators who need external access for
maintenance should use an explicit admin path such as `docker compose exec`,
SSH tunnel, VPN, or a separately firewalled override.

## Env And Config Contract

Implemented:

```text
HEIMDALL_DATABASE_URL
```

This is only the Heimdall control database URL. It must not be reused as an
application database URL for projects.

Compose-only initialization variables:

```text
HEIMDALL_CONTROL_POSTGRES_DB
HEIMDALL_CONTROL_POSTGRES_USER
HEIMDALL_CONTROL_POSTGRES_PASSWORD
HEIMDALL_CONTROL_POSTGRES_DATA_DIR
HEIMDALL_PROJECT_POSTGRES_DB
HEIMDALL_PROJECT_POSTGRES_USER
HEIMDALL_PROJECT_POSTGRES_PASSWORD
HEIMDALL_PROJECT_POSTGRES_DATA_DIR
```

Managed project DB variables:

```text
HEIMDALL_PROJECT_DATABASE_ADMIN_URL
HEIMDALL_PROJECT_DATABASE_APP_HOST
HEIMDALL_PROJECT_DATABASE_APP_PORT
HEIMDALL_PROJECT_DATABASE_NETWORK
```

`HEIMDALL_PROJECT_DATABASE_ADMIN_URL` is an API-only provisioner credential. It
must never be injected into preview containers. It is used only to create,
alter, and drop project roles/databases.

`HEIMDALL_PROJECT_DATABASE_APP_HOST`, `HEIMDALL_PROJECT_DATABASE_APP_PORT`, and
`HEIMDALL_PROJECT_DATABASE_NETWORK` describe the data-plane endpoint used when
assembling application `DATABASE_URL` values at deploy time.

Repo YAML may declare dependency intent:

```yaml
database:
  required: true
  type: postgres
  env_var: DATABASE_URL
```

Repo YAML and `runtime_env` must not contain the raw `DATABASE_URL`, database
password, provisioner URL, or any other secret value.

## Data Model Additions

Implemented project-level managed database resource table:

```text
project_databases
  id TEXT PRIMARY KEY
  project_id TEXT NOT NULL
  database_name TEXT NOT NULL
  role_name TEXT NOT NULL
  password_secret_ref TEXT NOT NULL
  app_host TEXT NOT NULL
  app_port INTEGER NOT NULL
  network_name TEXT NOT NULL
  status TEXT NOT NULL
  retention_policy TEXT NOT NULL
  orphaned_at TEXT
  created_at TEXT NOT NULL
  updated_at TEXT NOT NULL
  provisioned_at TEXT
  last_error TEXT

  UNIQUE(project_id)
  UNIQUE(database_name)
  UNIQUE(role_name)
```

Implemented service binding table for deploy-time injection:

```text
project_database_bindings
  id TEXT PRIMARY KEY
  project_database_id TEXT NOT NULL
  project_id TEXT NOT NULL
  service_id TEXT
  env_var_name TEXT NOT NULL
  required_secret_name TEXT
  created_at TEXT NOT NULL
  updated_at TEXT NOT NULL

  UNIQUE(project_id, service_id, env_var_name)
```

There is no implemented `project_database_events` audit table yet. Control DB
rows store generated identifiers and secret references, not raw database
passwords or full connection URLs.

## API And UI Flow

Create or enable managed database:

1. User marks a project as requiring PostgreSQL, either in UI or by importing
   YAML dependency intent.
2. API validates that the requested env var name is an env key such as
   `DATABASE_URL`.
3. API creates a `project_databases` row in `pending` state.
4. Provisioner creates the database, role, grants, and password secret.
5. API marks the resource `active` and shows redacted metadata in the UI.

Deploy:

1. Deployment loads the project database metadata and binding.
2. Secret resolver retrieves the project role password by
   `password_secret_ref`.
3. Deployment assembles `DATABASE_URL` in memory.
4. Executor injects the URL into only the service containers that require it.
5. Logs, API responses, UI state, and release records show only that the secret
   was provided by name.

Read/update UI:

- Show status, env var name, database resource ID, and lifecycle actions.
- Do not show the role password, raw `DATABASE_URL`, or admin URL.
- Password rotation remains future work.
- Require explicit confirmation for destructive purge.

Delete:

- Default project delete should mark the project database orphaned and retain
  data.
- Purge should be a separate action with explicit application-data
  confirmation.

## Provisioning Algorithm

Identifier generation:

- Generate database and role names from immutable project/service IDs plus
  short hashes.
- Do not derive database or role identifiers from mutable project slugs.
- Keep generated identifiers well under PostgreSQL's 63-byte identifier limit
  and store the exact generated names in the control DB.
- Use structured identifier quoting in implementation, for example
  `psycopg.sql.Identifier`. PostgreSQL identifiers are not value parameters and
  must not be interpolated with ad hoc string formatting.

Provision:

1. Open the admin connection from `HEIMDALL_PROJECT_DATABASE_ADMIN_URL`.
2. Enable autocommit before `CREATE DATABASE` or `DROP DATABASE`.
3. Generate and store `database_name`, `role_name`, and password secret.
4. Create the role if it does not exist:

   ```sql
   CREATE ROLE <role_name>
     LOGIN
     NOSUPERUSER
     NOCREATEDB
     NOCREATEROLE
     PASSWORD <password>;
   ```

5. Create the database:

   ```sql
   CREATE DATABASE <database_name> OWNER <role_name>;
   ```

6. Connect to the new database as the admin/provisioner role.
7. Revoke default broad access and grant only the project role:

   ```sql
   REVOKE CONNECT, TEMPORARY ON DATABASE <database_name> FROM PUBLIC;
   GRANT CONNECT, TEMPORARY ON DATABASE <database_name> TO <role_name>;
   REVOKE CREATE ON SCHEMA public FROM PUBLIC;
   GRANT USAGE, CREATE ON SCHEMA public TO <role_name>;
   ```

8. Mark the control DB resource `active`.

Drop/purge:

1. Require explicit purge confirmation.
2. Disable new deploys for the database resource.
3. Terminate active sessions owned by the project role or connected to the
   project database.
4. Enable autocommit for the admin connection.
5. Drop the database.
6. Drop the role.
7. Delete the password secret after SQL succeeds.
8. Mark the resource `purged`.

The first implementation can be fail-fast and operator-visible rather than
trying to hide partial failures. Partial states must be recorded so a retry can
continue safely.

## Docker Network Model

Implemented executor behavior:

- Single-service DB-backed previews join `heimdall-project-db`.
- Multi-service previews keep their project-private network for service DNS.
- DB-backed services also join `heimdall-project-db`.
- Non-DB services do not need the DB network unless the project explicitly
  requires it.
- No preview container joins `heimdall-control`.
- Project PostgreSQL is reachable by the app host alias, for example
  `project-postgres`.
- Project PostgreSQL does not publish host port `5432` by default.

Network cleanup must be label-scoped and must not delete the shared
`heimdall-project-db` network as part of project container replacement.

## Secret And Redaction Model

Managed project database credentials are first-class secrets:

- Store the generated project role password in a secret store or ignored
  operator-owned secret file.
- Store only `password_secret_ref` in the control DB.
- Assemble `DATABASE_URL` only during deploy.
- Inject `DATABASE_URL` only into the intended project service containers.
- Never persist raw `DATABASE_URL` in `runtime_env`, repo YAML, release
  manifests, deployment logs, normal API responses, or UI state.

The provisioner/admin credential is more sensitive than app credentials:

- It lives only in operator config for the trusted API.
- It is never returned by API.
- It is never injected into previews.
- It must be redacted from logs using the same token redaction path as provider
  tokens and webhook secrets.

Redaction should match complete URLs, passwords, role passwords, admin URLs,
and known secret env var values. Logs may say `DATABASE_URL provided from
managed_project_postgresql` but must not show the value.

## Lifecycle, Delete, Backup, And Restore

Project delete default:

- Stop/remove Heimdall-managed containers.
- Retain managed project database data.
- Mark the `project_databases` row `orphaned` or retain a tombstone with
  `orphaned_at`.
- Stop injecting the database into future previews unless the project is
  restored.

Project purge:

- Separate destructive action.
- Requires exact typed confirmation.
- Terminates sessions and drops the database and role.
- Deletes the role password secret after SQL succeeds.
- Test purge only with disposable databases until the operator has current
  `project-postgres` backups.

Backup:

- Back up `heimdall-postgres` separately from `project-postgres`.
- Control DB backups preserve Heimdall metadata and secret references.
- Project DB backups preserve application data.
- Secret-store backups must be coordinated with both DB backups so restored
  metadata can still resolve credentials.

Restore:

- Restore control DB and project DB from coordinated snapshots where possible.
- If control metadata points to missing project DB resources, mark them
  `needs_repair` and require operator action.
- If project DB data exists without control metadata, treat it as orphaned and
  require explicit import/adoption tooling later.

## Rollback Limitation

Image rollback does not roll back PostgreSQL data.

Rolling a project preview back to an earlier release should recreate containers
and re-inject the current managed database credential. It must not promise a
database restore. UI copy and API status should make this explicit for any
release that has a managed project database binding.

Point-in-time database restore is a separate operator workflow and is out of
scope for normal release rollback.

## Implementation Status

Implemented:

- Run separate `heimdall-postgres` and `project-postgres` services.
- Document the control/data-plane boundary.
- Add managed DB settings to API config.
- Add `project_databases` and binding tables.
- Add redacted read models.
- Add tests proving raw URLs and passwords are not stored in DB-facing project
  config, YAML, logs, or API responses.
- Add first-class generated project DB password storage.
- Store secret refs in control DB.
- Add redaction for generated database credentials and admin URL.
- Add PostgreSQL admin connection handling.
- Use autocommit for `CREATE DATABASE` and `DROP DATABASE`.
- Quote identifiers with structured APIs.
- Implement create, retry, orphan, and purge state transitions.
- Add isolation grants and revocations.
- Attach single-service DB-backed previews to `heimdall-project-db`.
- Attach DB-backed services in multi-service previews to
  `heimdall-project-db`.
- Assemble and inject `DATABASE_URL` at deploy time.
- Keep the admin URL API-only.
- Add database requirement/status controls.
- Add redacted metadata display.
- Add explicit purge confirmation.

Not yet implemented:

- Live disposable PostgreSQL/Docker smoke tests.
- Password rotation.
- Orphan inventory/adoption UI after project deletion.
- Project database backup/restore automation, PITR, HA, or cloud database
  abstraction.

## Validation And Test Plan

Compose validation:

```bash
cd product
docker compose --env-file .env.compose.example -f compose.yaml config --quiet
```

Docs consistency should include stale-wording searches for old SQLite-only
state language, old Compose service names, old storage paths, and outdated
claims about managed project PostgreSQL implementation status.

Code tests:

- API config rejects missing project DB settings only when a managed DB feature
  is used.
- Generated identifiers are stable across slug rename.
- Generated identifiers remain below PostgreSQL identifier length limits.
- Identifier quoting uses structured APIs.
- `CREATE DATABASE` and `DROP DATABASE` run with autocommit.
- Provisioning revokes public `CONNECT` and `TEMPORARY`.
- App role is `LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE`.
- Raw `DATABASE_URL`, role password, and admin URL are absent from YAML,
  `runtime_env`, logs, release manifests, normal API responses, and UI state.
- Single-service DB-backed previews join the project DB network.
- Multi-service DB-backed services join both their project network and the DB
  network.
- Project delete retains DB data by default.
- Purge drops DB and role only after explicit confirmation.
- Rollback does not claim to restore database state.

## Non-goals

- Storing raw `DATABASE_URL` in YAML, `runtime_env`, control DB rows, or UI.
- Injecting provisioner/admin credentials into preview containers.
- Host-publishing project PostgreSQL port `5432` by default.
- Per-branch or per-release databases in the first managed DB implementation.
- Automatic application schema migrations.
- Automated backups, orphan adoption, password rotation, and database restore
  workflows.
- Database point-in-time restore through release rollback.
- High-availability PostgreSQL, replication, or managed cloud database
  abstraction.
