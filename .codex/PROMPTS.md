# Heimdall Multi-Agent Prompt Templates

이 파일은 이 저장소의 멀티 에이전트 설정과 같이 쓰는 복붙용 프롬프트 모음이다.

## Quick Start

새 Codex 세션을 이 저장소 루트에서 열고 아래 프롬프트 중 하나를 그대로 붙여 넣는다.

현재 구성 기준 역할:
- `explorer`: 범위 파악
- `reviewer`: 리스크 리뷰
- `docs_researcher`: 문서와 설정 가정 검증
- `worker`: 최소 수정 수행

## General Implementation

```text
이 작업은 Heimdall 기본 멀티 에이전트 플로우로 처리해.

1. explorer가 먼저 실제 코드 경로, 영향 파일, 관련 심볼, 설정/마이그레이션, 연관 테스트를 정리한다.
2. reviewer가 correctness, regression, security, missing tests 관점에서 실제 리스크만 찾는다.
3. docs_researcher가 로컬 문서, 프레임워크/API/설정 가정을 검증한다.
4. worker가 가장 작은 수정만 적용한다.

중간 로그는 길게 노출하지 말고, 마지막에 아래 형식으로 통합해서 보여줘.
- scope
- risks
- docs constraints
- changes made
- validation
- residual risk
```

## Bug Investigation And Fix

```text
이 버그를 Heimdall 멀티 에이전트 플로우로 조사하고 수정해.

- explorer는 재현에 관련된 실제 코드 경로와 상태 전이를 찾는다.
- reviewer는 실패 원인 후보와 회귀 포인트를 severity 순으로 정리한다.
- docs_researcher는 관련 옵션, 버전 제약, 설정 요구사항을 검증한다.
- 원인 가설이 정리된 뒤에만 worker가 수정한다.

수정 전에는 원인 가설과 근거를 먼저 한 번 요약해.
수정 후에는 변경 파일, 검증 결과, 남은 불확실성을 정리해.
```

## Branch Review

```text
현재 브랜치를 main과 비교해 Heimdall 멀티 에이전트 리뷰를 해줘.

- explorer는 변경 영향 범위와 연쇄 영향 파일을 맵핑한다.
- reviewer는 must-fix 수준의 correctness, security, regression 이슈만 찾는다.
- docs_researcher는 패치가 기대는 외부 동작이나 버전 의존성을 확인한다.
- worker는 수정하지 않는다.

최종 결과는 아래 세 구역으로만 정리해.
- must fix
- should fix
- watchlist
```

## Safe Refactor

```text
이 리팩터를 바로 크게 하지 말고 Heimdall 방식으로 안전 범위부터 잡아줘.

- explorer가 변경 후보 파일, 호출 경로, 인터페이스 경계를 찾는다.
- reviewer가 깨질 수 있는 계약, 데이터 흐름, 테스트 공백을 찾는다.
- docs_researcher가 버전, 설정, 마이그레이션 제약을 확인한다.
- worker는 단계 1의 최소 변경만 수행한다.

한 번에 큰 리팩터 대신 되돌리기 쉬운 작은 단계로 나눠서 진행해.
```

## Scope First

```text
explorer를 먼저 돌려서 이 작업의 실제 코드 경로를 좁혀줘.
영향 파일, 관련 심볼, 설정, 마이그레이션, 연관 테스트를 먼저 정리하고
수정 제안은 하지 말고 근거 위주로만 요약해.
```

## Risk Review Only

```text
reviewer를 돌려서 correctness, regression, security, missing tests 관점으로만 봐줘.
스타일 코멘트는 빼고 실제로 터질 가능성이 있는 것만
severity와 근거 중심으로 정리해.
```

## Docs Validation Only

```text
docs_researcher를 돌려서 이 구현이 기대는 프레임워크, API, 설정 가정을 확인해줘.
로컬 문서와 버전 정보를 먼저 보고,
외부 docs MCP가 있으면 그걸로 교차 검증해.
확인된 사실, 버전 주의점, 구현에 미치는 영향만 요약해.
```

## Worker Only

```text
이제 worker만 수정하게 해.
explorer와 reviewer가 좁힌 범위 안에서만 움직이고,
가장 작은 수정만 적용해.
관련 없는 리팩터는 하지 말고,
마지막에 변경 파일, 검증 결과, 잔여 리스크를 요약해.
```

## Heimdall-Specific Variant

이 저장소는 현재 `product/` 아래의 Heimdall 제품 구현을 중심으로 한다.
주요 경로는 FastAPI API, Vite Web, Docker Compose self-hosting, 운영/아키텍처 문서다.

```text
이 작업은 Heimdall 멀티 에이전트 플로우로 처리하되, 아래를 특히 신경 써줘.

- explorer는 product/apps/api, product/apps/web, product/compose.yaml, product/docs 중 실제 영향 경로만 좁힌다.
- reviewer는 preview 배포 회귀, Docker/socket trust boundary, env 설정 누락, API 계약 변경, DB/secret handling 리스크를 우선 본다.
- docs_researcher는 README, product/docs/, .env.compose.example, Docker/Compose 실행 가이드를 먼저 확인한다.
- worker는 범위 밖 디렉터리는 건드리지 않고 최소 수정만 한다.

결과는 아래 형식으로 정리해.
- impacted areas
- deployment risk
- config/env caveats
- changes made
- validation
- residual risk
```

## Notes

- 멀티 에이전트 설정은 새 Codex 세션에서 읽히는 것이 가장 확실하다.
- 기본 운영 방식은 `AGENTS.md`를 따른다. main session은 직접 편집할 수 있고, subagent는 큰 작업이나 위험한 작업에서만 쓴다.
- `explorer`, `reviewer`, `docs_researcher`는 읽기/검증 역할로 쓰고, `worker`는 범위가 큰 구현 조각을 분리할 때만 쓴다.
- `code-graph`를 쓰지 않는 세션에서도 이 프롬프트들은 그대로 사용할 수 있다.
