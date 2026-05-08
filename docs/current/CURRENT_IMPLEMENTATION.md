# 현재 구현 상태

이 문서는 2026-05-08 기준 repo 안에 실제로 들어와 있는 Heimdall DevOps MVP 구현을 설명한다.

## 한 줄 요약

Heimdall은 지금 사람 운영자가 보는 DevOps 운영 시스템 방향으로 정렬되어 있다. 현재 구현은 typed backend contract와 read-only dashboard를 중심으로 하며, VM 생성이나 provider-side 실행기는 포함하지 않는다.

## 현재 들어와 있는 핵심 모델

shared-docs 설계와 현재 backend skeleton이 같이 고정하려는 중심 모델은 다음이다.

- `Service`
- `ServiceEnvironment`
- `DeploymentTargetReference`
- `DatabaseStatus`
- `CiCdRun`

이 모델이 표현하는 운영 범위:

- service catalog
- `dev` / `staging` / `prod` 환경
- CI/CD 이력과 상태
- DB health / migration / backup / restore readiness
- deployment target reference
- verification/report/runbook link

중요한 보안 규칙:

- DB나 외부 연동의 비밀값은 raw credential로 저장하지 않는다.
- `secret_ref`만 저장한다.
- credential-bearing URL, query token, raw DB secret assignment는 계약 단계에서 거부한다.

## backend 구현 상태

구현 위치:

- `backend/app/domains/devops/schemas.py`
- `backend/app/domains/devops/service.py`
- `backend/app/domains/devops/router.py`
- `backend/app/domains/devops/fixtures.py`
- `backend/app/main.py`

현재 구현된 endpoint:

```text
GET  /api/devops/services
POST /api/devops/services
GET  /api/devops/services/{service_id}/summary
GET  /api/devops/environments
POST /api/devops/services/{service_id}/environments
GET  /api/devops/deployment-targets
POST /api/devops/environments/{environment_id}/deployment-targets
GET  /api/devops/ci-runs
POST /api/devops/ci-runs
POST /api/devops/ci-runs/{run_id}/actions/{action}:preview
GET  /api/devops/db-status
POST /api/devops/environments/{environment_id}/db-status
POST /api/devops/db-status/{db_status_id}/checks:record
GET  /api/devops/dashboard
```

현재 성격:

- persistence 없음
- migration 없음
- in-memory catalog only
- auth 없음
- provider-side deploy/retry 실행 없음
- action endpoint는 preview only

문서 해석 시 주의:

- frontend만 read-only다.
- backend API 전체가 GET-only라고 쓰면 틀리다.
- POST route는 현재도 존재하지만, durable control plane이나 provider executor가 아니라 skeleton contract 수준이다.

## frontend 구현 상태

구현 위치:

- `frontend/src/App.jsx`
- `frontend/src/components/DevOpsDashboard.jsx`
- `frontend/src/services/devopsApi.js`
- `frontend/src/utils/devopsDashboard.js`

현재 사용자 표면:

- `/devops` route
- read-only dashboard
- panel: `Services`, `CI/CD`, `Database`, `Deployment targets`
- empty/loading/partial-error/summary state
- `getServiceSummary` helper
- mounted/unmount guard

frontend API client 특징:

- `baseURL`은 `/api`
- GET method만 노출
- `/api/devops/*` 중 dashboard/list/summary 조회만 사용

## smoke fixture 구현 상태

`HEIMDALL_DEVOPS_SMOKE_FIXTURES`가 truthy일 때만 in-memory 초기 fixture가 들어간다.

truthy 값:

```text
1
true
yes
on
smoke
```

기본값:

- 비어 있는 catalog

fixture 안전 규칙:

- `.invalid` host / URL 사용
- `vault/heimdall/devops-smoke/...` 형태의 `secret_ref` 사용
- `allowed_actions=[]`
- mutation endpoint 없음
- production 데이터처럼 보이지 않도록 inert data만 사용

## 구현되지 않은 것

- `/api/devops` 아래 VM lifecycle route
- Proxmox 직접 운영 기능
- provider-side CI/CD 재실행
- deploy / retry / rollback 실제 실행
- catalog mutation UI
- persistence-backed history
- worker/agent runner 중심 운영 플로우
