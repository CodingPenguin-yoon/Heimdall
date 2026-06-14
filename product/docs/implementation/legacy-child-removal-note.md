# Legacy Child Removal Note

## Preflight Result

Recorded for the legacy child removal slice:

- Local `product-runtime/state/heimdall.db` had `0` projects with
  `projects.run_as_heimdall_child=1`.
- Local `product-runtime/state/heimdall.db` had `0` project services with
  `project_services.run_as_heimdall_child=1`.
- `/srv/heimdall/children` was missing.
- No child runtime roots or project-volume roots were deleted.

## Cleanup Boundary

Normal product code no longer creates, updates, serializes, displays, deploys,
or injects runtime settings for nested/child Heimdall.

Existing SQLite databases may still contain legacy `run_as_heimdall_child`
columns on `projects` or `project_services`. Those columns are ignored by the
application and are left as DB-only cleanup unless a future table-rebuild
migration is explicitly planned.
