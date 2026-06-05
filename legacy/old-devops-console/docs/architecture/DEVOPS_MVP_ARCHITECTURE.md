# DevOps MVP 아키텍처

## 목표

Heimdall MVP는 사람이 서비스 운영 상태를 읽고 판단하는 DevOps control plane을 만든다. 현재 목표는 자동 실행기가 아니라 운영 모델을 typed contract로 정리하는 것이다.

## 현재 아키텍처 한눈에 보기

```text
Operator/Hermes
  -> Heimdall frontend (/devops, read-only)
  -> Heimdall backend (/api/devops/*, typed contract skeleton)
  -> service/environment/ci-run/db-status/deployment-target read models
  -> runbook/verification reference

Gjallar
  -> VM provisioning / Proxmox lifecycle / infra ownership
```

## 핵심 엔티티

### 1. `Service`

서비스 카탈로그의 기준 단위다.

포함하는 운영 정보:

- repo metadata
- owner team
- runtime/framework
- health/lifecycle
- runbook URL
- current version / commit

### 2. `ServiceEnvironment`

서비스별 환경 단위다.

예:

- `sample-api:dev`
- `sample-api:staging`
- `sample-api:prod`

포함하는 운영 정보:

- environment name
- branch
- desired/deployed version
- health/deploy status
- last deployed timestamp

### 3. `DeploymentTargetReference`

배포가 향하는 실제 target을 참조한다. 현재 MVP는 target을 “직접 생성”하지 않고 “참조”한다.

포함하는 운영 정보:

- `target_kind`
- `provider`
- `gjallar_ref`
- `host`
- `port`
- `scheme`
- readiness / reachability

### 4. `CiCdRun`

CI/CD 이력과 판단용 신호를 저장한다.

포함하는 운영 정보:

- provider
- pipeline URL
- build/test/lint/deployable
- run status
- approval 필요 여부
- preview 가능한 action 목록

### 5. `DatabaseStatus`

DB 운영 가시성 모델이다.

포함하는 운영 정보:

- engine / role
- `secret_ref`
- `host_ref`
- connection health
- migration status
- backup status
- restore readiness

## 왜 `secret_ref`만 저장하는가

Heimdall의 역할은 운영 메타데이터와 판단 신호를 관리하는 것이다. secret 원문을 들고 있으면 다음 문제가 생긴다.

- 문서, 로그, API payload, DB row에 비밀값이 퍼질 수 있다.
- 운영자용 dashboard와 실행기 책임이 섞인다.
- provider 변경 시 credential 확산 범위가 커진다.

그래서 현재 계약은 다음을 지킨다.

- raw `DATABASE_URL` 금지
- `token`, `api_key`, `client_secret` 같은 query/value 금지
- secret은 secret manager 또는 vault path reference로만 다룸

## 왜 raw shell/provider action을 아직 안 넣는가

현재 MVP는 “어디가 문제인지 판단할 수 있는 DevOps 운영 화면과 계약”을 먼저 고정하는 단계다. 실행기를 먼저 넣으면 다음 위험이 있다.

- product boundary가 불명확해진다.
- approval, audit, rollback 모델 없이 side effect가 생긴다.
- Gjallar와의 책임 분리가 다시 흐려진다.

그래서 현재는:

- CI action은 preview only
- deploy/retry/provider execution 없음
- VM lifecycle 없음
- frontend mutation 없음

## 운영 플로우

현재 MVP 관점의 정상 흐름:

1. service를 등록한다.
2. service 아래에 `dev`/`staging`/`prod` environment를 연결한다.
3. environment에 deployment target reference와 DB status를 연결한다.
4. CI/CD run과 검증 결과를 읽는다.
5. 운영자는 runbook과 verification reference를 보고 다음 행동을 결정한다.

새 target 또는 새 VM이 필요할 때:

1. Heimdall이 필요한 target shape를 보여 준다.
2. 운영자 또는 Hermes가 Gjallar 작업 필요를 판단한다.
3. Gjallar가 VM/host/proxmox 자원을 준비한다.
4. Heimdall은 준비된 target을 reference로 연결한다.
