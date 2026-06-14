# Implementation Roadmap

## Current Foundation

Implemented:

- FastAPI API scaffold
- Heimdall control DB persistence with SQLite and PostgreSQL support through
  `HEIMDALL_DATABASE_URL`
- Project CRUD
- Deployment, Release, PortAllocation, WebhookEvent models
- manual deploy endpoint
- dry-run local Docker executor for simulated deploys
- real local Dockerfile executor
- multi-service Dockerfile preview deploy
- sectioned deployment logs
- GitHub/GitLab webhook endpoints
- provider tokens loaded from ignored local `.env`
- GitHub/GitLab repository access validation
- GitHub/GitLab webhook registration and reuse
- webhook secret verification
- React/Vite web scaffold
- legacy-console-style project list/create/detail/deployment/log/release UI
- `.heimdall/project.yaml` frontend preview
- managed project PostgreSQL config, metadata, secret storage, provisioning,
  deploy-time injection, delete-orphan retention, purge, and UI lifecycle
  controls

Current executor behavior:

```text
dry_run=false performs clone/fetch, Docker build, container start, health check
dry_run=true records a simulated dry-run release
preview containers do not receive generated bind mounts yet
managed project PostgreSQL is available for Dockerfile preview projects
compose mode is unsupported
rollback remains disabled for simulated releases
image rollback does not restore managed PostgreSQL data
```

## Next Milestones

1. Pivot implementation toward the
   [single outer Heimdall direction](single-outer-heimdall-direction.md).
2. Keep nested/child Heimdall as deprecated historical context only.
3. Rework web UI with legacy console visual language.
4. Add `.heimdall/project.yaml` schema types and parser.
5. Add config validate/import/export API.
6. Add UI YAML preview/import/export panel.
7. Add provider token reference model.
8. Add scoped token handling through `.env` or ignored runtime secrets.
9. Add automatic webhook registration.
10. Harden the [Preview Deployment Pipeline](preview-deployment-pipeline.md).
11. Add
   [generated project-volume bind mounts](docker-project-volume-support.md)
   after the storage contract is implemented.
12. Add managed project PostgreSQL live smoke tests, backup/runbook hardening,
   orphan inventory/adoption, and password rotation.
13. Add real rollback from single-service and multi-service release manifests.
14. Add compose mode after Dockerfile modes are stable.

The multi-service direction is documented in [Multi-service Preview Deployment Plan](multi-service-preview.md).

## Near-term Backend Work

The next backend slice should follow [Preview Deployment Pipeline](preview-deployment-pipeline.md).

Provider token and app secret handling:

```text
DB stores token_ref only.
Token and generated app DB password values live in .env, ignored runtime
secret storage, or an equivalent server-side secret provider.
UI never shows saved token values.
Logs redact token-like values, admin DB URLs, app DATABASE_URL values, and
generated role passwords.
```

Single outer Heimdall pivot:

```text
One operator-managed Heimdall API/Web is the supported self-hosting model.
Nested child Heimdall is legacy/deprecated, not the default path.
Existing child rows and roots need staged operator cleanup if they exist.
Normal product code no longer creates, deploys, or displays child Heimdall.
```

Managed project PostgreSQL order:

```text
implemented: compose target and docs
-> API config and control DB metadata
-> first-class generated password secret refs
-> Postgres provisioner with quoted identifiers and autocommit
-> single-service and multi-service DB network attachment
-> deploy-time DATABASE_URL assembly and injection
-> explicit retain/orphan/purge lifecycle UI
remaining: live smoke, backups, orphan inventory/adoption, password rotation
```

Legacy child cleanup notes:

1. Do not delete `/srv/heimdall/children` automatically.
2. Require backup and explicit operator confirmation before removing legacy
   child runtime state or project volumes.
3. Existing SQLite DB legacy child columns may remain as DB-only cleanup until a
   table-rebuild migration is worth the risk.

## Near-term Web Work

- legacy-style header/tabs
- project table-first layout
- config form grouped by Source, Build, Runtime, Health, Webhook
- YAML preview panel
- dry-run vs real preview status clearly labeled
- release table with rollback disabled for simulated releases
- managed PostgreSQL status, retry, purge, and dependency-intent controls

## Validation Gates

Run after each meaningful change:

```bash
cd product/apps/api
venv/bin/python -m pytest
```

```bash
cd product/apps/web
pnpm build
```

For running locally:

```bash
cd product/apps/api
venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 18080
```

```bash
cd product/apps/web
VITE_API_BASE_URL=http://127.0.0.1:18080 pnpm exec vite --host 127.0.0.1 --port 15173
```
