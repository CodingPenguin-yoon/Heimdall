# Platform Design Summary

이 문서는 어제부터 정리한 설계 방안을 한 번에 공유하기 위한 상위 요약이다.  
상세 구현 계획은 하위 문서를 본다.

관련 상세 문서:

- `01_GITLAB_ENV_PLATFORM_ARCHITECTURE.md`
- `02_IMPLEMENTATION_ROADMAP.md`
- `03_PROJECT_MANIFEST_SPEC.md`

## 1. 이 프로젝트의 정체성

이 프로젝트는 더 이상 단순한 "Proxmox VM 생성 웹 UI" 로만 보지 않는다.

목표 정체성:

- 개발자 셀프서비스 환경 플랫폼
- GitLab 프로젝트와 연결되는 배포 오케스트레이터
- VM / DB / secret / pipeline 을 함께 조정하는 control plane

즉 개발자는 GitLab 에 프로젝트를 만들고, 이 플랫폼에서는 `Bootstrap`, `Deploy Staging`, `Redeploy`, `Destroy` 같은 버튼만 누르면 된다.

## 2. 현재까지 닫힌 범위

현재 구현에서 사실상 마무리된 부분:

- VM 생성 경로는 템플릿 클론 기반으로 정리했다
- ISO 직접 생성 경로는 제거했다
- Ansible 후처리 경로는 유지했다
- 작업 상태 추적과 UI 기반 운영 흐름은 이미 존재한다

의미:

- 지금 있는 VM 생성 기능은 최종 목표의 하위 모듈이다
- 앞으로 프로젝트별 환경 자동 생성에서 재사용될 인프라 엔진이 된다

## 3. 왜 템플릿 기반으로 갔는가

운영 관점에서 VM 생성은 다음 구분이 맞다고 합의했다.

- ISO: 템플릿을 준비하는 데 사용하는 단계
- 앱 플랫폼: 준비된 템플릿을 클론해서 환경을 빠르게 만드는 단계

따라서 이 프로젝트는 템플릿 클론 기반 VM 생성만 책임진다.

## 4. Terraform / Ansible / GitLab 역할 분리

- Terraform
  - VM, 스토리지, 네트워크 같은 인프라 프로비저닝

- Ansible
  - 호스트 운영 표준화
  - Docker, Nginx, 런타임, 운영 패키지, agent, 사용자/권한 같은 서버 내부 상태를 맞춤

- GitLab
  - 코드 저장소
  - CI/CD pipeline control plane
  - 빌드/테스트/배포 기록의 공식 소스

- 이 플랫폼
  - GitLab 프로젝트 수집
  - 환경 오케스트레이션
  - VM 생성
  - DB 생성
  - secret 생성 및 주입
  - GitLab 변수/파이프라인 조정

핵심 합의:

- DB 자동화는 GitLab 이 아니라 이 플랫폼이 담당한다
- GitLab 은 "실행과 추적" 을 맡고, 이 플랫폼은 "무엇을 어떻게 만들지" 를 결정한다

## 5. 앞으로 만들 최종 사용자 흐름

```text
1. 개발자가 GitLab 웹에서 프로젝트 생성
2. 이 플랫폼이 프로젝트를 자동 감지해서 목록에 표시
3. 사용자가 프로젝트를 Bootstrap
4. 플랫폼이 manifest, CI 설정, webhook, 변수 등을 준비
5. 사용자가 Deploy Staging 클릭
6. 플랫폼이 VM + DB + secret + GitLab pipeline 실행
7. GitLab Runner 가 앱을 빌드/테스트/배포
8. 플랫폼 UI 에 환경 상태, URL, 리소스, 최근 배포 결과 표시
```

## 6. DB 도입에 대한 합의

두 종류의 DB 를 구분한다.

### 6.1 플랫폼 내부 DB

이 플랫폼 자신의 상태를 저장하는 DB 가 필요하다.

저장 대상:

- tasks
- gitlab_projects
- environments
- environment_resources
- gitlab_pipeline_runs
- audit_logs

개발 단계:

- SQLite 로 시작 가능

운영 단계:

- Postgres 로 전환

중요:

- 지금 DB 도입은 "서비스 앱용 DB" 가 아니라 "플랫폼 control-plane DB" 를 먼저 도입하는 것이다
- 가장 먼저 바꿔야 하는 곳은 `TaskManager` 의 파일 기반 persistence 이다

### 6.2 서비스 프로젝트용 DB

사용자 프로젝트가 staging / production 에서 쓸 DB 는 이 플랫폼이 별도로 자동 생성한다.

권장 모델:

- `dev`, `staging`: shared DB cluster 위에 environment 별 DB/user 생성
- `production`: 전용 DB 인스턴스 또는 별도 DB 서버 사용

## 7. GitLab 중심 운영 모델

합의된 방향:

- 앞으로 운영 자동화를 붙일 다른 프로젝트들은 GitLab 에 넣는다
- GitLab 은 중앙 control plane 으로 사용한다
- 이 플랫폼은 GitLab 과 Proxmox/DB 사이를 연결하는 오케스트레이터가 된다

즉 이 프로젝트의 최종 역할은:

- 수동 운영 UI
- 자동화 오케스트레이터

두 가지를 함께 갖는 것이다.

## 8. 현재 설계상 새로 필요한 백엔드 도메인

- `gitlab`
- `environments`
- `database`
- `webhooks`
- `platform`

현재 있는 `deploy`, `task`, `proxmox`, `llm` 위에 이 계층을 추가한다.

## 9. 현재 설계상 새로 필요한 프론트엔드 화면

- Projects
- Project Detail
- Environment Detail
- Blueprints

현재 있는 `Create Instance`, `Task Board`, `Monitoring`, `LLM Assistant` 는 유지하고, 운영 자동화 화면을 위에 얹는 방향이다.

## 10. 단계별 구현 우선순위

### Step 1

플랫폼 내부 상태 DB 도입

### Step 2

GitLab 프로젝트 인벤토리

- GitLab 프로젝트 읽기
- project_create 감지
- 프로젝트 목록 UI

### Step 3

프로젝트 Bootstrap

- `.argus/project.yaml`
- `.gitlab-ci.yml`
- webhook
- 기본 변수

### Step 4

Staging MVP

- staging blueprint 1종
- VM 생성
- DB 생성
- secret 생성
- GitLab 변수 주입
- pipeline 실행

### Step 5

상태 동기화 + Destroy / Redeploy / Credential Rotate

## 11. 가장 중요한 설계 판단

### 이미 결정된 것

- VM 생성은 템플릿 클론만 지원
- Ansible 은 계속 사용하되 "호스트 운영 표준화" 역할로 둔다
- GitLab 은 중앙 control plane 이다
- DB 자동화는 이 플랫폼이 수행한다
- 플랫폼 내부 상태 DB 는 먼저 도입한다
- 개발 단계 DB 는 SQLite 로 시작 가능하다

### 아직 결정이 필요한 것

- 플랫폼 내부 DB ORM / migration 도구
- secret manager 도입 시점
- project manifest 최종 필드
- staging DB 를 shared cluster 로 바로 갈지
- bootstrap 을 direct commit 으로 할지 merge request 로 할지

## 12. 지금 시점의 결론

이 프로젝트는 현재:

- 사람이 수동으로 VM 을 만들고 관리하는 운영 UI

이면서 동시에 앞으로는:

- 프로젝트별 개발/스테이징/운영 환경을 자동 생성하는 플랫폼

으로 확장된다.

즉 이번에 정리한 VM 생성 기능은 끝이 아니라, 앞으로 붙을 GitLab/DB/환경 오케스트레이션의 기반층이다.
