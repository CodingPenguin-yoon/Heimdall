# 최근 변경 설명

이 문서는 최근 DevOps 방향 전환과 주요 구현 커밋이 무엇을 바꿨는지 빠르게 설명한다.

## 방향 전환

이전 문서는 staging-first 또는 worker-first 흔적이 강했다. 현재 방향은 다음으로 고정한다.

- Heimdall은 사람이 쓰는 DevOps 운영 시스템이다.
- Gjallar는 VM 생성 및 Proxmox 운영 시스템이다.
- Hermes는 두 시스템을 대신 조작하고 요약하는 운영자다.
- worker/agent는 나중에 adapter/runner로 돌아올 수 있지만, 현재 MVP 정체성은 아니다.

## 최근에 해결하려던 이슈들

### 이슈 1. Heimdall과 Gjallar의 책임이 겹쳤다

예전 Heimdall 문서와 코드에는 GitLab staging deploy, Terraform/Ansible, `Create Instance`, staging host pool 같은 표현이 많았다. 이 상태로 계속 가면 Heimdall도 VM을 만들고 Gjallar도 VM을 만드는 모양이 되어, 장애가 났을 때 “어느 제품이 책임자인지”가 흐려진다.

고친 방향:

- VM 생성/삭제/Proxmox lifecycle은 Gjallar 책임으로 분리했다.
- Heimdall은 준비된 target을 `DeploymentTargetReference`로만 연결한다.
- repo-local legacy staging 문서는 `docs/archive/legacy-staging/` 아래로 옮겨 active guidance에서 제외했다.

### 이슈 2. Heimdall이 또 하나의 AI brain처럼 보일 위험이 있었다

worker registry, agent task queue, evidence contract는 유용한 작업이지만, 이것을 제품 정체성으로 앞세우면 Heimdall이 Hermes와 비슷한 “또 다른 agent brain”처럼 보일 수 있었다.

고친 방향:

- Hermes가 판단/계획/요약/승인 조율을 맡는다.
- Heimdall은 사람이 읽는 DevOps 운영 표면과 typed API를 맡는다.
- worker/agent lane은 `docs/archive/parked-worker-agent/`와 [../implementation/PARKED_WORKER_AGENT_LANE.md](../implementation/PARKED_WORKER_AGENT_LANE.md)에 parked 상태로 정리했다.

### 이슈 3. DevOps MVP를 설명할 active repo 문서가 부족했다

공유 문서에는 Service/Environment/CI/CD/DB/Target 모델이 정리되어 있었지만, repo-local docs에는 여전히 staging/worker 중심 문서가 active처럼 남아 있었다.

고친 방향:

- [CURRENT_IMPLEMENTATION.md](CURRENT_IMPLEMENTATION.md) — 현재 repo 구현 요약
- [../architecture/DEVOPS_MVP_ARCHITECTURE.md](../architecture/DEVOPS_MVP_ARCHITECTURE.md) — 현재 DevOps MVP 아키텍처
- [../implementation/BACKEND_DEVOPS_API.md](../implementation/BACKEND_DEVOPS_API.md) — backend 구현
- [../implementation/FRONTEND_DEVOPS_DASHBOARD.md](../implementation/FRONTEND_DEVOPS_DASHBOARD.md) — frontend 구현
- [../implementation/SAFE_SMOKE_FIXTURES.md](../implementation/SAFE_SMOKE_FIXTURES.md) — smoke fixture 구현
- [../implementation/VERIFICATION.md](../implementation/VERIFICATION.md) — 검증 기록

## `c310361` 설명

커밋: `c310361`

제목:

```text
feat(devops): add typed API and read-only dashboard
```

핵심 의미:

- repo 안에 DevOps MVP typed contract가 처음 고정됐다.
- backend는 `/api/devops/*` skeleton을 가졌다.
- frontend는 `/devops` read-only dashboard를 가졌다.

backend에서 들어온 것:

- `DevOpsCatalogService` in-memory catalog
- Pydantic schemas / enums
- parent 존재 검증
- cross-parent 검증
- credential-bearing URL 거부
- raw DB secret / raw secret assignment 거부
- CI action preview only
- VM lifecycle route 부재를 테스트로 고정

frontend에서 들어온 것:

- `/devops` route
- dashboard overview
- `Services`, `CI/CD`, `Database`, `Deployment targets` 패널
- loading / empty / partial-error state
- GET-only API client

이 커밋이 일부러 하지 않은 것:

- persistence
- migration
- provider-side deploy/retry execution
- mutation UI

## `65d6f82` 설명

커밋: `65d6f82`

제목:

```text
feat(devops): add opt-in smoke fixtures
```

핵심 의미:

- empty catalog 기본값은 유지했다.
- 대신 opt-in smoke fixture로 dashboard와 contract를 검증할 수 있게 했다.

들어온 것:

- `backend/app/domains/devops/fixtures.py`
- env var `HEIMDALL_DEVOPS_SMOKE_FIXTURES`
- fixture-aware catalog factory
- deterministic seed data

fixture 설계 이유:

- local smoke/demo/validation에만 쓰기 위해서다.
- production과 헷갈리지 않도록 `.invalid` 주소를 쓴다.
- secret 원문 대신 `vault/heimdall/devops-smoke/...` ref만 쓴다.
- provider-side action을 유도하지 않도록 `allowed_actions=[]`를 유지한다.

## parked worker/agent lane 설명

repo에는 worker/agent task queue/evidence 관련 dirty work가 남아 있다. 이것은 현재 MVP의 active lane이 아니다.

무엇을 하던 작업이었는가:

- task lifecycle
- worker assignment
- workspace action metadata
- event / artifact / verification report metadata

왜 parked인가:

- 현재 우선순위는 사람이 직접 보는 DevOps 운영 표면이다.
- CI/CD, DB, deployment target, logs/verification, runbook을 먼저 solid하게 만들어야 한다.
- 그 다음에 worker/agent는 adapter 또는 runner로 다시 붙이는 편이 경계가 명확하다.
