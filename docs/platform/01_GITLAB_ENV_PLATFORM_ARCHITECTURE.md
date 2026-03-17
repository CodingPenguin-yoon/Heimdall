# GitLab Environment Platform Architecture

이 문서는 현재 Proxmox 자동화 플랫폼을 "개발자 셀프서비스 환경 플랫폼"으로 확장하기 위한 목표 구조를 정리한다.

기준 시나리오:

- 개발자가 GitLab 웹에서 새 프로젝트를 만든다.
- 이 플랫폼이 해당 프로젝트를 자동 감지하고 레포지토리 목록에 반영한다.
- 사용자가 이 플랫폼 웹에서 `Deploy Staging` 같은 버튼을 누른다.
- 플랫폼이 VM, DB, secret, GitLab 변수, 파이프라인 실행까지 오케스트레이션한다.
- 사용자는 GitLab CI/CD 와 이 플랫폼 웹 둘 다에서 상태를 확인할 수 있다.

이 문서는 "현재 구현"이 아니라 "다음 단계의 목표 설계"다.

## 1. 목표

이 프로젝트의 역할을 다음처럼 확장한다.

- 현재: Proxmox 템플릿 기반 VM 생성 + Ansible 후처리
- 목표: GitLab 프로젝트 기반 환경 온보딩 + VM/DB/secret/CI 파이프라인 오케스트레이션

핵심 목표:

- GitLab 프로젝트 자동 수집
- 프로젝트별 표준 온보딩
- `dev`, `staging`, `prod` 환경 생성/재배포/삭제
- DB 자동 생성 및 연결 정보 주입
- GitLab 파이프라인과 이 플랫폼 상태를 한 화면에서 추적

## 2. 북극성 사용자 흐름

```text
개발자
  -> GitLab 에서 프로젝트 생성
  -> 플랫폼 UI 에 프로젝트가 자동 표시됨
  -> "Bootstrap Project" 클릭
  -> 플랫폼이 CI 템플릿/변수/웹훅/기본 환경을 준비
  -> "Deploy Staging" 클릭
  -> 플랫폼이 VM + DB + secret + GitLab pipeline 실행
  -> GitLab Runner 가 빌드/테스트/배포 수행
  -> 플랫폼 UI 에 환경 상태, URL, 최근 배포, 연결 리소스 표시
```

## 3. 현재 코드에서 재사용할 자산

이 저장소는 이미 아래 자산을 갖고 있다.

- Proxmox 리소스 조회 서비스
- Terraform 기반 VM 클론 생성
- Ansible 기반 초기 호스트 설정
- SSE 기반 작업 추적
- React 기반 운영 UI
- LLM 어시스턴트 인터페이스

재사용 대상:

- `backend/app/services/proxmox/__init__.py`
- `backend/app/services/deployment/service.py`
- `backend/app/services/terraform/__init__.py`
- `backend/app/services/ansible/__init__.py`
- `backend/app/services/task/manager.py`
- `frontend/src/components/TaskBoard.jsx`

즉 새 플랫폼은 "처음부터 다시 만드는 것"이 아니라, 현재 배포 엔진 위에 GitLab/환경/DB 계층을 얹는 방향이 맞다.

## 4. 제안 아키텍처

```text
GitLab Web UI
  -> GitLab
     -> System Hook / Project Hook
        -> This Platform (FastAPI)
           -> Platform DB
           -> Secret Store
           -> Proxmox / Terraform / Ansible
           -> Database Provisioner
           -> GitLab API
     -> GitLab Runner
        -> Build/Test/Package/Deploy jobs

React Frontend
  -> This Platform API
     -> Task SSE
     -> Project catalog
     -> Environment actions
```

### 4.1 역할 분리

- GitLab
  - 코드 저장소
  - CI/CD control plane
  - pipeline / job / deployment 상태의 공식 소스

- 이 플랫폼
  - 환경 오케스트레이터
  - 인프라 및 DB 프로비저너
  - GitLab 자동화 조정자
  - 개발자 셀프서비스 포털

- GitLab Runner
  - 실제 빌드 및 앱 배포 실행자
  - build runner 와 deploy runner 를 분리 가능

- Proxmox / Terraform / Ansible
  - VM 생성과 OS 초기 세팅 담당

- DB Provisioner
  - 프로젝트/환경별 DB 생성
  - 사용자/권한 생성
  - 접속 문자열 생성

## 5. 핵심 설계 원칙

### 5.1 GitLab 은 파이프라인의 control plane

빌드/테스트/배포 job 자체는 GitLab 이 추적한다. 이 플랫폼은 그 job 을 만들고, 필요한 인프라와 변수를 공급한다.

