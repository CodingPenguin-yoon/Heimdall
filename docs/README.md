# Heimdall 문서 인덱스

이 디렉터리는 repo 안에서 현재 구현을 이해하기 위한 **code-local 문서 세트**다. 프로젝트 전체의 장기 source of truth는 `/mnt/hermes_data/프로젝트/헤임달`에 두고, 여기서는 repo에 실제로 들어온 구현·경계·검증을 최신 상태로 설명한다. Active 문서는 현재 제품 방향과 이미 들어온 구현을 설명하고, `docs/archive/` 아래 문서는 역사 기록만 담당한다.

## 현재 제품 방향

```text
Heimdall = 사람이 쓰는 DevOps 운영 시스템
Gjallar = VM 생성 및 Proxmox 운영 시스템
Hermes = Heimdall/Gjallar를 대신 조작하고 요약하는 운영자
```

현재 MVP의 중심 범위:

- CI/CD 상태와 이력
- Service catalog
- `dev` / `staging` / `prod` 환경
- Database health / migration / backup readiness
- Deployment target reference
- 검증 리포트, 로그, runbook

현재 MVP의 비범위:

- VM 생성 및 Proxmox lifecycle 운영
- provider-side deploy/retry 실행
- raw shell 실행
- secret 원문 저장
- worker/agent를 제품 정체성으로 전면 배치하는 것

## 먼저 읽을 문서

- [current/CURRENT_IMPLEMENTATION.md](current/CURRENT_IMPLEMENTATION.md)
- [current/RECENT_CHANGES_EXPLAINED.md](current/RECENT_CHANGES_EXPLAINED.md)
- [architecture/DEVOPS_MVP_ARCHITECTURE.md](architecture/DEVOPS_MVP_ARCHITECTURE.md)
- [architecture/GJALLAR_HEIMDALL_BOUNDARY.md](architecture/GJALLAR_HEIMDALL_BOUNDARY.md)
- [implementation/BACKEND_DEVOPS_API.md](implementation/BACKEND_DEVOPS_API.md)
- [implementation/FRONTEND_DEVOPS_DASHBOARD.md](implementation/FRONTEND_DEVOPS_DASHBOARD.md)
- [implementation/SAFE_SMOKE_FIXTURES.md](implementation/SAFE_SMOKE_FIXTURES.md)
- [implementation/PARKED_WORKER_AGENT_LANE.md](implementation/PARKED_WORKER_AGENT_LANE.md)
- [implementation/VERIFICATION.md](implementation/VERIFICATION.md)

## 구현 상태

이미 구현됨:

- `backend/app/domains/devops/{schemas.py,service.py,router.py}` 기반 typed DevOps API skeleton
- `backend/app/main.py`에 `/api/devops/*` 라우터 마운트
- in-memory `DevOpsCatalogService`
- service/environment/deployment target/CI run/DB status/dashboard read model
- `HEIMDALL_DEVOPS_SMOKE_FIXTURES` 기반 opt-in smoke fixture seed
- `/devops` read-only dashboard와 GET 전용 frontend API client

아직 구현되지 않음:

- DevOps catalog persistence
- migration / durable storage
- provider-side deploy / retry / rollback execution
- VM lifecycle API under `/api/devops`
- raw credential 저장
- worker/agent runner를 현재 MVP의 주 실행 모델로 사용하는 것

중요한 nuance:

- frontend는 read-only다.
- 하지만 backend DevOps skeleton 전체가 GET-only는 아니다.
- 현재 backend에는 auth 없는 in-memory POST route가 있으며, 이는 계약 검증과 API 형태 고정을 위한 skeleton이다.

## 아카이브

아래 문서는 active guidance가 아니다. 새 설계나 구현의 기준으로 사용하지 말고, 이전 결정과 전환 이유를 확인할 때만 읽는다.

- [archive/legacy-staging/](archive/legacy-staging/)
- [archive/parked-worker-agent/](archive/parked-worker-agent/)

legacy staging 문서:

- [archive/legacy-staging/STAGING_ARCHITECTURE.md](archive/legacy-staging/STAGING_ARCHITECTURE.md)
- [archive/legacy-staging/STAGING_CONTRACT.md](archive/legacy-staging/STAGING_CONTRACT.md)
- [archive/legacy-staging/STAGING_RUNBOOK.md](archive/legacy-staging/STAGING_RUNBOOK.md)
- [archive/legacy-staging/NEXT_WORK.md](archive/legacy-staging/NEXT_WORK.md)
- [archive/legacy-staging/2026-05-02_COMPLETED_WORK_SUMMARY.md](archive/legacy-staging/2026-05-02_COMPLETED_WORK_SUMMARY.md)
- [archive/legacy-staging/2026-04-27_ENVIRONMENT_CONTRACT_SLICE.md](archive/legacy-staging/2026-04-27_ENVIRONMENT_CONTRACT_SLICE.md)

parked worker/agent 문서:

- [archive/parked-worker-agent/AGENT_WORKER_REGISTRY.md](archive/parked-worker-agent/AGENT_WORKER_REGISTRY.md)
- [archive/parked-worker-agent/WORKER_WORKSPACE_CONTRACT.md](archive/parked-worker-agent/WORKER_WORKSPACE_CONTRACT.md)
- [archive/parked-worker-agent/AGENT_TASK_QUEUE_MVP.md](archive/parked-worker-agent/AGENT_TASK_QUEUE_MVP.md)
- [archive/parked-worker-agent/AGENT_TASK_EVIDENCE_CONTRACT.md](archive/parked-worker-agent/AGENT_TASK_EVIDENCE_CONTRACT.md)

## 문서 사용 규칙

- 현재 제품 방향은 active 문서 기준으로 해석한다.
- archive 문서는 historical banner가 붙어 있어도 구현 사실 참고용일 뿐이다.
- code와 active docs가 충돌하면 먼저 현재 구현을 다시 확인한다.
