# Nested Heimdall Child Deploy Minimum Slice Handoff

> Deprecated legacy handoff. Nested/child Heimdall is historical context, not
> the supported self-hosting model. Use
> [Single Outer Heimdall Direction](single-outer-heimdall-direction.md) and
> [Managed Project PostgreSQL](../architecture/managed-project-postgresql.md)
> for current direction.

## Purpose

Concise handoff for implementing the minimum child-runner slice from
`trusted-heimdall-child-mode.md`.

## Working Directory

```text
/Users/yoon/03_projects/04_my_vm_proxmox/02_Heimdall
```

## Must Read Docs

- `AGENTS.md`
- `product/docs/implementation/trusted-heimdall-child-mode.md`
- `product/docs/architecture/self-hosting-storage.md`
- `product/docs/operations/self-hosting-docker.md`
- `product/docs/implementation/docker-project-volume-support.md`
- `product/docs/config/project-yaml.md`

## Goal Summary

Implement the smallest operable nested Heimdall child deploy:

- outer Heimdall is still started manually by the operator
- outer UI exposes `Heimdall child로 실행`
- API/DB stores `run_as_heimdall_child`
- executor adds fixed child mounts/env to one single-service inner Heimdall API
  container

## Scope

### 1. Settings/config

- Add `HEIMDALL_CHILD_RUNNER_ENABLED`.
- Add `HEIMDALL_CHILD_ROOT_HOST`.
- Add `HEIMDALL_CHILD_ROOT_CONTAINER`.
- Add fail-closed validation for child-runner capability and configured roots.

### 2. API/DB/schema

- Add boolean `run_as_heimdall_child`, default `false`.
- Use an additive migration strategy.
- Ensure project create/read/update roundtrips the boolean.
- Reject host path fields, child root fields, privileged mount fields, Docker
  socket fields, and raw Docker option fields.

### 3. Project service/deploy validation

- Default projects to `run_as_heimdall_child=false`.
- Require child-runner env gate and roots before accepting
  `run_as_heimdall_child=true`.
- Reject multi-service child projects in this slice.

### 4. Executor

- Implement only the single-service child API mount/env contract.
- Use `child_id=project_id`.
- Create/check child directories through `HEIMDALL_CHILD_ROOT_CONTAINER`.
- Use `HEIMDALL_CHILD_ROOT_HOST` paths as Docker bind mount sources.
- Inject child env with Docker `--env` args.
- Do not create or pass a child env file.
- Keep normal deployment argv unchanged.

### 5. Web UI

- Add one checkbox labeled `Heimdall child로 실행`.
- Do not expose host path, child root, Docker socket, privileged, or raw Docker
  option inputs.

### 6. Docs

- Update status/runbook notes only as needed for the implemented slice.

## Non-scope

- Automatic outer lifecycle management.
- Inner Web automation.
- Multi-service child role handling.
- Project volume executor mounts into user previews.
- Arbitrary host paths or raw Docker options.
- `docker.sock` in normal user preview containers.
- Child env-file automation.

## Acceptance Criteria

- `run_as_heimdall_child` is represented in API, DB, service validation, and UI.
- Normal deploy behavior and Docker argv remain unchanged.
- Child deploys require `HEIMDALL_CHILD_RUNNER_ENABLED=true` and configured
  child roots.
- Child deploys reject multi-service projects in this slice.
- Child paths derive from `project_id`, not names, slugs, repo paths, or user
  input.
- The child API executor mounts only the required Docker socket, runtime root,
  and project-volume root.
- The child API receives required env through Docker `--env` args only.
- User requests cannot supply arbitrary host paths, raw Docker args, privileged
  options, or Docker socket access for normal previews.
- Documentation states what is implemented and what remains out of scope.

## Test Checklist

- Settings validation accepts a complete child-runner configuration.
- Settings validation rejects missing roots when the boolean is used.
- API schema accepts/defaults `run_as_heimdall_child`.
- API schema rejects forbidden child root, host path, Docker socket, privileged,
  and raw Docker fields.
- Project persistence roundtrips `run_as_heimdall_child`.
- Project validation defaults missing boolean to `false`.
- Project validation rejects child mode when server config is disabled.
- Project validation rejects child multi-service projects.
- Executor unit coverage verifies normal argv is unchanged.
- Executor unit coverage verifies child API Docker mounts and env.
- Executor coverage verifies no child env file is created.
- Web build succeeds with the new checkbox.

## Validation Commands

```sh
cd product/apps/api && venv/bin/python -m pytest
```

If `venv` is missing, use the project-standard Python test command.

```sh
cd product/apps/web && pnpm build
docker build -t heimdall-api:child-runner-check product/apps/api
```

Run the Docker build only if Docker is available.

## Safety Instructions

- Use `apply_patch` only for edits.
- Do not revert unrelated dirty changes.
- Follow `AGENTS.md` delegation order.
- Only worker edits code.

## Next Prompt To Paste

```text
/Users/yoon/03_projects/04_my_vm_proxmox/02_Heimdall 에서 작업해줘.
product/docs/implementation/trusted-heimdall-child-mode-handoff.md 를 먼저 읽고, 그 문서 기준으로 Nested Heimdall Child Deploy Minimum Slice를 구현해줘.
AGENTS.md 운영 방식대로 explorer/reviewer/docs_researcher 후 worker만 코드 편집해줘.
```