### 5.2 DB 자동화는 이 플랫폼이 담당

DB 생성과 계정/권한 부여는 GitLab 이 아니라 이 플랫폼이 수행한다. GitLab 에는 결과물인 환경별 접속 정보만 전달한다.

### 5.3 템플릿 기반 VM 은 유지

현재 표준인 `템플릿 클론 -> Terraform -> Ansible` 흐름은 유지한다. 환경 배포는 이 엔진을 더 큰 워크플로우 안에 포함시키는 방식으로 확장한다.

### 5.4 프로젝트별 표준화는 Manifest 로 강제

모든 프로젝트가 서로 다른 언어/빌드/배포 방식을 갖기 때문에, 완전 자동화를 위해서는 저장소 안에 최소한의 선언형 메타데이터가 필요하다.

권장 파일:

- `.argus/project.yaml`

예시:

```yaml
project_type: webapp
runtime: node
build:
  command: npm ci && npm run build
deploy:
  type: docker-compose
  healthcheck_path: /health
  app_port: 3000
database:
  engine: postgres
  required: true
  schema_strategy: database-per-environment
environment_defaults:
  staging:
    blueprint: web-small
  production:
    blueprint: web-medium
```

Manifest 가 없으면 최소 read-only 프로젝트 인벤토리까지만 허용하고, 완전 자동 배포는 막는 것이 맞다.

## 6. 새로 필요한 백엔드 도메인

현재 도메인은 `deploy`, `task`, `proxmox`, `llm` 뿐이다. 아래 도메인을 추가하는 것이 맞다.

### 6.1 `gitlab`

역할:

- GitLab 프로젝트 동기화
- 프로젝트 bootstrap
- 변수/웹훅/파일/파이프라인 API 호출

예상 파일:

```text
backend/app/domains/gitlab/router.py
backend/app/services/gitlab/client.py
backend/app/services/gitlab/sync_service.py
backend/app/services/gitlab/bootstrap_service.py
backend/app/services/gitlab/pipeline_service.py
```

### 6.2 `environments`

역할:

- 환경 정의
- 환경 생성/재배포/삭제
- VM/DB/GitLab 파이프라인 전체 오케스트레이션

예상 파일:

```text
backend/app/domains/environments/router.py
backend/app/services/environments/orchestrator.py
backend/app/services/environments/blueprint_service.py
backend/app/services/environments/secret_mapping.py
```

### 6.3 `database`

역할:

- DB 엔진별 프로비저닝
- 사용자/권한 생성
- connection string 생성
- 폐기 시 계정/DB 정리

예상 파일:

```text
backend/app/domains/database/router.py
backend/app/services/database/base.py
backend/app/services/database/postgres.py
backend/app/services/database/mysql.py
```

### 6.4 `webhooks`

역할:

- GitLab system hook 수신
- pipeline/job/deployment event 수신
- 상태 동기화

예상 파일:

```text
backend/app/domains/webhooks/router.py
backend/app/services/webhooks/gitlab_system_hook.py
backend/app/services/webhooks/gitlab_project_hook.py
```

### 6.5 `platform`

역할:

- GitLab 연결 설정
- secret store 연결
- 기본 blueprint 관리
- 조직/그룹 단위 정책

## 7. 새로 필요한 프론트엔드 화면

현재 화면은 `Create Instance`, `Task Board`, `Monitoring`, `LLM Assistant` 중심이다. 아래 화면이 추가되어야 한다.

### 7.1 Projects

- GitLab 에서 수집된 프로젝트 목록
- onboarding 상태
- bootstrap 여부
- 마지막 pipeline 상태

### 7.2 Project Detail

- 프로젝트 manifest 상태
- GitLab 기본 정보
- 연결된 환경 목록
- 환경별 최근 배포/리소스/URL

### 7.3 Environment Detail

- VM 정보
- DB 정보
- GitLab pipeline/job 상태
- secret 주입 상태
- redeploy / suspend / destroy 버튼

### 7.4 Blueprints

- `web-small`, `web-medium`, `worker-small` 같은 환경 블루프린트 정의
- CPU, RAM, disk, DB 종류, runner tag, 배포 방식, 네트워크 정책 관리

## 8. Persistence 재설계

현재 `TaskManager` 는 메모리 + JSON 파일 기반이다. 이 구조는 단일 VM 생성에는 충분하지만, 멀티 프로젝트 환경 플랫폼에는 부족하다.

플랫폼 확장 전제:

- 작업 이력
- GitLab 프로젝트 메타데이터
- 환경 상태
- VM / DB / secret 매핑
- 파이프라인/배포 이벤트
- 감사 로그

를 저장할 정식 DB 가 필요하다.

권장:

