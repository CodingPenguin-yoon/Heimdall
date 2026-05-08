> 보관 문서 안내: 이 문서는 parked worker/agent lane의 역사 기록이다. 현재 active Heimdall MVP 가이드는 아니며, 나중에 adapter/runner 검토 시 배경 자료로만 사용한다.

# Agent Task Queue MVP

Heimdall Set 3 adds the first backend contract for Hermes-owned agent tasks.
The queue is intentionally a control-plane contract only: it persists task intent,
worker assignment, lifecycle state, and typed workspace/repo metadata. It does not
execute shell, git, agent CLI, VM, or PR commands.

## Scope

The MVP covers:

- `agent_tasks` database table and SQLAlchemy model.
- Worker-protected API endpoints under the existing workers router.
- Task lifecycle state transitions:
  - `queued -> running -> needs_review -> succeeded`
  - `running -> failed`
  - `queued/running/needs_review -> cancelled`
- Deterministic allocation to a ready, authenticated, non-stale, idle worker that
  supports the requested agent type and required capabilities.
- Workspace action metadata built from the Set 2 workspace contract.
- Fail-closed rejection of raw execution fields and sensitive metadata.

Out of scope:

- Running arbitrary commands.
- Running Codex/Claude/OpenCode CLI directly.
- Direct VM/Proxmox provisioning.
- Commit/push/PR automation.
- Storing API keys, tokens, passwords, private keys, auth files, or credentialed
  repo URLs.

## API surface

All endpoints are mounted on the existing workers router and inherit the same
fail-closed `HEIMDALL_WORKER_REGISTRY_API_KEY` dependency.

```text
GET    /api/agent-tasks?status=queued
POST   /api/agent-tasks
GET    /api/agent-tasks/{task_id}
POST   /api/agent-tasks/{task_id}/assign
PATCH  /api/agent-tasks/{task_id}/status
```

### Create task

`POST /api/agent-tasks` accepts typed metadata only:

```json
{
  "task_id": "task-queue-001",
  "title": "Run focused backend tests",
  "agent_type": "codex",
  "repo_url": "git@github.com:CodingPenguin-yoon/Heimdall.git",
  "target_ref": "main",
  "required_capabilities": ["repo-test-build"],
  "workspace_action": "prepare_worktree",
  "dirty_tree_policy": "fail_if_dirty",
  "labels": {
    "project": "Heimdall"
  }
}
```

New tasks must start as `queued`. The service validates the workspace action
request by calling `WorkerWorkspaceContractService.build_repo_action_contract()`
with a safe placeholder worker ID before persisting the task.

### Assign task

`POST /api/agent-tasks/{task_id}/assign` tries to move the task to `running`.
It selects the first worker ordered by `worker_id` that satisfies all of these:

- worker has the requested `agent_type`,
- `status == ready`,
- no `current_task_id`,
- auth status for the requested agent type is `authenticated`,
- worker heartbeat is not stale,
- worker labels include all requested capabilities when capabilities are set.

If no worker matches, the task remains `queued` with allocation status
`no_ready_authenticated_worker`.

When a worker is assigned, Heimdall stores a typed `workspace_action_contract`
that includes the explicit `worker_id` and `task_id`, and marks the worker
`busy` with `current_task_id` set to the task.

### Transition task

`PATCH /api/agent-tasks/{task_id}/status` accepts:

```json
{
  "status": "needs_review",
  "reason": "diff ready for Hermes review"
}
```

Lifecycle guard rules come from `app.domains.workers.lifecycle`:

```text
queued       -> running, cancelled
running      -> needs_review, failed, succeeded, cancelled
needs_review -> running, failed, succeeded, cancelled
failed       -> terminal
succeeded    -> terminal
cancelled    -> terminal
```

Transitions to `needs_review`, `failed`, `succeeded`, or `cancelled` release the
assigned worker. Release only marks the worker ready when the worker is still
pointing at the same task, so an older task cannot accidentally release a worker
that has already been reassigned. Terminal tasks cannot restart.

## Safety boundary

The task queue rejects:

- raw execution field names such as `command`, `cmd`, `exec`, `script`, `shell`,
  `subprocess`, `runCommand`, `shell_script`, and compact aliases like
  `runcommand` or `shellscript`,
- sensitive top-level or label keys,
- sensitive text values in queue labels,
- credential-bearing repo URLs through the Set 2 workspace contract validator.

The queue stores routing metadata and auth status labels only. It never stores
credential values.

## Files

```text
backend/app/domains/workers/task_queue.py
backend/app/domains/workers/router.py
backend/app/shared/platform_models.py
backend/alembic/versions/20260505_0012_agent_task_queue.py
backend/tests/test_agent_task_queue_contract.py
```

## Verification

The Set 3 implementation was verified with:

```bash
git diff --check
cd backend && . venv/bin/activate && python -m unittest \
  tests.test_agent_worker_registry \
  tests.test_create_instance_boundary \
  tests.test_worker_workspace_contract \
  tests.test_agent_task_queue_contract -v
cd backend && . venv/bin/activate && python -m compileall app tests/test_agent_task_queue_contract.py
cd backend && . venv/bin/activate && alembic upgrade head && alembic current
cd frontend && pnpm build
```

Independent review found and the implementation fixed raw-execution metadata
bypass cases and a worker release edge case where an old review task could have
released a reassigned worker. Remaining hardening for a future Set: concurrent
assignment protection with row-level locking or compare-and-set semantics.
