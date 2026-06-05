# Safe Smoke Fixtures

## 목적

`HEIMDALL_DEVOPS_SMOKE_FIXTURES`는 non-production smoke/demo/validation용 fixture seed를 opt-in으로 켜는 환경 변수다.

## 환경 변수

이름:

```text
HEIMDALL_DEVOPS_SMOKE_FIXTURES
```

truthy 값:

```text
1
true
yes
on
smoke
```

기본 동작:

- 설정하지 않으면 catalog는 비어 있다.

## fixture 내용

현재 fixture는 다음 유형을 채운다.

- sample `Service`
- `staging` / `prod` `ServiceEnvironment`
- `DeploymentTargetReference`
- `CiCdRun`
- `DatabaseStatus`

## 안전 설계

fixture는 production처럼 보이는 값을 의도적으로 피한다.

- URL/host는 `.invalid` 사용
- DB secret은 `vault/heimdall/devops-smoke/...` 형태의 `secret_ref` 사용
- CI run은 `allowed_actions=[]`
- fixture mutation endpoint 없음

## 왜 중요한가

smoke fixture는 화면과 계약을 검증하기 위한 데이터여야지, 실제 실행 가능한 운영 데이터가 되면 안 된다. 그래서 다음을 모두 피한다.

- 실제 credential
- 실제 `DATABASE_URL`
- 실제 provider token
- 실제 실행 가능한 host target

## 사용 시점

- local smoke check
- demo
- dashboard rendering 검증
- contract fixture 기반 테스트

사용하지 않을 시점:

- production bootstrap
- persistent seed data
- provider-side operation