- 플랫폼 내부 상태 저장용 Postgres 추가

필수 테이블 예:

- `gitlab_instances`
- `gitlab_projects`
- `project_manifests`
- `environment_blueprints`
- `environments`
- `environment_resources`
- `database_bindings`
- `gitlab_pipeline_runs`
- `gitlab_deployments`
- `audit_logs`

`task_history.json` 는 과도기 호환용으로만 남기고, 환경 플랫폼 단계에서는 DB 기반 저장으로 전환하는 것이 맞다.

## 9. GitLab 연동 모델

이 설계는 GitLab Self-Managed 를 중앙 control plane 으로 쓰는 것을 전제로 한다.

### 9.1 프로젝트 수집

우선순위:

1. GitLab `System Hook` 으로 `project_create` 감지
2. 주기적 `Projects API` 동기화로 누락 보정

플랫폼은 신규 프로젝트를 수신하면 다음을 수행한다.

- 프로젝트 메타데이터 저장
- 기본 onboarding 상태를 `discovered` 로 기록
- 기본 environment blueprint 후보 추천

### 9.2 프로젝트 bootstrap

Bootstrap 작업은 다음을 포함한다.

- `.argus/project.yaml` 존재 확인
- 없으면 기본 템플릿 제안 또는 생성
- `.gitlab-ci.yml` 생성 또는 중앙 템플릿 include 구성
- project webhook 등록
- 기본 CI/CD 변수 생성
- deploy runner tag 정책 연결

### 9.3 파이프라인 실행

환경 배포 시 플랫폼은 다음을 순서대로 수행한다.

1. 환경 입력 검증
2. VM 생성
3. DB 생성
4. secret 생성
5. GitLab 변수/파일/환경 갱신
6. `Pipelines API` 또는 trigger token 으로 pipeline 실행
7. GitLab webhook 으로 후속 상태 수신

## 10. DB 자동화 모델

이 플랫폼의 중요한 기능은 "개발자가 DB 를 직접 만들 필요가 없게 하는 것"이다.

### 10.1 권장 전략

- `dev`, `staging`
  - shared DB cluster 위에 environment 별 DB/user 생성
- `prod`
  - 별도 DB 인스턴스 또는 전용 DB 서버 사용

### 10.2 환경 배포 시 생성 대상

- DB 이름
- DB 사용자
- 강한 랜덤 패스워드
- 최소 권한
- `DATABASE_URL`
- 필요 시 migration 사용자와 app 사용자 분리

### 10.3 GitLab 으로 넘길 값

- `DATABASE_URL`
- `DB_HOST`
- `DB_PORT`
- `DB_NAME`
- `DB_USER`
- 필요한 애플리케이션 secret

DB 관리자 자격 증명은 GitLab 으로 넘기지 않는다. 이 플랫폼만 DB 관리자 권한을 가진다.

## 11. 보안 모델

### 11.1 권한 분리

- GitLab 관리자 토큰은 플랫폼만 사용
- 프로젝트 pipeline 에는 프로젝트 단위 또는 환경 단위 변수만 전달
- Proxmox API 토큰과 DB 관리자 비밀번호는 GitLab 으로 노출하지 않는다

### 11.2 Secret 저장

권장 우선순위:

1. 외부 secret manager 사용
2. 최소한 플랫폼 DB 에 암호화 저장

초기 MVP 는 암호화 저장으로 시작할 수 있지만, 운영 단계에서는 별도 secret manager 도입이 바람직하다.

### 11.3 Runner 분리

- `build-shared`
- `deploy-staging`
- `deploy-production`

처럼 runner 를 분리해야 blast radius 를 줄일 수 있다.

### 11.4 웹훅 검증

- GitLab webhook secret 검증
- idempotency key 처리
- 재전송 허용

## 12. 환경 상태 모델

환경은 단순한 "배포 버튼"이 아니라 상태 머신으로 다뤄야 한다.

예시 상태:

- `discovered`
- `bootstrapping`
- `bootstrap_failed`
- `ready`
- `provisioning`
- `provision_failed`
- `pipeline_running`
- `deployed`
- `degraded`
- `destroying`
- `destroyed`

플랫폼은 이 상태를 GitLab 파이프라인 상태와 VM/DB 실체 상태를 합쳐 계산해야 한다.

## 13. 워크플로우 설계

### 13.1 프로젝트 생성 감지

```text
GitLab project_create
  -> platform webhook
  -> save project metadata
  -> create default environment records
  -> show project in UI
```

### 13.2 Bootstrap Project

```text
User clicks Bootstrap
  -> validate project manifest
  -> write .gitlab-ci.yml or CI include
  -> create project webhook
  -> create base CI variables
  -> mark project ready
```

