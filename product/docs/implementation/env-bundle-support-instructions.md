# Env Bundle Support Implementation Instructions

## Objective

Implement the smallest coherent env bundle feature described in
[Env Bundle Support Specification](env-bundle-support-spec.md).

The deliverable should let an operator upload a service `.env` bundle, store it
under Heimdall runtime secrets, keep only metadata in the control database, and
inject it into Dockerfile preview containers with `--env-file`.

## Work Order

1. Refresh the PostgreSQL-only env and folder docs.
2. Add backend storage and DB metadata.
3. Add API endpoints and schemas.
4. Wire deploy-time env-file injection.
5. Add focused tests.
6. Add the Web UI only after the backend contract is stable.

Keep each slice small enough to validate with the existing API and Web test
commands.

## Backend Implementation Notes

### Storage service

Create a dedicated service module, for example:

```text
product/apps/api/app/services/env_bundles.py
```

Reuse the path safety approach from `project_database_secrets.py`:

- all refs are relative
- no absolute paths
- no `.` or `..`
- no backslashes
- no symlink escapes
- parent dirs are `0700`
- bundle files are `0600`
- writes are atomic through a temp file and `os.replace`

The first slice should derive the root from:

```python
settings.secrets_dir / "env-bundles"
```

Do not add `HEIMDALL_ENV_BUNDLE_ROOT` yet.

### Env parsing

Implement a small parser with explicit validation.

Allowed syntax:

```text
KEY=value
export KEY=value
# comment
blank line
```

Use the existing env-name validation style from `validation.py`. Preserve
values only in the stored file and in memory long enough to compute metadata
and write the file.

Return only:

```text
key_names
checksum_sha256
line_count or value_count if useful
```

Never return values.

### Database

Add `project_service_env_bundles` to both SQLite and PostgreSQL bootstrap paths
in `db.py`.

Prefer additive `CREATE TABLE IF NOT EXISTS` work. Do not introduce a risky
table rebuild for this feature.

Fetch env bundle metadata with services where deployments load project service
configuration. Keep the executor-facing object simple, for example:

```python
service["env_bundle"] = {
    "active_ref": "...",
    "key_names": [...],
    "checksum_sha256": "...",
}
```

### API shape

Add schemas such as:

```text
ProjectServiceEnvBundleWrite
ProjectServiceEnvBundleRead
```

The write request may be:

```json
{
  "content": "KEY=value\n"
}
```

The read response must include metadata only. For missing bundles, either
return `configured: false` or `404`; prefer a metadata response if it makes the
UI simpler.

### Project and service checks

Validate that:

- project exists
- service belongs to project
- service ID is stable and real
- deleted services do not keep active bundle rows

For single-service Dockerfile projects, use the persisted `app` service row.
Do not derive physical paths from the service name.

## Executor Instructions

Add env bundle support only to actual Docker run paths:

- single-service `_replace_container`
- multi-service `_replace_service_container`

Before appending `--env-file`, resolve the ref through the env bundle service
and verify the file still exists under `settings.secrets_dir`.

Conflict rules:

- `runtime_env` and env bundle duplicate keys: fail.
- managed runtime env and env bundle duplicate keys: fail.
- build args are separate and do not conflict with runtime env.

Log only metadata:

```text
env bundle configured with N key(s)
env bundle checksum ...
```

Do not add raw env file contents to deployment logs.

## Web UI Instructions

Add the UI after the API behavior has tests.

Recommended first UI:

- section title: Env Bundle
- configured state
- key list
- checksum
- updated timestamp
- textarea or file picker for replace
- delete button

Do not show saved values after upload. The operator can replace the bundle.

## Docs Instructions

Update:

- `product/docs/README.md`
- `product/docs/operations/self-hosting-docker.md`
- `product/docs/architecture/self-hosting-storage.md`
- `product/.env.compose.example` comments if needed

Document PostgreSQL-only operation with:

```text
/srv/heimdall/runtime/logs
/srv/heimdall/runtime/workspaces
/srv/heimdall/runtime/secrets/env-bundles
/srv/heimdall/control-postgres
/srv/heimdall/project-postgres
```

Do not recommend `/srv/heimdall/children` for env bundles.

## Validation

Run API tests after backend changes:

```bash
cd product/apps/api
venv/bin/python -m pytest
```

Run Web build after UI changes:

```bash
cd product/apps/web
pnpm build
```

Add focused tests for:

- valid env parsing
- invalid env parsing
- duplicate keys
- large file rejection
- path traversal and symlink escape rejection
- upload/read/delete API
- no values in read response
- executor uses `--env-file`
- executor rejects duplicate keys between bundle, `runtime_env`, and managed
  runtime env
- deployment logs do not contain env values

## Completion Checklist

- Env bundle root is derived from `settings.secrets_dir`.
- Raw env values are stored only in secret files.
- Control DB stores only metadata.
- Deployments pass env bundles with `--env-file`.
- Existing no-env-bundle deployments still pass.
- PostgreSQL-only env and VM folder docs are updated.
- Remaining risks are documented in the final response.
