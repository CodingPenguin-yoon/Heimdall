# Heimdall MVP Phase Plan

이 문서는 Heimdall MVP 의 실제 전달 순서를 더 세밀하게 정리한다.

상위 문서:

- [00_PLATFORM_DESIGN_SUMMARY.md](00_PLATFORM_DESIGN_SUMMARY.md)
- [01_GITLAB_ENV_PLATFORM_ARCHITECTURE.md](01_GITLAB_ENV_PLATFORM_ARCHITECTURE.md)
- [02_IMPLEMENTATION_ROADMAP.md](02_IMPLEMENTATION_ROADMAP.md)
- [03_PROJECT_MANIFEST_SPEC.md](03_PROJECT_MANIFEST_SPEC.md)

## Phase A. Inventory Intake

### Goal

이미 존재하는 GitLab inventory/settings/`System Hook` 슬라이스를 MVP 입력으로 묶는다.

### Scope

- 대상 프로젝트 식별
- bootstrap 가능 상태 표시
- staging 대상 후보 정리

### Implementation Work

- inventory 상태 집합 정리
- bootstrap 후보 판정 규칙 정리
- 기존 hook 기반 갱신 흐름 연결점 정의

### Done Criteria

- 어떤 프로젝트가 bootstrap 후보인지 설명 가능하다
- inventory 에서 staging 준비 대상을 식별할 수 있다
- inventory sync 와 `System Hook` 처리만으로 staging 배포가 자동 시작되지 않는다

## Phase B. Bootstrap MR

### Goal

기본 브랜치 직접 수정 없이 `.heimdall/project.yaml` 초안을 제안한다.

### Scope

- manifest 초안 생성
- branch / commit / MR 제안 규칙
- 검토 대기 상태 기록

### Implementation Work

- 저장소별 기본 템플릿 결정
- 초안 생성 실패 사유 정리
- MR 설명에 staging-first 제약 명시

### Done Criteria

- bootstrap 이 merge request 우선 경로로 고정된다
- 사용자는 MR 에서 manifest 초안을 검토할 수 있다
- bootstrap readiness 는 배포 적격성 신호일 뿐 실제 배포 트리거가 아니다

## Phase C. Staging Server Contract

### Goal

staging 서버 쪽 입력값과 성공 기준을 단일 경로로 고정한다.

### Scope

- `docker-compose` 배포 전제
- 앱 포트 및 healthcheck 계약
- 상태 기록 기준

### Implementation Work

- compose 파일 위치 검증
- 배포 전 필수 입력 목록 정의
- 최소 성공/실패 신호 정의

### Done Criteria

- 지원 경로가 `docker-compose` 하나로 고정된다
- staging 성공 기준이 문서화된다
- 서버 준비 상태만으로 실제 staging 배포가 자동 시작되지 않는다

## Phase D. Postgres Auto-Connection

### Goal

앱이 staging 에서 수동 설정 없이 Postgres 로 연결되게 한다.

### Scope

- Postgres 자원 할당
- 연결 문자열 생성
- 앱 전달 계약

### Implementation Work

- DB 이름 또는 스키마 명명 규칙 정의
- 자격증명 생성/회전의 최소 규칙 정의
- `DATABASE_URL` 전달 방식 정리

### Done Criteria

- staging 앱이 Postgres 연결 정보를 자동 수신한다
- 연결 대상과 배포 대상의 매핑이 남는다

## Phase E. Deploy Staging Skeleton

### Goal

bootstrap 이후 실제 staging 배포 실행으로 가기 위한 수동 요청 진입점, manifest 검증, task 추적의 최소 뼈대를 연다.

### Scope

- 실행 진입점
- 준비 상태 검사
- manifest 최소 검증
- 결과 기록
- 수동 요청 task 추적

### Implementation Work

- deploy 시작 조건 정의
- `.heimdall/project.yaml` 최소 검증 추가
- DB 준비 여부 검사
- 실행 로그와 상태 전이의 최소 저장 규칙 정리
- 실제 시작은 명시적 사용자 `Deploy Staging` 액션으로만 허용하고, discovery/hook/readiness/validation 신호는 준비 상태로만 사용
- 현재 슬라이스에서는 `Deploy Staging` 버튼이 valid manifest 를 통과한 경우에만 staging deploy 요청 task를 기록하고, 실제 VM/DB 실행은 deferred 상태로 남긴다

### Done Criteria

- bootstrap 완료 + valid manifest 프로젝트가 명시적 사용자 `Deploy Staging` 액션으로 staging deploy 요청 task를 남길 수 있다
- 요청 기록과 중복 방지가 추적 가능하다
- 실제 staging 실행 오케스트레이션은 다음 단계로 미뤄져 있음을 문서와 task metadata/log에서 확인할 수 있다

## Deferred After MVP

아래는 이번 phase plan 뒤로 미룬다.

- bootstrap 전체 자동화
- 완성형 `Deploy Staging` 실행 오케스트레이션
- DB provisioner 고도화
- pipeline trigger 고도화
- production flow
- reverse proxy / domain / TLS 자동화
