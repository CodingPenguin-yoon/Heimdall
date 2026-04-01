# GitLab Environment Platform Architecture

이 문서는 Heimdall MVP 를 기준으로 GitLab 중심 환경 플랫폼 구조를 다시 좁혀 설명한다.

관련 문서:

- [00_PLATFORM_DESIGN_SUMMARY.md](00_PLATFORM_DESIGN_SUMMARY.md)
- [02_IMPLEMENTATION_ROADMAP.md](02_IMPLEMENTATION_ROADMAP.md)
- [03_PROJECT_MANIFEST_SPEC.md](03_PROJECT_MANIFEST_SPEC.md)

## Architectural Intent

이번 아키텍처의 목적은 “staging-first 개발자 배포 경로”를 만드는 것이다.

흐름은 아래로 제한한다.

1. GitLab 프로젝트를 inventory 에서 확인
2. merge request 로 `.heimdall/project.yaml` 초안을 제안
3. 사용자가 초안을 검토하고 병합
4. 플랫폼이 `staging` 대상 서버 배포를 준비
5. Postgres 접속 정보를 자동 생성하고 앱과 연결
6. 이후 `Deploy Staging` 으로 이어질 수 있는 최소 기반을 남김

여기서 discovery, inventory sync, GitLab `System Hook`, bootstrap readiness, manifest validation 은 모두 staging 배포 적격성이나 준비 상태를 갱신하는 신호로만 취급한다. 실제 staging 배포는 명시적 사용자 `Deploy Staging` 액션이 있을 때만 시작한다.

즉 이번 문서의 초점은 “모든 환경 자동화”가 아니라 `staging` 단일 경로를 먼저 닫는 것이다.

## Existing Slices To Reuse

이미 있다고 보는 슬라이스:

- GitLab inventory 방향
- GitLab settings 방향
- GitLab `System Hook` 방향

이 슬라이스들은 재설계 대상이 아니라 재사용 대상이다. 이번 MVP 에서는 이 기반을 이용해 merge-request bootstrap 과 staging 경로를 얹는다.

## MVP System Boundary

### GitLab

GitLab 은 이번 MVP 에서 아래 역할만 맡는다.

- 프로젝트 inventory 의 원천
- merge request bootstrap 전달 채널
- 필요한 CI/CD 변수 저장 위치

### Heimdall Platform

Heimdall 은 아래를 담당한다.

- staging 후보 프로젝트 식별
- 계획 중인 `.heimdall/project.yaml` 계약 검증
- `docker-compose` 배포 전제 확인
- Postgres 연결 정보 생성과 주입
- staging 배포 오케스트레이션을 위한 상태 기록
- 준비 신호와 실제 `Deploy Staging` 실행 진입점 구분

### Target Server

타겟 서버는 아래 전제를 가진다.

- 앱은 `docker-compose` 로 실행된다
- 앱은 Postgres 연결 문자열을 받아 기동한다
- reverse proxy, domain, TLS 는 이번 MVP 범위에 포함하지 않는다

## Planned Control-Plane Data

플랫폼 내부 DB 는 이미 시작된 기반 위에 아래 제어 평면 데이터를 추가하는 방향이다.

- GitLab 프로젝트 inventory 상태
- bootstrap 제안 상태
- staging 환경 메타데이터
- Postgres 연결 리소스 메타데이터
- 배포 실행 이력

중요한 점은 두 종류의 DB 를 구분하는 것이다.

- 플랫폼 내부 DB: Heimdall control-plane 상태 저장
- 서비스용 Postgres DB: 앱 런타임 연결 대상

## Deferred Architecture

아래는 구조적으로 필요하지만 이번 MVP 에서는 future work 로 둔다.

- bootstrap 전체 자동화
- `Deploy Staging` 완성형 UX
- DB provisioner 완성형 운영 모델
- pipeline trigger 완성형 동작
- production 환경 분기
- reverse proxy / domain / TLS 자동화

이 분리는 의도적이다. 구현 계약은 [04_MVP_PHASE_PLAN.md](04_MVP_PHASE_PLAN.md) 에서 더 세밀하게 다룬다.
