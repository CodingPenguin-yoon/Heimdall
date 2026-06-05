# Backend DevOps API

## 위치

- `backend/app/domains/devops/schemas.py`
- `backend/app/domains/devops/service.py`
- `backend/app/domains/devops/router.py`
- `backend/app/domains/devops/fixtures.py`
- `backend/app/main.py`

## 목적

현재 backend DevOps API는 typed contract skeleton이다. 운영 메타데이터를 in-memory로 다루며, provider-side 실행기나 persistence는 아직 넣지 않는다.

## 라우트

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

## contract 특징

### `Service`

- repo metadata
- lifecycle/health
- owner/runtime/framework
- runbook URL

### `ServiceEnvironment`

- `service_id` 하위 리소스
- `dev` / `staging` / `prod`
- deploy/health/version 상태

### `DeploymentTargetReference`

- `environment_id` 하위 리소스
- target kind/provider/ref/host/port 상태

### `CiCdRun`

- `service_id` 필수
- `environment_id` optional
- build/test/lint/deployable 상태
- `allowed_actions`
- `requires_user_approval`

### `DatabaseStatus`

- `environment_id` 하위 리소스
- DB health / migration / backup / restore readiness
- `secret_ref` only

## validation 규칙

현재 테스트와 스키마가 고정하는 주요 규칙:

- parent resource가 없으면 nested create 거부
- CI run의 `environment_id`는 해당 `service_id`에 속해야 함
- `service_id` / `environment_id` path와 payload mismatch 거부
- credential-bearing URL 거부
- credential query parameter 거부
- raw connection string 거부
- raw secret assignment 거부

## secret 저장 규칙

허용:

```text
vault/heimdall/sample-app/staging/db
```

허용하지 않음:

```text
postgresql://[REDACTED]
db_password=[REDACTED]
https://git.example.invalid/repo.git?access_token=[REDACTED]
```

이 규칙이 중요한 이유:

- dashboard/API/log에 secret이 새지 않도록 하기 위해서다.
- Heimdall은 secret manager가 아니라 운영 메타데이터 plane이기 때문이다.

## 의도적인 제한

- persistence 없음
- DB migration 없음
- auth 없음
- provider-side deploy/retry execution 없음
- `/api/devops/vms` 같은 VM lifecycle route 없음
- action endpoint는 preview만 제공

## 문서상 주의점

frontend read-only 특성을 backend 전체에 일반화하면 안 된다. 현재 backend는 in-memory POST contract를 포함한다. 다만 이것은 operator UI mutation이나 provider execution을 의미하지 않는다.
