# Parked Worker / Agent Lane

## 상태

이 lane은 제품 정체성/UX 기준으로 historical/parked다. 현재 Heimdall MVP의 주 구현 방향은 human-facing DevOps 운영 화면이다.

단, 아래 backend worker registry / task queue / evidence route와 migration은 이미 검증된 내부 API surface로 repo에 남아 있으며 `/api/workers/*` guard 아래 mounted 상태다. 이 surface는 primary UX가 아니고, 향후 runner/automation adapter로 재해석하기 전까지 fail-closed auth, secret/raw-execution 차단, audit metadata 계약을 유지해야 한다.

## 무엇이 남아 있는가

repo에는 worker/agent 관련 내부 API surface와 historical 문서가 함께 남아 있다.

대표 파일 범위:

- `backend/alembic/versions/20260505_0012_agent_task_queue.py`
- `backend/alembic/versions/20260505_0013_agent_task_evidence.py`
- `backend/app/domains/workers/task_queue.py`
- `backend/app/domains/workers/task_evidence.py`
- 관련 backend tests
- [../archive/parked-worker-agent/AGENT_TASK_QUEUE_MVP.md](../archive/parked-worker-agent/AGENT_TASK_QUEUE_MVP.md)
- [../archive/parked-worker-agent/AGENT_TASK_EVIDENCE_CONTRACT.md](../archive/parked-worker-agent/AGENT_TASK_EVIDENCE_CONTRACT.md)

## 이 작업이 하려던 것

### task queue

- task lifecycle
- worker assignment
- agent type/capability 기준 선택
- typed workspace action metadata

### evidence layer

- task events
- artifact metadata
- verification report metadata
- workspace action 결과를 사람이 검토할 수 있는 기록

## 왜 parked인가

현재 우선순위는 worker-first가 아니라 human-facing DevOps MVP다.

먼저 solid해야 하는 것:

- service catalog
- environment view
- CI/CD history
- DB health / migration / backup readiness
- deployment target reference
- logs / verification / runbook

이 기반이 먼저 고정되어야 나중에 worker/agent를 adapter 또는 runner로 붙여도 product boundary가 흐려지지 않는다.

## 나중에 돌아올 때의 해석

worker/agent가 다시 들어오더라도 현재 MVP 정체성을 대체하지 않는다.

권장 해석:

- worker -> runner / automation adapter
- task queue -> approval 이후 실행 orchestration 보조 계층
- evidence -> verification/report/audit metadata 계층

유지할 원칙:

- VM lifecycle ownership은 Gjallar
- DevOps 운영 모델 ownership은 Heimdall
- secret 원문 저장 금지
- raw shell/provider execution은 명시적 approval/audit 모델 없이 넣지 않음
