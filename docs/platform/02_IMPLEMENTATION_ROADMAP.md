# GitLab Platform Implementation Roadmap

이 문서는 `docs/platform/01_GITLAB_ENV_PLATFORM_ARCHITECTURE.md` 를 실제 구현 계획으로 쪼갠 로드맵이다.

목표는 "한 번에 모든 걸 만들기"가 아니라, 운영 가능한 단계로 나누어 리스크를 줄이는 것이다.

## 1. 전제

이 로드맵은 아래를 전제로 한다.

- GitLab Self-Managed 인스턴스가 준비돼 있다.
- 이 플랫폼은 GitLab API 에 접근 가능한 서비스 계정을 가진다.
- Proxmox 템플릿 기반 VM 생성 경로는 이미 동작한다.
- Ansible 기반 초기 호스트 설정이 동작한다.

## 2. 단계별 목표

### Phase 0. 기반 정리

목표:

- 플랫폼을 멀티 프로젝트/멀티 환경 구조로 확장할 최소한의 기반을 마련한다.

작업:

- 플랫폼 내부 상태 저장용 DB 도입
- ORM 또는 명시적 repository 계층 추가
- 공통 설정 구조 도입
- GitLab 인스턴스 연결 설정 모델 추가
- audit log 기본 구조 추가

완료 기준:

- JSON 파일 없이도 주요 플랫폼 상태를 DB 에 저장 가능
- 개발/운영 환경에서 GitLab 연결 정보를 읽을 수 있음

### Phase 1. GitLab 프로젝트 인벤토리

목표:

- GitLab 프로젝트가 이 플랫폼 UI 에 자동으로 보이게 한다.

작업:

- `Projects API` 읽기 클라이언트 추가
- 수동 sync API 추가
- `System Hook` 수신 엔드포인트 추가
- 프로젝트 목록 UI 추가
- 프로젝트 상태: `discovered`, `ready_for_bootstrap`

완료 기준:

- GitLab 에서 프로젝트 생성 후 플랫폼에 나타남
- 수동 sync 로 누락 복구 가능

### Phase 2. 프로젝트 Bootstrap

목표:

- 프로젝트를 환경 배포 가능한 표준 형태로 맞춘다.

작업:

- `.argus/project.yaml` manifest 스키마 정의
- manifest 검사기 추가
- `.gitlab-ci.yml` 생성 또는 템플릿 include 자동화
- project webhook 자동 등록
- 기본 CI 변수 생성
- 프로젝트 상세 화면 추가

완료 기준:

- 프로젝트 상세 화면에서 bootstrap 상태 확인 가능
- 표준 manifest 와 CI 구성이 자동 생성됨

### Phase 3. Staging MVP

목표:

- `Deploy Staging` 한 번으로 환경이 올라가게 한다.

작업:

- staging blueprint 한 종류 정의
- 환경 생성 API 추가
- VM 생성 orchestration 추가
- PostgreSQL shared cluster 기반 DB 생성기 추가
- GitLab 변수 upsert 로직 추가
- pipeline trigger 로직 추가
- 환경 상세 UI 추가

완료 기준:

- 버튼 한 번으로 staging VM + DB + pipeline 실행
- 플랫폼에서 VM/DB/pipeline 상태 확인 가능

### Phase 4. 상태 동기화와 정리

목표:

- 파이프라인과 환경 상태를 지속적으로 맞춘다.

작업:

- GitLab project webhook 으로 pipeline/job/deployment event 수신
- 환경 상태 머신 구현
- `Redeploy`, `Destroy`, `Rotate DB Credentials` 액션 추가
- child step 기반 task 표시 강화

완료 기준:

- 배포 완료/실패 상태가 자동 반영됨
- 환경 정리 작업이 end-to-end 로 수행됨

### Phase 5. Production 하드닝

목표:

- production 운영용 보안/승인/감사를 강화한다.

작업:

- runner 분리
- secret manager 도입
- 환경별 정책/권한 모델 강화
- production 전용 blueprint 추가
- audit trail / change history 고도화

완료 기준:

- production 배포가 staging 과 분리된 정책으로 작동
- 중요한 secret 이 GitLab 과 플랫폼 DB 에 평문 저장되지 않음

## 3. MVP 범위

처음 MVP 는 아래만 해도 충분하다.

