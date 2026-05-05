# Agent Worker Registry

Heimdall은 자체 LLM 두뇌가 아니라 Hermes가 조종하는 Agentic DevOps Execution Plane이다.
이 문서는 Heimdall이 관리하는 worker registry의 1차 계약이다.

## 목적

worker registry는 Codex/Claude/OpenCode 작업자를 안전하게 목록화한다.
Heimdall은 worker의 원격 인증 파일이나 OAuth token 원문을 저장하지 않는다.

## Worker 필드

```text
worker_id           stable logical ID, 예: codex-01
display_name        선택적 표시 이름
hostname / host_ip  접속 대상
ssh_user            선택적 SSH 사용자
agent_types         codex / claude / opencode
agent_auth_status   authenticated / expired / needs_login / unknown / not_applicable
status              unknown / ready / busy / offline / error
labels              비민감 routing metadata
current_task_id     현재 실행 중인 agent task ID
last_checked_at     마지막 상태 확인 시각(UTC ISO timestamp)
is_stale            파생 health flag, last_checked_at 기준 300초 초과/파싱 실패 시 true
```

## Gjallar provisioning output → Heimdall registry input draft

Set 1 기준에서 Gjallar는 VM/host provisioning owner이고 Heimdall은 생성된 worker/host를 registry에 등록해 task execution plane으로 소비한다. 따라서 Gjallar가 Heimdall에 넘기는 값은 **routing/health metadata**여야 하며, token·password·private key·auth file 원문은 포함하지 않는다.

### Gjallar worker provisioning output v1

Gjallar가 worker VM/bootstrap을 완료했거나 완료 상태를 보고할 때 Heimdall이 기대하는 초안 schema:

```json
{
  "schema_version": "gjallar.worker_provisioning_result.v1",
  "provisioning_id": "gjallar-provisioning-20260504-001",
  "owner_project": "Gjallar",
  "worker_id": "codex-01",
  "display_name": "Codex Worker 01",
  "hostname": "codex-worker-01.local",
  "host_ip": "<worker-management-ip>",
  "ssh_user": "yoon",
  "agent_types": ["codex"],
  "agent_auth_status": {"codex": "authenticated"},
  "bootstrap_status": "completed",
  "observed_at": "2026-05-04T12:30:00Z",
  "labels": {
    "pool": "dev",
    "provisioning_owner": "Gjallar",
    "provisioning_id": "gjallar-provisioning-20260504-001",
    "node": "pve-node-a",
    "capability": "repo-test-build"
  },
  "checks": {
    "ssh_reachable": true,
    "codex_cli_available": true,
    "workspace_ready": true
  }
}
```

Required fields for Heimdall registration:

```text
schema_version       must be gjallar.worker_provisioning_result.v1
owner_project        must be Gjallar
worker_id            stable logical ID chosen before/at provisioning time
hostname             management hostname or DNS name for the worker
agent_types          one or more of codex / claude / opencode
bootstrap_status     completed / pending / failed / unreachable
```

Optional fields:

```text
display_name         human-readable worker name
host_ip              management IP or address string; never credential-bearing
ssh_user             login username only, never password/key material
agent_auth_status    per-agent auth state: authenticated / expired / needs_login / unknown / not_applicable
observed_at          Gjallar observation timestamp, UTC ISO preferred; if absent Heimdall registration time is used
labels               non-sensitive routing metadata allowlist
checks               non-sensitive bootstrap evidence booleans
```

### Field mapping into Heimdall register_worker

| Gjallar output field | Heimdall registry field | Rule |
| --- | --- | --- |
| `worker_id` | `worker_id` | Required. Must pass Heimdall safe identifier validation and must not contain sensitive markers. |
| `display_name` | `display_name` | Optional display-only value; rejected if it includes sensitive markers. |
| `hostname` | `hostname` | Required routing target. No credentials or connection strings. |
| `host_ip` | `host_ip` | Optional management address string. No credential-bearing URI. |
| `ssh_user` | `ssh_user` | Optional username only. SSH password/key material is never accepted. |
| `agent_types` | `agent_types` | Normalize/dedupe to supported agent types: `codex`, `claude`, `opencode`. |
| `agent_auth_status` | `agent_auth_status` | Keep status labels only. Do not store OAuth/device auth token contents or auth files. Missing agent types default to `unknown`. |
| `bootstrap_status` + `checks` | `status` | `completed` with reachable/ready checks → `ready`; `pending` → `unknown`; `unreachable` → `offline`; `failed` → `error`. |
| `labels` + safe Gjallar metadata | `labels` | Allow non-sensitive routing metadata such as `pool`, `provisioning_owner`, `provisioning_id`, `node`, `capability`. Drop/reject secret-like keys or string values. |
| `observed_at` | `last_checked_at` | Normalize to UTC ISO. If absent, Heimdall registration time is used. |
| _none at registration_ | `current_task_id` | Register new worker with `null` unless Hermes is explicitly assigning an active task. |

### Bootstrap / auth / heartbeat sequence

Canonical Set 1 handoff sequence:

