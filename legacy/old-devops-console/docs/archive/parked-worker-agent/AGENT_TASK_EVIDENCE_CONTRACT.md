> 보관 문서 안내: 이 문서는 parked worker/agent lane의 역사 기록이다. 현재 active Heimdall MVP 가이드는 아니며, 나중에 adapter/runner 검토 시 배경 자료로만 사용한다.

# Agent Task Evidence Contract

Heimdall Set 4 adds the evidence layer that lets Hermes review what happened during an agent task without giving Heimdall a raw command runner.

The evidence contract stores typed metadata only:

- task events / log lines,
- artifact metadata and paths,
- verification report summaries and check outcomes.

It does not execute shell, git, agent CLI, VM, PR, or staging commands. It also does not store API keys, tokens, passwords, SSH/private keys, auth files, credentialed URLs, or raw secret-bearing logs.

## API surface

All endpoints inherit the existing worker registry fail-closed guard:

```text
HEIMDALL_WORKER_REGISTRY_API_KEY
X-Heimdall-Worker-Registry-Key
```

```text
GET  /api/agent-tasks/{task_id}/events
POST /api/agent-tasks/{task_id}/events
GET  /api/agent-tasks/{task_id}/artifacts
POST /api/agent-tasks/{task_id}/artifacts
GET  /api/agent-tasks/{task_id}/verification-reports
POST /api/agent-tasks/{task_id}/verification-reports
```

These endpoints are control-plane surfaces for worker/Hermes self-reporting. They are not public endpoints.

## Task events

Task events are append-only typed log/event rows linked to `agent_tasks`.

Example payload:

```json
{
  "event_type": "worker.started",
  "severity": "info",
  "source": "worker",
  "message": "Worker accepted typed task intent",
  "metadata": {
    "phase": "checkout"
  }
}
```

Response schema version:

```text
heimdall.agent_task_event.v1
```

Rules:

- `sequence` is monotonic per task.
- `severity` is one of `debug`, `info`, `warning`, `error`.
- `message` and metadata are sanitized for sensitive markers and common credential-value shapes (credentialed URLs, private-key material, bearer/JWT/provider-style tokens, bare long alphanumeric keys, symbol-wrapped token-like values, and high-entropy token-like values).
- raw execution keys such as `command`, `cmd`, `exec`, `script`, `shell`, `runCommand`, and compact aliases are rejected.
- raw command-shaped text values are rejected; `command_label` must be a human-readable check label, not an executable invocation. `command_label` also uses a stricter human-label guard that rejects path separators, shell metacharacters, leading executable names, option-like tokens, and script file tokens.

## Artifact metadata

Artifacts are registered as metadata under the Set 2 worker run layout. Heimdall stores the path contract, not file bytes.

A task must already have an assigned `workspace_action_contract` because artifact paths are derived from the assigned worker layout.

For task `task-123` on worker `codex-01`:

```text
/var/lib/heimdall/workers/codex-01/runs/task-123/artifacts/<relative_path>
```

Example payload:

```json
{
  "artifact_id": "verification-report-json",
  "artifact_type": "verification_report",
  "relative_path": "verification-report.json",
  "media_type": "application/json",
  "size_bytes": 321,
  "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "metadata": {
    "producer": "worker-verifier"
  }
}
```

Response schema version:

```text
heimdall.agent_task_artifact.v1
```

Rules:

- `artifact_id` is scoped by `task_id`; workers may reuse stable IDs such as `verification-report-json` across different tasks.
- `relative_path` must be relative and must not contain empty, dot, or dot-dot path parts.
- `layout.artifacts_path` must equal `layout.run_root/artifacts` from the assigned worker workspace contract.
- generated artifact path must stay under `layout.artifacts_path`.
- generated artifact path must not be inside `layout.worktree_path`.
- artifact bytes remain in the worker run root; Heimdall persists metadata only.

Retention policy in responses:

```json
{
  "scope": "task_run_evidence",
  "storage": "worker_run_root",
  "artifacts_inside_repo": false,
  "secrets_allowed": false,
  "delete_requires_operator_policy": true
}
```

## Verification reports

Verification reports summarize test/build/lint/static-scan outcomes for Hermes review.

Example payload:

```json
{
  "report_id": "verification-report-001",
  "status": "pass",
  "summary": "Selected backend checks passed",
  "checks": [
    {
      "name": "backend-selected-unittest",
      "status": "pass",
      "command_label": "backend selected unittest",
      "artifact_id": "verification-report-json",
      "summary": "focused worker/task/evidence checks passed"
    }
  ],
  "metadata": {
    "review_gate": "ready"
  }
}
```

Response schema version:

```text
heimdall.agent_task_verification_report.v1
```

Rules:

- `report_id` is scoped by `task_id`; workers may reuse stable IDs such as `verification-report-001` across different tasks.
- report `status` is `pass`, `fail`, or `blocked`.
- check `status` is `pass`, `fail`, `warning`, `skipped`, or `blocked`.
- `command_label` is a human label only; raw command strings are not accepted.
- referenced `artifact_id` values must exist for the same task.
- `review_handoff.ready_for_hermes_review` means Hermes can inspect the summary and artifact references; it is not an automatic merge/commit/PR approval.

## Safety boundary

The evidence service rejects:

- raw execution fields at any nested payload level,
- sensitive field names and sensitive text values,
- path traversal in artifact `relative_path`,
- artifact registration before worker assignment creates a workspace contract,
- artifact references that do not belong to the same task.

Evidence storage does not alter worker lifecycle state. Task status transitions still go through the Set 3 task queue lifecycle API.

## Files

```text
backend/app/domains/workers/task_evidence.py
backend/app/domains/workers/router.py
backend/app/shared/platform_models.py
backend/alembic/versions/20260505_0013_agent_task_evidence.py
backend/tests/test_agent_task_evidence_contract.py
```

## Verification

Focused Set 4 contract check:

```bash
cd backend
. venv/bin/activate
python -m unittest tests.test_agent_task_evidence_contract -v
```

Selected backend regression check:

```bash
python -m unittest \
  tests.test_agent_worker_registry \
  tests.test_create_instance_boundary \
  tests.test_worker_workspace_contract \
  tests.test_agent_task_queue_contract \
  tests.test_agent_task_evidence_contract -v
```

Migration/compile check:

```bash
python -m compileall app tests/test_agent_task_queue_contract.py tests/test_agent_task_evidence_contract.py
alembic upgrade head
alembic current
```
