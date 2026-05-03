# Heimdall

> Hermes가 조종하는 **Agentic DevOps Execution Plane**

Heimdall은 더 이상 “Proxmox VM을 직접 만들고 GitLab 프로젝트를 staging에 배포하는 단일 앱”으로 보지 않는다.
새 방향성은 다음처럼 고정한다.

```text
Heimdall = agent worker / repo / test / build / PR / staging 검증을 실행·기록하는 DevOps 실행 계층
```

쉽게 말하면 Heimdall은 **AI 개발 작업자의 작업장과 관제탑**이다.
판단과 대화는 Hermes가 맡고, Heimdall은 Hermes가 안전하게 호출할 수 있는 typed API, task log, verification report를 제공한다.

---

## 전체 홈랩에서의 위치

```text
사용자 / Discord
  ↓ 자연어 요청
Hermes
  ↓ 판단 / 계획 / 승인 / 검토 / 보고
Heimdall
  ↓ 작업 실행 / 로그 / 검증 / PR / staging
Codex Worker / Claude Worker / OpenCode Worker / CI Runner
```

인프라가 필요할 때는 Heimdall이 직접 Proxmox VM을 만들지 않고 Gjallar를 사용한다.

```text
Hermes
  → Heimdall: worker capacity / DevOps task 필요 확인
  → Gjallar: VM 생성 plan / risk 확인
  → 사용자 승인
  → Gjallar: Proxmox VM 생성·bootstrap
  → Heimdall: worker 등록·상태 확인
  → Heimdall: repo 작업 / test / build / PR / staging 검증 실행
```

---

## Heimdall이 담당하는 것

### 1. Agent worker 운영

- Codex / Claude / OpenCode worker 등록
- worker 상태 확인
- worker별 repo clone/fetch/reset
- agent 실행 래핑
- agent 작업 로그와 artifact 저장
- 인증 상태 확인: `authenticated` / `expired` / `unknown`

Heimdall은 Codex OAuth token 원문을 저장하거나 추출하지 않는다.
worker VM 안에서 공식 `device-auth` 흐름으로 인증된 상태만 관측한다.

### 2. DevOps task lifecycle

Heimdall은 작업을 대화형 agent loop로 직접 추론하지 않는다.
대신 작업 상태를 명확하게 관리한다.

```text
queued → running → needs_review → succeeded
                    ↘ failed
                    ↘ cancelled
```

Hermes는 이 task 상태와 로그를 보고 다음 판단을 한다.

### 3. Repo / branch / worktree / PR 흐름

- repo 연결
- issue/task 기반 작업 생성
- branch/worktree 준비
- agent 작업 결과 diff 수집
- test/build/lint 실행
- PR 생성/업데이트 준비
- 결과 요약과 검증 리포트 저장

### 4. Staging 검증

Staging은 Heimdall에 남을 수 있다.
다만 의미가 바뀐다.

기존:

```text
Heimdall이 VM을 만들고 staging host pool까지 직접 관리
```

새 방향:

```text
Gjallar가 VM/인프라를 제공
Heimdall은 그 위에서 앱 배포, 헬스체크, 검증 리포트를 실행
```

즉 staging은 “인프라 생성 기능”이 아니라 **DevOps 실행 결과 검증 단계**로 정리한다.

---

## Heimdall이 담당하지 않는 것

| 영역 | 담당 프로젝트 | 이유 |
|---|---|---|
| Proxmox node/VM/LXC/storage inventory | Gjallar | 인프라 운영 가시성은 Gjallar의 핵심 역할 |
| VM 생성/삭제/lifecycle action | Gjallar | Terraform/Proxmox state 소유권을 한 곳에 모으기 위해 |
| 운영 리스크 대시보드 | Gjallar | backup/snapshot/storage/guest-agent/owner 정책은 인프라 운영 문제 |
| LLM provider/context/memory/agent loop | Hermes | Heimdall은 자체 Hermes가 되지 않는다 |
| raw shell 무제한 자동 실행 | 하지 않음 | typed action, 승인, 로그, 검증 경계가 필요 |
| Codex/Claude/OpenCode token 원문 저장 | 하지 않음 | credential은 worker 내부 공식 인증 상태로만 다룬다 |

---

## Gjallar와의 관계

두 프로젝트는 경쟁하거나 기능을 중복하지 않는다.

