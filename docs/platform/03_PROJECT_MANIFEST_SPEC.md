# Project Manifest Specification

이 문서는 Heimdall 프로젝트 계약과 현재 런타임에서 실제로 강제되는 최소 검증 범위를 함께 정의한다.

중요:

- 대상 경로는 `.heimdall/project.yaml`
- `.heimdall/project.yaml` 최소 검증은 현재 GitLab inventory/settings/deploy request 경로에서 런타임으로 적용된다
- bootstrap 초안 생성과 full deployment contract 는 아직 future work 이다

관련 문서:

- [00_PLATFORM_DESIGN_SUMMARY.md](00_PLATFORM_DESIGN_SUMMARY.md)
- [02_IMPLEMENTATION_ROADMAP.md](02_IMPLEMENTATION_ROADMAP.md)
- [04_MVP_PHASE_PLAN.md](04_MVP_PHASE_PLAN.md)

## Contract Intent

`.heimdall/project.yaml` 의 목적은 아래를 최소 범위로 선언하게 하는 것이다.

- 이 프로젝트가 staging 배포 대상인지
- `docker-compose` 로 배포 가능한지
- Postgres 자동 연결이 필요한지
- merge-request bootstrap 이 어떤 초안을 생성해야 하는지

이번 계획 계약은 의도적으로 좁다.

- 환경은 `staging` 기준으로 시작한다
- 배포 전략은 `docker-compose` 만 다룬다
- DB 엔진은 `postgres` 만 다룬다

## Path

- `.heimdall/project.yaml`

bootstrap 단계에서는 플랫폼이 이 파일의 초안을 merge request 로 제안하는 방향을 기본값으로 둔다.
이 파일의 존재, 초안 생성, 검증 통과는 staging 배포 적격성/준비 상태만 뜻하며 실제 staging 배포를 자동 시작하지 않는다. 실제 시작은 명시적 사용자 `Deploy Staging` 액션에서만 가능하다.

## Minimum Schema

```yaml
name: billing-api
runtime: node

deploy:
  strategy: docker-compose
  compose_file: deploy/docker-compose.yml
  app_port: 3000
  healthcheck_path: /health

database:
  required: true
  engine: postgres
  connection_env: DATABASE_URL

environments:
  staging:
    enabled: true
```

## Field Definitions

### Top-Level

- `name`
  - 사람이 읽는 프로젝트 식별자

- `runtime`
  - bootstrap 과 검증에 참고하는 런타임 힌트
  - 예: `node`, `python`, `go`

### `deploy`

- `strategy`
  - MVP 계획 계약에서는 `docker-compose` 만 허용

- `compose_file`
  - 저장소 내 compose 파일 위치

- `app_port`
  - 앱 서비스가 수신하는 내부 포트

- `healthcheck_path`
  - staging 검증에 쓰는 HTTP 경로

### `database`

- `required`
  - Postgres 자동 연결 필요 여부

- `engine`
  - MVP 계획 계약에서는 `postgres` 만 허용

- `connection_env`
  - 앱이 받을 연결 문자열 환경변수 이름
  - 기본값 후보는 `DATABASE_URL`

### `environments`

- `staging.enabled`
  - MVP 대상 여부를 명시

production 관련 선언은 향후 확장 대상으로 남기되, 이번 계획 계약의 필수 요소에 넣지 않는다.

## Runtime-Enforced Minimum Validation

현재 백엔드는 GitLab Repository Files raw API 로 프로젝트의 기본 브랜치가 있으면 그 브랜치, 없으면 `HEAD` 에서 `.heimdall/project.yaml` 을 읽고 아래 최소 규칙만 검사한다.

- top-level `name` 이 비어 있지 않은 문자열인가
- top-level `runtime` 이 비어 있지 않은 문자열인가
- `deploy.strategy == docker-compose` 인가
- `environments.staging.enabled == true` 인가
- `database.required == true` 이면 `database.engine == postgres` 인가

현재 단계에서는 아래는 아직 검사하지 않는다.

- compose 파일 실제 존재 여부
- bootstrap MR 생성 가능 여부
- full staging/prod deployment 계약 전체

검증 상태는 `valid`, `missing`, `invalid`, `unchecked` 로 노출된다.

- `valid`: 최소 규칙을 통과함
- `missing`: `.heimdall/project.yaml` 파일이 없음
- `invalid`: 파일은 있지만 최소 스키마를 통과하지 못함
- `unchecked`: GitLab 설정 불가 또는 404 이외 API 오류로 이번 확인을 완료하지 못함

## Future Validation Work

bootstrap 또는 staging 준비 단계에서 아래를 추가 검증하는 방향을 유지한다.

- `.heimdall/project.yaml` 이 존재하거나 MR 초안 생성이 가능한가
- `deploy.strategy` 가 `docker-compose` 인가
- `deploy.compose_file` 이 저장소 경로로 해석 가능한가
- `database.engine` 이 필요한 경우 `postgres` 인가
- `environments.staging.enabled` 가 `true` 인가
- `connection_env` 이름이 배포 입력과 충돌하지 않는가

위 검증은 staging 배포 준비 여부를 판정하기 위한 것이며, discovery, inventory sync, `System Hook`, bootstrap readiness 와 마찬가지로 자동 배포 트리거가 아니다.

검증 실패 시 예상 동작:

- inventory 에는 남긴다
- staging 자동화 대상에서는 제외한다
- 수정 가능한 bootstrap MR 또는 검토 액션으로 되돌린다

## Example

```yaml
name: billing-api
runtime: node

deploy:
  strategy: docker-compose
  compose_file: deploy/docker-compose.yml
  app_port: 3000
  healthcheck_path: /health

database:
  required: true
  engine: postgres
  connection_env: DATABASE_URL

environments:
  staging:
    enabled: true
```

## Out Of Scope For The Current Slice

아래는 이번 문서에서 정의하지 않는다.

- `systemd`, `static-files`, `custom-script` 같은 다른 배포 전략
- `mysql`, `redis` 같은 다른 엔진
- production 환경 필수 스키마
- reverse proxy / domain / TLS 설정
- edge 라우팅 정책

위 항목은 나중에 확장할 수 있지만, 지금 이 문서에 넣으면 MVP 계약이 다시 흐려진다.