```text
1. Hermes detects that worker capacity is missing or stale.
2. Hermes asks Gjallar, not Heimdall, for worker VM/host provisioning plan and risk review.
3. After approval, Gjallar creates/bootstrap the VM/host and checks non-sensitive readiness signals:
   - management hostname/address is reachable
   - requested agent CLI is installed/available
   - workspace root is prepared
   - agent auth state is observed as status-only metadata
4. Gjallar emits `gjallar.worker_provisioning_result.v1` with routing/health metadata only.
5. Heimdall validates `schema_version`, `owner_project=Gjallar`, safe identifiers, supported agent types, bootstrap status, and secret-like top-level fields.
6. Heimdall maps the result with `AgentWorkerRegistryService.build_registration_payload_from_gjallar_result(...)` and calls the same `register_worker` validation path used by `POST /api/workers/register`.
7. Registered workers start with `current_task_id=null`; Hermes assigns tasks only after worker status/auth are usable for the requested agent type.
8. Worker/Hermes status probes call `POST /api/workers/{worker_id}/heartbeat` with status-only `agent_auth_status`, optional `current_task_id`, and `observed_at`.
9. When a task finishes or is abandoned, heartbeat/status update sends `current_task_id: null` to release the worker-task association.
10. Heimdall reports `is_stale=true` when `last_checked_at` is older than the threshold or unparsable; stale is a re-check signal, not permission for Heimdall to mutate VM lifecycle.
```

Status mapping from Gjallar bootstrap to Heimdall registry:

| Gjallar `bootstrap_status` + checks | Heimdall `status` | Meaning |
| --- | --- | --- |
| `completed` + `ssh_reachable=true` + `workspace_ready=true` + requested agent CLI checks true | `ready` | Worker can be considered for scheduling. |
| `completed` but required readiness checks are missing/false | `unknown` | Provisioning completed, but Hermes/Gjallar should re-check before scheduling. |
| `pending` | `unknown` | Handoff is not ready yet. |
| `unreachable` | `offline` | Heimdall records status but does not repair or recreate the host. |
| `failed` | `error` | Heimdall records status; remediation remains with Hermes/Gjallar/user decision. |

Scheduling guardrails:

- Heimdall does not run shell commands on workers just because a worker is stale or unavailable.
- Heimdall does not create/delete/resize Proxmox resources when capacity is short.
- Agent auth status is represented as labels such as `authenticated`, `expired`, `needs_login`, `unknown`, or `not_applicable`; raw auth files, tokens, key material, and credentialed URLs stay outside the contract.
- Contract drift must be reviewed by comparing Gjallar's provisioning result schema and Heimdall's mapper/registry tests before Set completion.
- `workspace_ready=true` only means the worker-local root is prepared. Repo clone/fetch/reset/worktree execution follows the separate [Worker Workspace / Repo Execution Contract](WORKER_WORKSPACE_CONTRACT.md).

### Explicit non-contract data

The following must not cross into Heimdall registry payloads:

```text
raw Codex/Claude/OpenCode OAuth token contents
refresh tokens / API keys / passwords / bearer values
SSH private keys or public/private key file contents
credentialed URLs or connection strings
Gjallar Terraform state internals or Proxmox credentials
full auth/config file contents from worker home directories
```

If Gjallar needs to retain sensitive provisioning evidence, it should keep that evidence inside Gjallar-owned storage and only send Heimdall a non-sensitive status/metadata result.

## 민감정보 원칙

저장 금지:

```text
access token
refresh token
API key
password
secret
credential
authorization / bearer 값
private key / SSH key
auth_file contents
~/.codex 내부 파일 원문
```

Heimdall은 인증 상태만 저장한다.
Codex OAuth/device-auth는 worker VM 내부 공식 인증 상태로 유지한다.
`labels`는 routing metadata만 저장한다. token/secret/password/credential/API key/authorization/bearer/private key/SSH key/auth file 계열 key는 저장하지 않으며, 같은 marker가 포함된 label string value는 요청을 거부한다.
`worker_id`, `display_name`, `hostname`, `host_ip`, `ssh_user`, `current_task_id`, `last_checked_at`, heartbeat `observed_at`에도 같은 marker가 포함되면 저장하지 않고 `AgentWorkerRegistryError`/400으로 거부한다. `worker_id`는 API path/response/error에 노출되는 primary key이므로 영문/숫자/`.`/`_`/`:`/`-`만 허용한다.

## API 1차 계약

worker registry API는 fail-closed guard를 둔다.
`HEIMDALL_WORKER_REGISTRY_API_KEY`가 설정되지 않으면 `/api/workers*` 요청은 503으로 실패한다.
호출자는 `X-Heimdall-Worker-Registry-Key` header로 동일한 값을 전달해야 한다.

```text
GET   /api/workers
POST  /api/workers/register
GET   /api/workers/{worker_id}
PATCH /api/workers/{worker_id}/status
POST  /api/workers/{worker_id}/heartbeat
```

PATCH는 명시적 `null`을 허용한다. 예: `current_task_id: null`은 worker를 task에서 분리한다.

### Heartbeat

`POST /api/workers/{worker_id}/heartbeat`는 worker health probe/status heartbeat이다.
요청 body:

```json
{
  "status": "ready",
  "agent_auth_status": {"codex": "authenticated"},
  "current_task_id": null,
  "observed_at": "2026-05-04T12:30:00+09:00"
}
```

- 모든 필드는 선택적이다.
- `observed_at`이 있으면 ISO timestamp여야 하며 UTC ISO로 정규화해 `last_checked_at`에 저장한다.
- `observed_at`이 없거나 `null`이면 서버 UTC now를 `last_checked_at`에 저장한다.
- `current_task_id: null`은 현재 task 연결을 명시적으로 해제한다.
- worker가 없으면 404(`worker not found: ...`), invalid timestamp/unsupported status/auth/sensitive marker는 400이다.
- 응답에는 `is_stale`이 포함된다. 기본 threshold는 300초이며, `last_checked_at`이 threshold보다 오래됐거나 파싱 불가능하면 `true`이다.

## Agent task lifecycle 1차 계약

```text
queued -> running -> needs_review -> succeeded
queued -> running -> failed
queued -> running -> cancelled
needs_review -> running
needs_review -> failed/succeeded/cancelled
```

terminal state:

```text
succeeded
failed
cancelled
```

terminal state에서는 다시 running으로 되돌리지 않는다.
