# GitLab Platform Implementation Roadmap

이 문서는 현재 기준 다음 구현 순서를 정리한다.

## Phase 0. 기반 정리

이미 완료된 것:

- platform task persistence DB 도입
- SQLAlchemy + Alembic 기반 시작
- `data/platform_state.db` 사용

아직 남은 것:

- `gitlab_instances`
- `gitlab_projects`
- audit log 기본 구조
- GitLab 연결 설정 모델
- control-plane repository / query 정리

## Phase 1. GitLab 프로젝트 인벤토리

다음 바로 할 일이다.

- GitLab `Projects API` 클라이언트
- 수동 sync API
- `System Hook` 수신
- 프로젝트 목록 UI
- 프로젝트 상태 `discovered`, `ready_for_bootstrap`

## Phase 2. 프로젝트 설정 / Bootstrap

- `.argus/project.yaml` 스키마
- manifest 검증
- `.gitlab-ci.yml` 생성 또는 include
- project webhook 등록
- 기본 CI 변수 생성
- 프로젝트 설정 화면

## Phase 3. Staging MVP

- environment 모델
- staging blueprint 1종
- VM 생성 orchestration
- PostgreSQL shared cluster 기반 DB 생성기
- GitLab 변수 upsert
- pipeline trigger

## Phase 4. 상태 동기화와 운영 액션

- pipeline/job/deployment webhook 수신
- environment 상태 머신
- `Redeploy`
- `Destroy`
- `Rotate DB Credentials`

## 권장 구현 순서

1. GitLab instance / project 모델
2. GitLab inventory sync
3. `System Hook`
4. 프로젝트 설정 화면
5. Bootstrap 자동화
6. Environment 모델
7. DB provisioner
8. `Deploy Staging`
9. pipeline / deployment 동기화