- GitLab 프로젝트 자동 목록화
- 표준 CI bootstrap
- staging 환경 1종
- PostgreSQL 1종
- VM 1대 + DB 1개 + pipeline 1회 실행
- 상태 표시와 destroy

이 범위를 넘는 자동화는 2차 목표로 두는 것이 좋다.

## 4. 권장 구현 순서

1. 플랫폼 상태 저장 DB 도입
2. GitLab 읽기 클라이언트 작성
3. 프로젝트 목록 UI
4. System Hook 수신
5. Manifest + bootstrap 자동화
6. Environment 모델 추가
7. DB provisioner 추가
8. `Deploy Staging` 오케스트레이터 추가
9. GitLab pipeline/event 동기화
10. destroy / rotate / redeploy

## 5. 세부 작업 분해

### 5.1 Backend

- `domains/gitlab`
- `domains/environments`
- `domains/webhooks`
- `services/gitlab/*`
- `services/database/*`
- `services/environments/*`
- `repositories/*`

### 5.2 Frontend

- `ProjectsPage`
- `ProjectDetailPage`
- `EnvironmentDetailPage`
- `BlueprintPage`
- 상단 네비게이션 재구성

### 5.3 Infra / Ops

- GitLab runner tag 정책
- DB admin 계정/네트워크 정책
- secret 암호화 키 관리
- platform DB backup 정책

## 6. 상태 모델 초안

### Project

- `discovered`
- `bootstrapping`
- `ready`
- `bootstrap_failed`
- `archived`

### Environment

- `ready`
- `provisioning`
- `running_pipeline`
- `deployed`
- `degraded`
- `destroying`
- `destroyed`
- `failed`

### Deployment Task

- `pending`
- `running`
- `success`
- `failed`
- `canceled`

## 7. API 우선순위

### 먼저 만들 API

- `GET /api/gitlab/projects`
- `POST /api/gitlab/sync`
- `POST /api/webhooks/gitlab/system`
- `POST /api/gitlab/projects/{project_id}/bootstrap`
- `POST /api/projects/{project_id}/environments`
- `POST /api/environments/{environment_id}/deploy`

### 그 다음 API

- `GET /api/environments/{environment_id}`
- `POST /api/environments/{environment_id}/destroy`
- `POST /api/environments/{environment_id}/redeploy`
- `GET /api/gitlab/projects/{project_id}/pipelines`

## 8. 위험 요소

### 8.1 Manifest 없는 프로젝트

대응:

- read-only 목록만 허용
- bootstrap 전에 manifest 생성 유도

### 8.2 파이프라인과 플랫폼 상태 불일치

대응:

- webhook + 주기적 poll 둘 다 사용

### 8.3 Secret 노출

대응:

- DB admin secret 은 플랫폼에만 보관
- 프로젝트에는 app 용 secret 만 전달

### 8.4 인프라 생성 실패 후 반쯤 만들어진 환경

대응:

- 각 단계별 rollback 함수 정의
- partial resource record 저장

### 8.5 플랫폼 자체가 SPOF 가 됨

대응:

- 플랫폼 DB backup
- audit log 저장
- webhook 재처리 가능 구조

## 9. 권장 블루프린트 시작점

초기에는 아래 세 가지만 있으면 된다.

- `web-small`
  - staging 용
  - 2 vCPU / 4 GB / 40 GB
  - Postgres shared DB

- `web-medium`
  - production 시작점
  - 4 vCPU / 8 GB / 80 GB
  - 전용 Postgres 인스턴스 또는 전용 DB

- `worker-small`
  - 배치/워커 서비스용
  - 2 vCPU / 4 GB / 40 GB
  - queue + optional DB

## 10. 문서화 원칙

구현과 동시에 아래 문서를 계속 유지해야 한다.

- platform architecture
- API 계약
- manifest 스키마
- blueprint 카탈로그
- secret/권한 운영 정책
- environment 상태 머신

문서와 코드가 어긋나면, 이 플랫폼은 빠르게 운영 리스크가 커진다.

## 11. 다음 작업 제안

가장 먼저 할 일은 아래 둘 중 하나다.

1. 플랫폼 상태 저장 DB 와 GitLab 인벤토리 읽기부터 구현
2. 설계를 더 구체화해서 `manifest 스키마` 와 `staging blueprint` 를 먼저 확정

이 둘이 정해져야 그 다음 단계 구현이 빨라진다.
