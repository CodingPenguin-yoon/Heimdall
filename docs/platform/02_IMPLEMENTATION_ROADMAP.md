# Heimdall Implementation Roadmap

이 문서는 Heimdall 전달 방향에 맞춰 MVP 와 후속 단계를 단계별로 정리한다.

관련 문서:

- [00_PLATFORM_DESIGN_SUMMARY.md](00_PLATFORM_DESIGN_SUMMARY.md)
- [01_GITLAB_ENV_PLATFORM_ARCHITECTURE.md](01_GITLAB_ENV_PLATFORM_ARCHITECTURE.md)
- [03_PROJECT_MANIFEST_SPEC.md](03_PROJECT_MANIFEST_SPEC.md)
- [04_MVP_PHASE_PLAN.md](04_MVP_PHASE_PLAN.md)

## Planning Assumptions

- GitLab inventory/settings/`System Hook` 관련 슬라이스는 이미 존재한다
- 이번 로드맵은 그 위에 Heimdall MVP 를 얹는 순서를 다룬다
- MVP 계약은 `docker-compose` only, `postgres` only, `staging` first, merge-request bootstrap first 이다
- `.heimdall/project.yaml` 최소 검증은 현재 런타임에 반영되지만, bootstrap/full deploy 계약 전체가 완료된 것은 아니다

## Phase 1. Narrow The Contract

### Goal

MVP 가 지원하는 저장소 계약과 운영 경계를 명확히 고정한다.

### Scope

- `.heimdall/project.yaml` 계약 정리와 최소 검증 반영
- `staging` 전용 범위 명시
- `docker-compose` / `postgres` 만 허용
- production 및 edge 자동화 명시적 제외

### Implementation Work

- manifest 필수 필드와 검증 규칙 정의
- inventory/settings/deploy request 에서 최소 검증 상태 노출
- 배포 입력값에서 비지원 전략 제거
- 문서와 UI 문구에서 “지원 예정”과 “현재 범위” 구분

### Done Criteria

- 문서 기준 계약이 단일 해석만 가능하다
- 비지원 배포 전략이나 DB 엔진이 MVP 계약에 남아 있지 않다
- production 이 future work 로 분리되어 있다

## Phase 2. Merge-Request Bootstrap

### Goal

프로젝트가 Heimdall 관리 대상으로 들어오는 첫 경로를 안전하게 만든다.

### Scope

- GitLab inventory 에서 대상 프로젝트 식별
- `.heimdall/project.yaml` 초안 생성
- merge request 로 bootstrap 제안

### Implementation Work

- inventory 상태에 bootstrap 준비 상태 추가
- manifest 초안 생성기 정의
- merge request 생성 규칙 정의
- bootstrap 제안 상태 저장

### Done Criteria

- 대상 프로젝트에 대해 bootstrap MR 초안을 일관되게 제안할 수 있다
- 사용자는 직접 기본 브랜치 푸시 없이 초안을 검토할 수 있다
- MR 상태와 inventory 상태가 연결된다
- bootstrap, inventory sync, hook 이벤트만으로 staging 배포가 자동 시작되지 않는다

## Phase 3. Staging Deployment Substrate

### Goal

`staging` 서버 배포에 필요한 최소 서버 계약을 닫는다.

### Scope

- `docker-compose` 배포 입력만 허용
- staging 환경 메타데이터
- 서버 준비 및 앱 실행 기준 정리

### Implementation Work

- staging 전용 환경 모델 정의
- compose 파일 위치와 필수 값 검증
- 서버 기동 전제와 상태 기록 정의
- 배포 실행 이력 저장
- 준비 상태 갱신과 실제 배포 시작을 분리하고, 실제 시작은 사용자 `Deploy Staging` 액션으로만 허용

### Done Criteria

- staging 에 필요한 입력값이 manifest 와 환경 모델에서 닫힌다
- 비지원 전략 없이 `docker-compose` 경로만 남는다
- 배포 시도와 결과를 추적할 수 있다

## Phase 4. Postgres Auto-Connection

### Goal

서비스 앱이 staging 에서 Postgres 에 자동 연결되도록 한다.

### Scope

- `postgres` only
- 서비스 DB 또는 스키마 할당
- 앱 연결 정보 주입

### Implementation Work

- DB 자원 명명 규칙 정의
- 접속 정보 생성 및 저장 규칙 정의
- GitLab 변수 또는 배포 입력으로 전달되는 연결 계약 정의
- 앱 측 필수 환경변수 계약 정리

### Done Criteria

- staging 대상 앱이 수동 DB 입력 없이 Postgres 연결 정보를 받는다
- 연결 정보 생성 이력과 대상 환경이 추적된다
- 다른 DB 엔진 가정이 남아 있지 않다

## Phase 5. Deploy Staging Flow

### Goal

bootstrap 이후 실제 `Deploy Staging` 실행 흐름의 기본 뼈대를 연결한다.

### Scope

- 배포 실행 진입점
- 상태 전이
- 최소 실패 보고

### Implementation Work

- 배포 요청에서 staging 환경 선택 규칙 정의
- 배포 전 manifest/DB 준비 상태 검사
- 현재는 valid manifest + 수동 요청 task 기록까지만 제공
- 배포 시작, 성공, 실패 상태 기록
- 운영자/개발자가 볼 최소 상태 노출
- discovery, inventory sync, `System Hook`, bootstrap readiness, manifest validation 은 배포 적격성 검사 입력으로만 사용

### Done Criteria

- bootstrap 완료 프로젝트에서 명시적 사용자 `Deploy Staging` 액션으로 staging 배포를 시작할 수 있다
- 실패 지점이 상태로 남는다
- 후속 재시도 설계의 기반이 생긴다

## Future Work

아래는 중요하지만 MVP 뒤로 미룬다.

- bootstrap 완성형 자동화
- DB provisioner 운영 고도화
- pipeline trigger 고도화
- production 환경 흐름
- reverse proxy / domain / TLS 자동화

상세 실행 순서는 [04_MVP_PHASE_PLAN.md](04_MVP_PHASE_PLAN.md) 를 따른다.
