# Gjallar / Heimdall 경계

## 한 줄 규칙

```text
Gjallar는 VM과 Proxmox를 운영한다.
Heimdall은 준비된 대상 위의 DevOps 운영 상태를 관리한다.
```

## Gjallar가 맡는 것

- VM 생성
- Proxmox lifecycle
- node / storage / snapshot / backup 같은 infra 관점 운영
- VM bootstrap의 infra 소유권
- Terraform/infra ownership

## Heimdall이 맡는 것

- service catalog
- environment 상태
- CI/CD run history
- DB health / migration / backup readiness
- deployment target reference
- verification report, logs, runbook

## Heimdall에서 target이 필요할 때

Heimdall은 target 자체를 provision하지 않고 requirement와 reference를 관리한다.

예시 흐름:

1. `prod` environment에 새 deployment target이 필요하다.
2. Heimdall 또는 Hermes가 필요한 shape를 정리한다.
3. 운영자는 Gjallar에 VM/host 준비를 요청한다.
4. Gjallar가 준비를 끝내면 target metadata를 Heimdall에 연결한다.

이때 Heimdall에 남는 정보:

- `target_kind`
- `provider`
- `gjallar_ref`
- `host`
- `port`
- health/reachability

이때 Heimdall에 남지 않는 정보:

- Proxmox credential
- VM clone procedure
- Terraform state detail
- raw bootstrap secret

## 왜 이렇게 나누는가

- 인프라 lifecycle과 서비스 운영 lifecycle은 변경 주기가 다르다.
- 사람이 보는 운영 dashboard와 VM 생성 절차를 같은 제품 표면에 두면 복잡도가 급격히 올라간다.
- Hermes가 중간에서 두 시스템을 대신 조작하더라도, 각 시스템의 typed responsibility는 유지되어야 한다.

## worker/agent와의 관계

worker/agent는 지금 당장 Gjallar도 Heimdall도 대표하지 않는다. 나중에 붙더라도 다음 원칙을 따른다.

- VM lifecycle ownership은 여전히 Gjallar
- service 운영 contract ownership은 여전히 Heimdall
- worker/agent는 adapter/runner일 뿐 MVP 정체성이 아니다
