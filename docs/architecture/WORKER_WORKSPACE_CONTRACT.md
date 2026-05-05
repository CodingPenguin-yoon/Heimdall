# Worker Workspace / Repo Execution Contract

Heimdall은 worker에게 raw shell을 열어 주는 도구가 아니다. 이 문서는 Set 2 기준으로 worker별 repo/workspace를 어떻게 할당하고, clone/fetch/reset/worktree 준비를 어떤 typed action으로 표현할지 정한다.

## Current inventory

현재 repo에는 아래 가정이 섞여 있다.

- `README.md`, `docs/README.md`: Heimdall이 worker / repo / test / build / PR / staging verification 실행 계층이라는 방향을 선언한다.
- `docs/architecture/AGENT_WORKER_REGISTRY.md`: Gjallar가 worker VM/bootstrap을 준비하고 Heimdall이 routing/health metadata만 registry에 저장하는 계약을 둔다. `checks.workspace_ready=true`는 workspace root가 준비됐다는 status label이다.
- `backend/app/domains/workers/*`: worker registry와 heartbeat/status self-report는 구현되어 있지만, repo checkout/fetch/reset 실행기는 아직 없다.
- `backend/app/shared/task_store.py`, `backend/app/shared/tasks.py`: 기존 task log 저장이 있으나 agent run artifact/log contract는 별도 Set에서 확장한다.
- `backend/app/integrations/terraform`, `backend/app/integrations/ansible`, `backend/app/domains/deploy`: legacy provisioning/deploy 흐름이며 Set 2 repo execution contract의 기준이 아니다.

## Scope boundary

Set 2는 execution contract를 고정한다. 실제 worker-side git execution adapter, agent command 실행, PR 생성은 후속 Set에서 다룬다.

금지:

- raw shell command string을 API/contract에 저장하거나 그대로 실행
- token/password/private key/auth file/credentialed URL 저장
- dirty worktree를 확인하지 않은 reset/overwrite
- artifact/log를 repo worktree 안에 저장
- Gjallar repo/docs/lock mutation

## Workspace root convention

Default root:

```text
/var/lib/heimdall/workers
```

Override env name:

```text
HEIMDALL_WORKER_WORKSPACE_ROOT
```

Worker-local layout:

```text
<workspace_root>/<worker_id>/
  repos/<repo_slug>/cache.git               # persistent repo cache/mirror
  worktrees/<task_id>/<repo_slug>/          # per-task working tree
  runs/<task_id>/logs/worker.log
  runs/<task_id>/logs/verification.log
  runs/<task_id>/artifacts/verification-report.json
```

Rules:

- `worker_id` and `task_id` are safe identifiers: letters, numbers, `.`, `_`, `:`, `-` only, but single `.` / `..` path segments are rejected.
- `repo_slug` is derived from `repo_url` or supplied explicitly, then normalized to a safe path segment.
- `workspace_root` must be an absolute POSIX path without `.`/`..` parts. Credentialed repo URLs are rejected across HTTP(S), SSH, and git+ssh forms.
- Logs/artifacts live under `runs/<task_id>` and must not be placed inside the repo worktree.

## Typed repo action schema

In-code schema version:

```text
heimdall.worker_repo_action.v1
```

Supported actions:

```text
clone              ensure persistent repo cache exists
fetch              fetch remote updates into existing cache
prepare_worktree   create/reuse per-task branch/worktree from target_ref
reset              reset an existing worktree to target_ref after clean-tree guard
status             read-only worktree status
```

Required common fields:

```text
action
worker_id
task_id
repo_url
```

Action-specific fields:

```text
target_ref         required for prepare_worktree/reset
checkout_branch    optional; default heimdall/<task_id>/<repo_slug>
default_branch     optional; default main
dirty_tree_policy  default fail_if_dirty, status uses read_only_status
workspace_root     optional absolute override
repo_slug          optional safe slug override
```

The contract output includes only typed steps, not shell commands. Example typed steps for `prepare_worktree`:

```text
repo.ensure_cache
repo.fetch
worktree.create_or_reuse_branch
worktree.require_clean_before_reuse
```

Example typed steps for `reset`:

```text
worktree.require_clean
repo.fetch
worktree.reset_to_ref
```

## Branch / worktree lifecycle

Default task branch:

```text
heimdall/<task_id>/<repo_slug>
```

Lifecycle:

1. Ensure repo cache exists for the non-credentialed repo URL.
2. Fetch remote refs into the cache.
3. Create or reuse a per-task worktree and branch under `worktrees/<task_id>/<repo_slug>`.
4. Before reusing or resetting a worktree, inspect dirty state.
5. If dirty/untracked changes exist, fail with a typed dirty-tree result and do not reset.
6. Store logs/artifacts outside the worktree under `runs/<task_id>`.
7. Release worker/task association through worker heartbeat/status after task completion or abandonment.

Git refs must be safe: no whitespace/control characters, no `..`, no `@{`, no leading/trailing `/`, no `.lock` suffix, no backslash.

## Dirty tree protection

Supported policy values:

```text
fail_if_dirty
read_only_status
```

Rules:

- `reset` always requires `fail_if_dirty`.
- `prepare_worktree` requires `fail_if_dirty` before reuse because it may create/reuse mutable worktrees.
- `status` defaults to `read_only_status` and must not mutate repo state.
- Dirty tree detection must run before any overwrite/reset action. If clean-tree evidence is unavailable, the action is blocked.

## Artifact / log convention

For task `task-123` on worker `codex-01` and repo `Heimdall`:

```text
/var/lib/heimdall/workers/codex-01/runs/task-123/logs/worker.log
/var/lib/heimdall/workers/codex-01/runs/task-123/logs/verification.log
/var/lib/heimdall/workers/codex-01/runs/task-123/artifacts/verification-report.json
```

No secret values should be written to logs/artifacts. Later Sets may define retention and report schemas, but Set 2 fixes the paths and “outside repo” rule.

## Code reference

- Contract builder: `backend/app/domains/workers/workspace_contract.py`
- Regression tests: `backend/tests/test_worker_workspace_contract.py`
