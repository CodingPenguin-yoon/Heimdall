# Heimdall

Heimdall is a Git-based preview deployment manager.

- `product/` contains the current implementation.
- `legacy/old-devops-console/` contains the archived previous DevOps console.
- Gjallar owns VM and Proxmox lifecycle.
- Heimdall owns Git repo integration, local preview deployment, Docker release history, logs, and rollback.

The repository root keeps governance and shared repo configuration only.
