# GitLab 중심 개발자 셀프서비스 환경 플랫폼

이 프로젝트는 최종적으로 **GitLab 중심 개발자 셀프서비스 환경 플랫폼**을 목표로 합니다.  
프로젝트별 `Bootstrap`, `Deploy Staging`, `Redeploy`, `Destroy` 같은 작업을 플랫폼 UI 에서 수행하고, 그 과정에서 **VM, DB, secret, pipeline** 을 함께 오케스트레이션하는 control plane 을 지향합니다.

현재 저장소는 그 최종 플랫폼을 향한 **기반 단계**입니다. 이미 구현된 Proxmox 템플릿 클론 VM 배포, Terraform/Ansible 연동, Task/SSE 추적, 운영 UI, LLM Assistant 는 모두 앞으로 붙을 GitLab/환경/DB 계층의 하위 모듈이자 재사용 엔진입니다.

중요:

- 이 README 는 **최종 목표 플랫폼 관점**에서 프로젝트를 설명합니다.
- `GitLab 인벤토리`, `Bootstrap`, `Deploy Staging`, `DB 자동 연결`, `pipeline/event 동기화`, `Redeploy`, `Destroy`, `Rotate DB Credentials`, `secret manager` 는 **현재 구현 완료 기능이 아니라 목표/로드맵** 입니다.
- 현재 구현된 기반은 아래 [현재 구현된 기반](#현재-구현된-기반) 섹션에서 별도로 설명합니다.

## 이 프로젝트가 최종적으로 지향하는 것

이 플랫폼의 최종 정체성은 더 이상 "Proxmox VM 생성 웹 UI"가 아닙니다.

목표 정체성:

- GitLab 프로젝트와 연결되는 개발자 셀프서비스 환경 플랫폼
- VM / DB / secret / pipeline 을 함께 조정하는 배포 오케스트레이터
- 환경 상태, 배포 결과, 연결 리소스를 한 화면에서 다루는 운영 control plane

최종적으로는 개발자가 GitLab 에 프로젝트를 만들면, 플랫폼은 그 프로젝트를 감지하고 표준화한 뒤 아래 액션을 제공하는 형태를 목표로 합니다.

- `Bootstrap`
- `Deploy Staging`
- `Redeploy`
- `Destroy`
- `Rotate DB Credentials`

초기 범위는 넓게 잡지 않습니다.  
이 플랫폼의 우선 목표 범위는 **웹 애플리케이션 + VM + PostgreSQL + GitLab CI** 입니다. 멀티 클라우드, Kubernetes, 범용 오케스트레이션 플랫폼을 바로 지향하지 않습니다.

## 왜 이 플랫폼이 필요한가

이 프로젝트가 해결하려는 문제는 "VM 하나 만드는 자동화" 자체보다 더 큽니다.

실제 운영에서 반복적으로 발생하는 문제:

- 프로젝트마다 인프라 준비 방식이 다르고 수동 단계가 많다.
- GitLab 프로젝트 생성 이후 환경 준비가 사람 지식에 의존한다.
- VM 생성, DB 생성, secret 관리, CI 변수 주입, pipeline 실행이 서로 다른 도구와 사람 손을 거친다.
- 배포 상태의 공식 소스가 GitLab, VM 상태, 운영 메모로 흩어져 있다.
- 운영자가 직접 DB 를 만들고 연결 정보를 전달하는 구조는 느리고 위험하다.

이 플랫폼이 필요한 이유:

- 프로젝트 온보딩을 표준화할 수 있다.
- 환경 생성과 배포를 버튼 중심 워크플로우로 줄일 수 있다.
- DB 자동 생성과 연결 정보 주입을 플랫폼이 대신 처리할 수 있다.
- GitLab pipeline 상태와 실제 환경 상태를 함께 추적할 수 있다.
- 현재의 VM 배포 엔진을 재사용해 더 큰 플랫폼으로 확장할 수 있다.

## 북극성 사용자 흐름

아래 흐름은 **최종 목표 사용자 흐름**입니다.

```text
1. 개발자가 GitLab 웹에서 프로젝트 생성
2. 플랫폼이 프로젝트를 자동 감지해 목록에 표시
3. 사용자가 Bootstrap 실행
4. 플랫폼이 manifest, CI 설정, webhook, 기본 변수 준비
5. 사용자가 Deploy Staging 클릭
6. 플랫폼이 VM + DB + secret + GitLab pipeline 을 함께 오케스트레이션
7. GitLab Runner 가 빌드/테스트/배포 수행
8. 플랫폼 UI 와 GitLab 양쪽에서 환경 상태, URL, 최근 배포 결과 추적
```

이 흐름에서 중요한 점:

- GitLab 은 코드 저장소이자 CI/CD control plane 입니다.
- 이 플랫폼은 "무엇을 어떻게 만들지" 를 결정하는 오케스트레이터 입니다.
- VM 생성은 최종 목표의 일부일 뿐이고, DB/secret/pipeline 까지 포함해야 비로소 완성된 환경 플랫폼이 됩니다.

## 목표 아키텍처와 역할 분리

아래는 **목표 아키텍처**입니다.

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
        -> Build / Test / Package / Deploy jobs

React Frontend
  -> This Platform API
     -> Project catalog
     -> Environment actions
     -> Task SSE
```

### GitLab

목표 역할:

- 코드 저장소
- CI/CD control plane
- pipeline / job / deployment 상태의 공식 소스

### 이 플랫폼

목표 역할:

- 프로젝트 인벤토리 수집기
- 환경 오케스트레이터
- VM / DB / secret 프로비저닝 조정자
- GitLab 자동화 조정자
- 개발자 셀프서비스 포털

### Proxmox / Terraform / Ansible

목표 역할:

- Proxmox: 실제 가상화 리소스 제공
- Terraform: VM, 스토리지, 네트워크 프로비저닝
- Ansible: 호스트 운영 표준화, 런타임/패키지/서비스 후처리

### DB Provisioner

목표 역할:

- 프로젝트/환경별 DB 생성
- DB 사용자와 권한 생성
- 접속 문자열 생성
- 폐기 시 계정/DB 정리

### Secret Store

목표 역할:

- 환경별 secret 저장
- 앱용 secret 과 관리자급 secret 분리
- 장기적으로는 외부 secret manager 도입

### GitLab Runner

목표 역할:

- 실제 빌드/테스트/배포 실행자
- 장기적으로 `build-shared`, `deploy-staging`, `deploy-production` 같은 분리 정책 적용

## 목표 기능 구성

아래 항목은 **최종 플랫폼 기준의 목표 기능 구성**입니다. 현재 구현 완료 기능으로 읽으면 안 됩니다.

### 1. GitLab 프로젝트 인벤토리

목표:

- GitLab `Projects API` 기반 프로젝트 목록 수집
- `System Hook` 으로 `project_create` 감지
- 수동 sync 로 누락 보정
- 프로젝트 상태를 `discovered`, `ready_for_bootstrap` 등으로 관리

결과적으로 플랫폼은 GitLab 에서 생긴 프로젝트를 자동으로 보여 주고, 어떤 프로젝트가 배포 준비가 되었는지 한 화면에서 관리해야 합니다.

### 2. Bootstrap 자동화

목표:

- 프로젝트를 배포 가능한 표준 형태로 맞춤
- `.argus/project.yaml` 존재 여부 확인 및 검증
- `.gitlab-ci.yml` 생성 또는 중앙 템플릿 include 구성
- project webhook 등록
- 기본 CI/CD 변수 생성

중요:

- `.argus/project.yaml` 은 **표준화에 사용할 예정인 선언형 manifest** 입니다.
- 현재 구현 완료 기능이 아닙니다.
- direct commit 으로 넣을지, merge request 로 제안할지는 아직 결정이 남아 있습니다.

### 3. Environment 오케스트레이션

목표:

- `dev`, `staging`, `prod` 환경 단위 관리
- `Deploy Staging` 버튼 한 번으로 환경 준비
- blueprint 와 manifest 를 조합해 환경 생성 결정
- VM / DB / secret / pipeline 을 하나의 작업 흐름으로 연결

핵심은 단순 VM 생성이 아니라 **환경 전체**를 오케스트레이션하는 것입니다.

### 4. DB 자동 연결

목표:

- 플랫폼이 환경별 DB 이름, 사용자, 강한 랜덤 비밀번호를 생성
- `DATABASE_URL`, `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER` 를 계산
- 필요 시 migration 사용자와 app 사용자 분리
- `dev`, `staging` 은 shared DB cluster 기반, `prod` 는 전용 DB 전략 검토

가장 중요한 보안 경계:

- **DB 관리자 자격 증명은 플랫폼만 보유합니다.**
- GitLab 에는 **환경별 연결 정보와 앱용 secret 만 전달**합니다.
- 즉 GitLab 으로 전달되는 값은 `DATABASE_URL`, `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, 그리고 필요한 애플리케이션 secret 수준이어야 합니다.
- Proxmox API 토큰, GitLab 관리자 토큰, DB 관리자 비밀번호를 GitLab 에 넘기는 구조를 목표로 하지 않습니다.

### 5. Secret 처리와 GitLab 변수 주입

목표:

- 환경별 secret 생성
- GitLab project/environment 변수 upsert
- app 용 secret 과 관리자급 secret 분리
- 장기적으로 외부 secret manager 사용

주의:

- secret manager 도입은 **권장 방향**이지만 아직 구현 방식이 확정된 것은 아닙니다.
- MVP 단계에서는 플랫폼 DB 암호화 저장으로 시작할 가능성이 열려 있습니다.

### 6. Pipeline 실행과 상태 동기화

목표:

- `Pipelines API` 또는 trigger token 으로 pipeline 실행
- GitLab project hook / webhook 으로 pipeline, job, deployment event 수신
- 플랫폼 상태와 GitLab 상태를 함께 계산
- 환경 상태 머신 운영

예상 환경 상태:

- `discovered`
- `bootstrapping`
- `ready`
- `provisioning`
- `pipeline_running`
- `deployed`
- `degraded`
- `destroying`
- `destroyed`

### 7. Blueprints 와 정책

목표:

- `web-small`, `web-medium`, `worker-small` 같은 blueprint 관리
- CPU, RAM, disk, DB 종류, runner tag, 네트워크 정책 관리
- 프로젝트 유형과 환경 기본값을 선언형으로 연결

### 8. 운영 액션과 Production Hardening

목표:

- `Redeploy`
- `Destroy`
- `Rotate DB Credentials`
- runner 분리
- webhook secret 검증
- approval / 권한 정책 강화
- audit trail / change history 강화

## Manifest 계획

`.argus/project.yaml` 은 **프로젝트 표준화에 사용할 예정인 선언형 manifest** 입니다.

목표 역할:

- 프로젝트 타입 식별
- runtime 식별
- build / deploy 방식 정의
- DB 필요 여부와 엔진 정의
- 환경별 기본 blueprint 정의

대표적으로 아래 성격의 정보를 담게 됩니다.

- `project_type`
- `runtime`
- `build.command`
- `deploy.strategy`
- `deploy.app_port`
- `deploy.healthcheck_path`
- `database.required`
- `database.engine`
- `database.mode`
- `environment_defaults`

이 manifest 가 없으면 장기적으로는 read-only 인벤토리까지만 허용하고, 완전 자동화는 막는 구조가 적절합니다.

## 남은 작업과 단계별 로드맵

아래는 현재 문서 기준으로 정리된 **주요 남은 작업**입니다.

### 작업 범주

- 플랫폼 내부 상태 DB 도입
- GitLab 프로젝트 인벤토리와 sync / system hook
- Bootstrap 자동화
- 환경 오케스트레이션
- DB 자동 생성 및 연결 정보 주입
- secret 생성 및 관리
- GitLab 변수 주입과 pipeline trigger
- pipeline/job/deployment event 상태 동기화
- `Redeploy`, `Destroy`, `Rotate DB Credentials`
- blueprint 와 환경 정책
- production hardening

### Phase 0. 기반 정리

목표:

- 플랫폼 내부 상태 저장용 DB 도입
- ORM 또는 repository 계층 추가
- GitLab 연결 설정 구조 추가
- audit log 기본 구조 추가

이 단계는 현재 `TaskManager` 의 파일 기반 persistence 를 대체할 준비 단계입니다.

### Phase 1. GitLab 프로젝트 인벤토리

목표:

- `Projects API` 읽기 클라이언트 추가
- 수동 sync API 추가
- `System Hook` 수신 엔드포인트 추가
- 프로젝트 목록 UI 추가

### Phase 2. 프로젝트 Bootstrap

목표:

- `.argus/project.yaml` 스키마 정의
- manifest 검증기 추가
- `.gitlab-ci.yml` 생성 또는 include 자동화
- webhook 자동 등록
- 기본 CI 변수 생성
- 프로젝트 상세 화면 추가

### Phase 3. Staging MVP

목표:

- staging blueprint 1종 정의
- 환경 생성 API 추가
- VM 생성 orchestration 추가
- PostgreSQL shared cluster 기반 DB 생성기 추가
- GitLab 변수 upsert 로직 추가
- pipeline trigger 로직 추가

완료 기준 관점:

- 버튼 한 번으로 staging VM + DB + pipeline 실행
- 플랫폼에서 VM/DB/pipeline 상태 확인 가능

### Phase 4. 상태 동기화와 정리

목표:

- GitLab pipeline / job / deployment event 수신
- 환경 상태 머신 구현
- `Redeploy`, `Destroy`, `Rotate DB Credentials`
- child step 기반 task 표시 강화

### Phase 5. Production 하드닝

목표:

- runner 분리
- secret manager 도입
- 환경별 승인/권한 모델 강화
- production 전용 blueprint 추가
- audit trail / change history 고도화

### 아직 결정이 필요한 항목

문서상 아직 열려 있는 결정:

- 플랫폼 내부 DB 방식과 ORM / migration 도구
- secret manager 도입 시점
- bootstrap 을 direct commit 으로 할지 merge request 로 할지
- staging DB 를 shared cluster 로 갈지 별도 인스턴스로 갈지
- runner 분리 정책을 어디까지 적용할지

## 현재 구현된 기반

아래는 **현재 저장소에 이미 구현되어 있어 최종 플랫폼의 기반이 되는 부분**입니다.

### 1. 템플릿 클론 기반 VM 배포 엔진

- Proxmox 템플릿 기반 VM 생성
- Terraform 기반 프로비저닝
- 현재 VM 생성은 템플릿 클론 경로만 지원

### 2. Ansible 후처리

- VM 생성 후 기본 패키지/역할 적용
- 호스트 운영 표준화의 기반

### 3. TaskManager + SSE

- 작업 상태와 로그 추적
- UI 에서 실시간 진행률 확인
- 최종적으로는 더 큰 환경 워크플로우 task 로 확장 예정

### 4. React 운영 UI

- Create Instance
- Task Board
- Monitoring
- LLM Assistant

이 화면들은 장기적으로 Projects / Project Detail / Environment Detail / Blueprints 화면 위에 얹히는 기반이 됩니다.

### 5. LLM Assistant

- 현재도 동일 배포 엔진의 보조 진입점 역할 수행
- 장기적으로는 더 넓은 환경 운영 보조로 확장 가능

즉 지금 저장소는 "새 플랫폼을 처음부터 만드는 빈 껍데기"가 아니라,  
**템플릿 클론 VM 배포 + Ansible 후처리 + Task/SSE + 운영 UI** 가 이미 구현된 상태에서 GitLab/환경/DB 계층을 추가해 가는 구조입니다.

## 핵심 문서 안내

최종 비전과 남은 작업을 이해하려면 아래 문서를 우선 보는 것이 가장 정확합니다.

### 최종 목표와 설계

- [docs/platform/00_PLATFORM_DESIGN_SUMMARY.md](./docs/platform/00_PLATFORM_DESIGN_SUMMARY.md)
- [docs/platform/01_GITLAB_ENV_PLATFORM_ARCHITECTURE.md](./docs/platform/01_GITLAB_ENV_PLATFORM_ARCHITECTURE.md)
- [docs/platform/02_IMPLEMENTATION_ROADMAP.md](./docs/platform/02_IMPLEMENTATION_ROADMAP.md)
- [docs/platform/03_PROJECT_MANIFEST_SPEC.md](./docs/platform/03_PROJECT_MANIFEST_SPEC.md)

### 현재 구현 기반

- [docs/README.md](./docs/README.md)
- [docs/LOCAL_RUN_GUIDE.md](./docs/LOCAL_RUN_GUIDE.md)
- [docs/backend/01_OVERVIEW.md](./docs/backend/01_OVERVIEW.md)
- [docs/backend/02_ARCHITECTURE.md](./docs/backend/02_ARCHITECTURE.md)
- [docs/backend/03_API_ENDPOINTS.md](./docs/backend/03_API_ENDPOINTS.md)
- [docs/backend/05_DEPLOYMENT_FLOW.md](./docs/backend/05_DEPLOYMENT_FLOW.md)
- [docs/ANSIBLE_AUTOMATION.md](./docs/ANSIBLE_AUTOMATION.md)

현재 저장소 실행 방법이 필요하면 README 보다 [docs/LOCAL_RUN_GUIDE.md](./docs/LOCAL_RUN_GUIDE.md) 를 우선 보는 편이 맞습니다.

## 정리

이 프로젝트의 최종 목표는 **GitLab 프로젝트를 기준으로 환경을 자동 온보딩하고, VM / DB / secret / pipeline 을 함께 오케스트레이션하는 개발자 셀프서비스 환경 플랫폼** 입니다.

현재 구현은 그 최종 목표의 기반 엔진입니다.  
즉 지금 있는 Proxmox 템플릿 클론 배포, Terraform/Ansible 흐름, Task/SSE 추적, 운영 UI 는 끝이 아니라, 앞으로 붙을 GitLab 인벤토리, Bootstrap, DB 자동 연결, 상태 동기화, production hardening 의 토대입니다.