```text
Gjallar = Proxmox 인프라를 준비하고 안전하게 운영하는 계층
Heimdall = 준비된 인프라 위에서 개발/배포/agent 작업을 실행하는 계층
Hermes = 두 계층을 조합해서 판단하고 사용자에게 보고하는 자연어 운영자
```

### 예시: 새 Codex worker가 필요할 때

1. Hermes가 Heimdall 상태를 보고 worker capacity 부족을 확인한다.
2. Hermes가 Gjallar에 worker VM 생성 plan을 요청한다.
3. Gjallar가 node/storage/template/network/resource risk를 확인한다.
4. 사용자가 승인하면 Gjallar가 VM을 생성하고 bootstrap한다.
5. Heimdall이 VM을 worker registry에 등록한다.
6. 사용자가 필요하면 worker 안에서 Codex device-auth를 승인한다.
7. Heimdall이 해당 worker에 repo 작업을 배정한다.

### Terraform/Ansible 소유권 원칙

장기적으로 VM 인프라 소유권은 Gjallar에 모은다.
Heimdall은 VM을 직접 Terraform state로 소유하지 않고, Gjallar API를 통해 필요한 실행 환경을 요청하는 consumer가 된다.

---

## 현재 repo 상태 해석

이 repo에는 아직 과거 staging-first 구현과 문서가 남아 있다.
특히 아래 표현은 새 방향성에서 legacy 또는 전환 대상이다.

- Proxmox VM 생성이 Heimdall의 핵심 기능처럼 보이는 설명
- staging host registry / staging pool을 인프라 소유 계층처럼 다루는 설명
- GitLab deploy 중심으로 제품 정체성을 설명하는 문서

당장 모든 코드를 한 번에 삭제하지 않는다.
대신 앞으로는 아래 기준으로 정리한다.

```text
VM/Proxmox ownership → Gjallar로 이동
repo/task/worker/test/PR/staging verification → Heimdall에 유지
```

---

## 우선순위 로드맵

### Phase 0 — 정체성 정리

- [x] Heimdall을 `Agentic DevOps Execution Plane`으로 재정의
- [x] Gjallar와 역할 분리 문서화
- [x] root README / docs README를 새 방향성으로 갱신
- [ ] legacy staging/GitLab 중심 상세 문서 정리

### Phase 1 — Worker registry

- worker schema 정의
- worker type: Codex / Claude / OpenCode / generic runner
- auth status / health status / current task / last heartbeat 관리

### Phase 2 — Agent task lifecycle

- task queue
- task 상태 전이
- log/artifact 저장
- 실패/취소/검토 필요 상태 분리

### Phase 3 — Repo execution flow

- repo checkout/fetch/reset
- branch/worktree 관리
- agent command 실행
- test/build/lint 결과 수집
- diff summary와 PR 준비

### Phase 4 — Gjallar integration

- worker VM 필요성 판단
- Gjallar provision API contract 정의
- 생성된 VM을 Heimdall worker로 등록
- owner/environment/service metadata 정리

### Phase 5 — Thin adapters

웹앱/API가 안정화된 뒤 MCP/CLI adapter를 얇게 붙인다.
Heimdall 자체를 또 다른 대화형 AI로 만들지 않는다.

---

## Repository layout

```text
backend/        Backend API and task orchestration code
frontend/       Web UI
infra/          Legacy provisioning/deploy assets; review before extending
docs/           Repo-local docs. Shared storage remains the product source of truth.
```

---

## 문서 source of truth

제품 방향과 현재 상태는 shared storage를 먼저 본다.

```text
/mnt/hermes_data/프로젝트/헤임달
/mnt/hermes_data/프로젝트/AI_Homelab_Control_Plane_방향성.md
```

읽는 순서:

1. `/mnt/hermes_data/프로젝트/헤임달/README.md`
2. `/mnt/hermes_data/프로젝트/헤임달/CURRENT_STATE.md`
3. `/mnt/hermes_data/프로젝트/헤임달/TASKS.md`
4. `/mnt/hermes_data/프로젝트/헤임달/DECISIONS.md`
5. `/mnt/hermes_data/프로젝트/헤임달/01_아키텍처/Hermes_중심_Heimdall_방향성.md`
6. `/mnt/hermes_data/프로젝트/Gjallar/README.md`

Repo-local docs는 [docs/README.md](docs/README.md)에서 시작한다.

---

## 한 줄 결론

```text
Heimdall은 Hermes가 조종하는 agent/devops 실행 계층이고,
Gjallar는 그 실행 계층이 올라갈 Proxmox 인프라를 제공하는 운영 계층이다.
```
