# Project Manifest Specification

이 문서는 GitLab 프로젝트를 이 플랫폼에 자동 온보딩하기 위한 최소 선언형 파일 형식을 정의한다.

권장 경로:

- `.argus/project.yaml`

목적:

- 프로젝트가 어떤 종류의 서비스인지
- 어떤 환경이 필요한지
- 어떤 DB 가 필요한지
- 파이프라인이 어떤 방식으로 배포되어야 하는지

를 플랫폼이 자동 판단할 수 있게 하는 것이다.

## 1. 설계 원칙

- 저장소 안에 있어야 한다.
- 사람이 읽고 수정하기 쉬워야 한다.
- 플랫폼이 안전하게 검증할 수 있어야 한다.
- 프로젝트별 커스텀 로직보다 선언형 설정을 우선한다.

## 2. 최소 스키마

```yaml
name: billing-api
project_type: webapp
runtime: node

build:
  command: npm ci && npm run build

deploy:
  strategy: docker-compose
  app_port: 3000
  healthcheck_path: /health

database:
  required: true
  engine: postgres
  mode: shared-cluster

environment_defaults:
  staging:
    blueprint: web-small
  production:
    blueprint: web-medium
```

## 3. 필드 정의

### 3.1 Top-level

- `name`
  - 사람이 읽는 프로젝트 이름
  - GitLab 프로젝트 이름과 달라도 되지만 가능하면 맞춘다

- `project_type`
  - 예: `webapp`, `worker`, `api`, `cron`

- `runtime`
  - 예: `node`, `python`, `java`, `go`

### 3.2 `build`

- `command`
  - 기본 빌드 명령
- `artifact_path`
  - 선택
  - 정적 파일/압축물/이미지 메타데이터 위치

### 3.3 `deploy`

- `strategy`
  - `docker-compose`
  - `systemd`
  - `static-files`
  - `custom-script`

- `app_port`
  - 앱이 리슨하는 포트

- `healthcheck_path`
  - 서비스 정상 여부를 판단할 경로

- `start_command`
  - 선택
  - custom/script 계열일 때 사용

### 3.4 `database`

- `required`
  - `true` 또는 `false`

- `engine`
  - `postgres`
  - `mysql`
  - `redis`
  - 초기 MVP 는 `postgres` 만 허용하는 것이 안전하다

- `mode`
  - `shared-cluster`
  - `dedicated-instance`

- `migration_command`
  - 선택
  - 예: `npm run migrate`, `alembic upgrade head`

### 3.5 `environment_defaults`

환경별 기본 blueprint 를 지정한다.

예:

```yaml
environment_defaults:
  development:
    blueprint: web-dev
  staging:
    blueprint: web-small
  production:
    blueprint: web-medium
```

## 4. 확장 필드

필요하면 아래 필드를 확장할 수 있다.

```yaml
env:
  required:
    - JWT_SECRET
    - APP_BASE_URL
  generated:
    - DATABASE_URL

network:
  public: true
  domain_template: "{env}.{project}.example.com"

deploy:
  strategy: docker-compose
  compose_file: deploy/docker-compose.yml

runner:
  tags:
    - build-shared
    - deploy-staging
```

## 5. 검증 규칙

플랫폼은 bootstrap 전에 아래를 검증해야 한다.

- `project_type` 유효성
- `runtime` 지원 여부
- `deploy.strategy` 지원 여부
- DB 설정과 blueprint 호환성
- 필수 env 이름 충돌 여부
- healthcheck 경로 형식

검증 실패 시:

- 프로젝트는 read-only 인벤토리 상태로만 남긴다
- 자동 배포 버튼은 비활성화한다

## 6. 예시

### 6.1 Node.js API

```yaml
name: billing-api
project_type: api
runtime: node

build:
  command: npm ci && npm run build

deploy:
  strategy: docker-compose
  app_port: 3000
  healthcheck_path: /health

database:
  required: true
  engine: postgres
  mode: shared-cluster
  migration_command: npm run migrate

environment_defaults:
  staging:
    blueprint: web-small
  production:
    blueprint: web-medium
```

### 6.2 Python Worker

```yaml
name: report-worker
project_type: worker
runtime: python

build:
  command: pip install -r requirements.txt

deploy:
  strategy: systemd
  start_command: python -m app.worker

database:
  required: false

environment_defaults:
  staging:
    blueprint: worker-small
```

## 7. 권장 Bootstrap 동작

프로젝트에 이 파일이 없으면 플랫폼은 다음 중 하나를 해야 한다.

1. 샘플 manifest 를 생성해 커밋
2. merge request 로 초안 제안
3. 웹 UI 에서 manifest 생성 마법사 제공

운영 안정성을 생각하면, 직접 main 브랜치에 밀어넣는 것보다 merge request 로 제안하는 편이 더 안전하다.

## 8. 비목표

이 manifest 는 Helm chart 나 Terraform module 전체를 대체하려는 것이 아니다.

목적은 오직:

- 플랫폼이 프로젝트를 식별하고
- 환경에 맞는 자동화 결정을 하고
- GitLab pipeline 과 인프라 연결을 일관되게 수행하는 것

에 있다.
