# Heimdall

> 사람이 쓰는 **DevOps 운영 콘솔** — CI/CD, 데이터베이스 연결, 배포 환경, 운영 상태를 한 곳에서 관리한다.

Heimdall의 1차 제품 방향은 AI/agent 플랫폼이 아니다.
새 기준은 다음이다.

```text
Heimdall = DevOps 시스템
- 서비스/프로젝트/환경 catalog
- CI/CD 상태와 실행 이력
- DB 연결/health/migration/backup 상태
- 배포 환경과 release/rollback/runbook
- 운영 로그와 검증 리포트
```

Hermes는 Heimdall을 대신 조작하거나 상태를 요약하는 운영자다.
Codex/Claude/OpenCode worker류 기능은 1차 MVP 이후 DevOps 자동화 adapter 후보로 둔다.

---

## 전체 홈랩에서의 위치

```text
사용자 / 브라우저
  ↓ 직접 조작
Heimdall
  ↓ DevOps 운영: CI/CD / DB / 배포 / 로그 / 릴리즈 / 검증
서비스 / 애플리케이션 / 데이터베이스 / 배포 환경
```

Hermes 사용 시:

```text
사용자 / Discord
  ↓ 자연어 요청
Hermes
  ↓ Heimdall UI/API를 대신 조작하거나 상태를 요약
Heimdall
```

인프라가 필요할 때는 Heimdall이 직접 Proxmox VM을 만들지 않고 Gjallar를 사용한다.

```text
Gjallar = VM 생성 및 Proxmox 운영 시스템
Heimdall = DevOps 시스템
Hermes = 둘을 대신 컨트롤할 수 있는 운영자
```

---

## Heimdall이 1차 MVP에서 담당하는 것

### 1. Service / Project / Environment Catalog

- 서비스 목록
- repo URL / owner / runtime / framework
- dev / staging / prod 환경
- 현재 배포 commit/version
- 연결된 VM/host/domain/DB reference
- health 상태

### 2. CI/CD 운영

- pipeline 상태
- 최근 run history
- build/test/lint 결과
- 실패 로그 요약
- retry / approve / hold 같은 operator action boundary
- 배포 가능 여부

### 3. 데이터베이스 연결/운영 상태

- 서비스별 DB connection metadata
- DB 종류와 환경
- secret reference만 저장
- connection health
- migration 적용/pending 상태
- backup/restore readiness

### 4. 배포 환경 관리

- dev/staging/prod 환경 목록
- deployment target
- release history
- rollback 후보
- pre-deploy checklist
- post-deploy smoke check
- runbook link/action boundary

### 5. 운영 로그 / 검증 리포트

- 최근 실패 로그
- 테스트/빌드/배포 검증 결과
- 사람이 읽기 쉬운 요약
- 조치 필요/확인 필요/정상 상태 구분

---

## Heimdall이 1차 MVP에서 담당하지 않는 것

| 영역 | 담당/처리 |
|---|---|
| Proxmox node/VM/LXC/storage inventory | Gjallar |
| VM 생성/삭제/lifecycle action | Gjallar |
| Proxmox backup/snapshot/storage/guest-agent risk | Gjallar |
| Codex/Claude/OpenCode worker 플랫폼 | MVP 이후 adapter 후보 |
| agent task queue 중심 제품화 | 보류 |
| LLM provider/context/memory/agent loop | Hermes |
| credential 원문/API key/token/private key 저장 | 금지 |
| raw shell 무제한 자동 실행 | 금지 |

---

## Gjallar와의 관계

두 프로젝트는 기능을 중복하지 않는다.

```text
Gjallar = 인프라/VM 계층
Heimdall = DevOps/서비스 운영 계층
```

예시:

```text
서비스 배포 target이 부족하다
→ Heimdall: 어떤 서비스/환경에 target이 필요한지 보여줌
→ Hermes/사용자: 새 VM 필요 판단
→ Gjallar: VM 생성/운영 담당
→ Heimdall: 생성된 target을 서비스/환경에 연결해서 운영 상태 관리
```

### Terraform/Ansible 소유권 원칙

장기적으로 VM 인프라 소유권은 Gjallar에 모은다.
Heimdall은 VM을 직접 Terraform state로 소유하지 않고, Gjallar가 제공한 target을 DevOps 환경 reference로 사용한다.

---

## 현재 repo 상태 해석

이 repo에는 아직 과거 staging-first 구현과 worker/agent 관련 코드가 남아 있을 수 있다.
당장 모든 코드를 한 번에 삭제하지 않는다.
앞으로는 아래 기준으로 정리한다.

```text
VM/Proxmox ownership → Gjallar
CI/CD / DB / deployment / logs / verification → Heimdall
worker/agent automation → MVP 이후 adapter 후보
```

---

## 우선순위 로드맵

### Phase 0 — 정체성 정리

- [x] Heimdall을 사람용 DevOps 운영 시스템으로 재정의
- [x] Gjallar와 역할 분리 문서화
- [x] shared docs / repo README / docs README 방향 갱신
- [ ] legacy staging/GitLab/worker 중심 상세 문서 정리

### Phase 1 — Service / Environment Catalog

- [ ] 서비스 catalog schema
- [ ] repo/owner/runtime/framework metadata
- [ ] dev/staging/prod environment schema
- [ ] deployment target / DB reference schema

### Phase 2 — CI/CD Status

- [ ] pipeline provider 연결 방식 결정
- [ ] run status/history schema
- [ ] build/test/lint 결과 수집
- [ ] 실패 로그 요약

### Phase 3 — DB Status

- [ ] DB connection metadata
- [ ] secret reference policy
- [ ] health/migration/backup readiness

### Phase 4 — Deployment / Runbook

- [ ] release history
- [ ] rollback candidate
- [ ] pre/post deploy checklist
- [ ] runbook action boundary

### Phase 5 — Later adapters

- [ ] CI 실패 자동 분석
- [ ] PR 준비 자동화
- [ ] worker/agent runner 연동 재검토

---

## Repository layout

```text
backend/        Backend API
frontend/       Web UI
infra/          Legacy provisioning/deploy assets; review before extending
docs/           Repo-local docs. Shared storage remains the product source of truth.
```

---

## 문서 source of truth

제품 방향과 현재 상태는 shared storage를 우선한다.

```text
/mnt/hermes_data/프로젝트/헤임달
/mnt/hermes_data/프로젝트/AI_Homelab_Control_Plane_방향성.md
```

repo-local docs가 shared docs와 다르면 shared docs를 우선한다.
