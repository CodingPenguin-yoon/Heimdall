# Legacy UI Migration Plan

## Decision

Use the legacy frontend as a design reference only.

Do not revive the legacy product.

## Useful Legacy References

From `legacy/old-devops-console/frontend/src/App.jsx`:

- clear header
- top tab navigation
- console-style layout

From `legacy/old-devops-console/frontend/src/components/DevOpsDashboard.jsx`:

- summary cards
- status pills
- refresh actions
- white panels with light borders
- dense operational sections

From `legacy/old-devops-console/frontend/src/components/GitLabWorkspace.jsx`:

- guided configuration form
- YAML preview/edit workflow
- readiness badges

## Do Not Bring Back

- VM list
- Proxmox controls
- instance lifecycle actions
- LLM assistant screens
- staging host registry
- old DevOps dashboard language
- GitLab-only assumptions

## New UI Shape

Keep the first screen operational.

Top navigation:

```text
Projects
Deployments
Settings
```

Project page:

- project list table
- selected project detail
- manual deploy action
- deployment history
- log panel
- release table
- rollback availability
- `.heimdall/project.yaml` import/export panel

## Visual Direction

Use:

- white surfaces
- light borders
- compact status badges
- dense tables
- restrained colors
- predictable tabs
- clear operational actions

Avoid:

- landing pages
- decorative hero sections
- VM/infrastructure vocabulary
- oversized cards
- one-note color themes

## Migration Order

1. Replace current MVP web layout with legacy-style header and tabs.
2. Add summary strip for projects/deployments/releases.
3. Convert project list/detail into table-first operational layout.
4. Add guided project registration form.
5. Add YAML preview/import/export panel.
6. Add deployment log drawer/panel.
7. Add release/rollback panel.
