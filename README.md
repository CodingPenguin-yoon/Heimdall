# Heimdall

Heimdall is a developer-convenience platform for server deployment and database auto-connection. GitLab is the control-plane entry: projects are discovered and managed from GitLab, and Heimdall owns the infrastructure and environment-side orchestration around them.

## Current product surface

Today Heimdall already includes:

- GitLab project inventory
- GitLab project creation
- GitLab project settings
- GitLab system hook handling
- Manual `Deploy Staging` for staging infra plus app deployment
- Proxmox template-clone VM deployment
- Terraform and Ansible provisioning flow
- GitLab archive delivery and `docker compose` app rollout on the staging VM
- Instance lifecycle operations and resize
- Task Board, SSE status streaming, and platform state persistence

This means the current product is not just a VM launcher. It already has the first GitLab control-plane slice plus the existing infrastructure operations base behind it.

## Not shipped yet

The following are not yet implemented and should be read as planned capability, not current behavior:

- Bootstrap automation
- GitLab merge/webhook-driven redeploys
- DB provisioner / automatic per-environment database provisioning
- Production environment workflow
- Reverse-proxy and domain automation

## Product boundary

Heimdall’s intended operating model is:

1. GitLab project enters Heimdall through the control plane.
2. Heimdall stores project-level settings and reacts to GitLab events.
3. Infrastructure deployment and database connection automation happen from Heimdall.

The unfinished layers are the bootstrap, environment rollout, and database/domain automation that complete that flow.

## Documentation

Start with [docs/README.md](docs/README.md). That index defines the active documentation hierarchy, links the current product-direction documents, and treats unindexed documents as legacy.