### 13.3 Deploy Staging

```text
User clicks Deploy Staging
  -> create environment task
  -> resolve blueprint + project manifest
  -> provision VM
  -> provision DB
  -> generate secrets
  -> upsert GitLab variables
  -> trigger pipeline on target ref
  -> receive pipeline/job/deployment events
  -> mark environment deployed
```

### 13.4 Destroy Environment

```text
User clicks Destroy
  -> stop app deployment
  -> revoke or rotate secrets
  -> delete DB/user
  -> destroy VM or archive VM
  -> mark environment destroyed
```

## 14. API 설계 초안

현재 API 스타일에 맞춰 `/api/*` 아래로 추가한다.

### 14.1 GitLab

- `GET /api/gitlab/projects`
- `POST /api/gitlab/sync`
- `GET /api/gitlab/projects/{project_id}`
- `POST /api/gitlab/projects/{project_id}/bootstrap`
- `GET /api/gitlab/projects/{project_id}/pipelines`

### 14.2 Environments

- `GET /api/projects/{project_id}/environments`
- `POST /api/projects/{project_id}/environments`
- `GET /api/environments/{environment_id}`
- `POST /api/environments/{environment_id}/deploy`
- `POST /api/environments/{environment_id}/redeploy`
- `POST /api/environments/{environment_id}/destroy`

### 14.3 Blueprints

- `GET /api/blueprints`
- `POST /api/blueprints`
- `PATCH /api/blueprints/{blueprint_id}`

### 14.4 Webhooks

- `POST /api/webhooks/gitlab/system`
- `POST /api/webhooks/gitlab/project/{project_id}`

### 14.5 Database

- `GET /api/environments/{environment_id}/database`
- `POST /api/environments/{environment_id}/database/rotate-credentials`

## 15. TaskManager 확장 방향

기존 `TaskManager` 는 여전히 유용하다. 다만 task 종류가 단일 VM 배포를 넘어 환경 워크플로우로 확장되어야 한다.

새 task 종류 예:

- `gitlab_sync`
- `project_bootstrap`
- `environment_provision`
- `database_provision`
- `pipeline_trigger`
- `environment_destroy`

또한 child step 개념이 필요하다.

예:

- `vm_provision`
- `db_provision`
- `gitlab_variable_upsert`
- `pipeline_run`

## 16. 권장 구현 순서

### Phase 1. GitLab 인벤토리

- GitLab 인스턴스 연결 설정
- `Projects API` 읽기
- `System Hook` 수신
- 프로젝트 목록 UI

### Phase 2. Bootstrap

- project manifest 검증
- `.gitlab-ci.yml` 자동화
- webhook / variables / runner tag 연결

### Phase 3. Staging MVP

- staging blueprint 하나 고정
- VM + DB + GitLab 변수 + pipeline 실행
- 배포 결과 상태 표시

### Phase 4. Destroy / Redeploy

- 환경 정리
- 자격 증명 rotation
- 재배포

### Phase 5. Production Hardening

- approval / runner 분리 / secret manager / audit 강화

## 17. 비목표

초기 설계에서 아래는 제외하는 것이 맞다.

- 멀티 클라우드 통합
- Kubernetes 기반 앱 오케스트레이션
- 범용 서비스 메시
- 모든 언어/프레임워크 자동 추론

처음에는 "웹 애플리케이션 + VM + PostgreSQL + GitLab CI" 범위로 좁히는 것이 좋다.

## 18. 즉시 필요한 결정

1. 플랫폼 자체 상태 저장 DB 를 무엇으로 둘지
2. secret manager 를 MVP 에서 바로 넣을지
3. 프로젝트 manifest 파일 이름과 스키마
4. staging DB 전략을 shared cluster 로 할지 별도 VM 으로 할지
5. pipeline bootstrap 을 direct commit 으로 할지 merge request 로 할지
6. deploy runner 를 환경별로 분리할지

## 19. 공식 참고 문서

- [GitLab System Hooks](https://docs.gitlab.com/administration/system_hooks/)
- [Projects API](https://docs.gitlab.com/api/projects/)
- [Repository Files API](https://docs.gitlab.com/api/repository_files/)
- [Project-level CI/CD Variables API](https://docs.gitlab.com/api/project_level_variables/)
- [Pipelines API](https://docs.gitlab.com/api/pipelines/)
- [Pipeline Triggers API](https://docs.gitlab.com/api/pipeline_triggers/)
- [Environments API](https://docs.gitlab.com/api/environments/)
- [Deployments API](https://docs.gitlab.com/api/deployments/)
- [Project Access Tokens API](https://docs.gitlab.com/api/project_access_tokens/)
