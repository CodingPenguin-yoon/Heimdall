> 보관 문서 안내: 이 문서는 parked worker/agent lane의 역사 기록이다. 현재 active Heimdall MVP 가이드는 아니며, 나중에 adapter/runner 검토 시 배경 자료로만 사용한다.

# Agent Worker Registry — historical / parked reference

> This document is preserved as historical implementation context only. It is not the active Heimdall MVP direction.

Current product direction:

```text
Heimdall = 사람이 CI/CD·DB·배포환경을 관리하는 DevOps 운영 시스템
Gjallar = VM 생성 및 Proxmox 운영 시스템
Hermes = 두 제품을 대신 컨트롤할 수 있는 운영자
```

The worker registry work may be revisited later as a DevOps automation adapter, after the human-facing DevOps MVP exists.
Do not use this document to start a worker-first implementation Set.

## Historical purpose

The old worker registry contract listed Codex/Claude/OpenCode workers and their status metadata.
Heimdall did not store remote authentication files or OAuth token contents.

## Historical worker fields

```text
worker_id           stable logical ID, 예: codex-01
display_name        선택적 표시 이름
hostname / host_ip  접속 대상
ssh_user            선택적 SSH 사용자
agent_types         codex / claude / opencode
agent_auth_status   authenticated / expired / needs_login / unknown / not_applicable
status              unknown / ready / busy / offline / error
labels              비민감 routing metadata
current_task_id     현재 실행 중인 task ID
last_checked_at     마지막 상태 확인 시각(UTC ISO timestamp)
is_stale            파생 health flag
```

## Current interpretation

- This is not a 1차 MVP product surface.
- If reused later, translate worker concepts into normal DevOps language such as runner, job, run history, verification report, and deployment automation.
- VM lifecycle still belongs to Gjallar.
- Credential/token/private key/API key/connection string raw values must never be stored in Heimdall docs, DB metadata, or logs.

## Do not resume directly

Before reusing this contract, first complete/define:

1. Service / project / environment catalog
2. CI/CD pipeline status and run history
3. DB connection, migration, and backup readiness status
4. Deployment / release / rollback / runbook flows
5. Gjallar VM target reference boundary

Only then decide whether a runner/automation adapter is useful.
