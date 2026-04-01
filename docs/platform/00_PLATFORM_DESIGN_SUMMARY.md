# Platform Design Summary

이 문서는 Heimdall 전달 방향의 현재 합의만 짧게 정리한다.

관련 문서:

- [01_GITLAB_ENV_PLATFORM_ARCHITECTURE.md](01_GITLAB_ENV_PLATFORM_ARCHITECTURE.md)
- [02_IMPLEMENTATION_ROADMAP.md](02_IMPLEMENTATION_ROADMAP.md)
- [03_PROJECT_MANIFEST_SPEC.md](03_PROJECT_MANIFEST_SPEC.md)
- [04_MVP_PHASE_PLAN.md](04_MVP_PHASE_PLAN.md)

## Delivery Direction

Heimdall 의 현재 전달 방향은 아래에 집중한다.

- 개발자 친화적인 서버 배포
- 서비스 DB 자동 연결
- `staging` 우선
- `docker-compose` 우선
- `postgres` 우선
- bootstrap 은 직접 반영보다 merge request 우선

즉 지금 문서의 MVP 는 “GitLab 프로젝트를 감지하고, 최소 manifest 초안을 merge request 로 제안하고, `staging` 에 대해 `docker-compose` 기반 서버 배포와 Postgres 자동 연결까지 이어지는 흐름”이다.

## Already Exists

아래 슬라이스는 이미 존재하는 자산으로 본다.

- GitLab inventory 관련 기본 방향
- GitLab settings 관련 기본 방향
- GitLab `System Hook` 관련 기본 방향

이 문서 묶음은 위 자산이 이미 있다는 전제 위에서, 당장 전달할 Heimdall MVP 계약을 더 좁게 다시 정리한다.

## MVP Contract

이번 MVP 에서 의도적으로 지원 범위를 좁힌다.

- 환경 범위는 `staging` 만 포함한다
- 배포 방식은 `docker-compose` 만 포함한다
- DB 엔진은 `postgres` 만 포함한다
- bootstrap 진입점은 merge request 기반 초안 생성으로 한정한다
- 앱 저장소 계약은 계획 중인 `.heimdall/project.yaml` 로 한정한다
- 실제 staging 배포 시작은 명시적 사용자 `Deploy Staging` 액션에서만 가능하다
- discovery, inventory sync, `System Hook`, bootstrap readiness, manifest validation 은 준비/적격 신호일 뿐 배포를 자동 시작하지 않는다

아래는 이번 MVP 범위 밖이다.

- bootstrap 자동 완성 전반
- `Deploy Staging` 전체 운영 경험 완성
- DB provisioner 완성
- pipeline trigger 완성
- production 배포 흐름
- reverse proxy / domain / TLS 자동화

위 항목은 제거가 아니라 future work 로 명시적으로 뒤로 민다.

## Scope Boundary

현재 문서 기준으로 Heimdall MVP 는 다음 질문에만 답하면 된다.

1. GitLab 프로젝트를 어떻게 staging 후보로 식별할 것인가
2. `.heimdall/project.yaml` 초안을 어떻게 merge request 로 제안할 것인가
3. staging 서버를 `docker-compose` 로 어떻게 띄울 것인가
4. Postgres 접속 정보를 어떻게 생성하고 앱에 어떻게 연결할 것인가

그 외 운영 고도화는 [02_IMPLEMENTATION_ROADMAP.md](02_IMPLEMENTATION_ROADMAP.md) 와 [04_MVP_PHASE_PLAN.md](04_MVP_PHASE_PLAN.md) 의 후속 단계로 둔다.
