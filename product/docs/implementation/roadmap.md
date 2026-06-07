# Implementation Roadmap

## Current Foundation

Implemented:

- FastAPI API scaffold
- SQLite persistence
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

Current executor behavior:

```text
dry_run=false performs clone/fetch, Docker build, container start, health check
dry_run=true records a simulated dry-run release
preview containers do not receive generated bind mounts yet
compose mode is unsupported
rollback remains disabled for simulated releases
```

## Next Milestones

1. Rework web UI with legacy console visual language.
2. Add `.heimdall/project.yaml` schema types and parser.
3. Add config validate/import/export API.
4. Add UI YAML preview/import/export panel.
5. Add provider token reference model.
6. Add scoped token handling through `.env` or ignored runtime secrets.
7. Add automatic webhook registration.
8. Harden the [Preview Deployment Pipeline](preview-deployment-pipeline.md).
9. Add
   [generated project-volume bind mounts](docker-project-volume-support.md)
   after the storage contract is implemented.
10. Add real rollback from single-service and multi-service release manifests.
11. Add compose mode after Dockerfile modes are stable.

The multi-service direction is documented in [Multi-service Preview Deployment Plan](multi-service-preview.md).

## Near-term Backend Work

The next backend slice should follow [Preview Deployment Pipeline](preview-deployment-pipeline.md).

Provider token handling:

```text
DB stores token_ref only.
Token values live in .env or ignored runtime secret storage.
UI never shows saved token values.
Logs redact token-like values.
```

## Near-term Web Work

- legacy-style header/tabs
- project table-first layout
- config form grouped by Source, Build, Runtime, Health, Webhook
- YAML preview panel
- dry-run vs real preview status clearly labeled
- release table with rollback disabled for simulated releases

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
