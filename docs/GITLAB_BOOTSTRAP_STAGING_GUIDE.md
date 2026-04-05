# GitLab Bootstrap And Staging Guide

이 문서는 현재 Heimdall 코드 기준으로 GitLab Workspace 를 어떻게 써야 하는지 설명한다.

핵심부터 먼저 정리하면 아래와 같다.

- GitLab merge 만으로 VM 이 자동 생성되지는 않는다
- GitLab System Hook 이 와도 현재는 inventory sync 만 자동 반영한다
- `Ready for bootstrap`, manifest validation, bootstrap strategy 는 준비 상태를 저장하는 용도다
- 실제 staging VM 생성은 사용자가 GitLab Workspace 에서 `Deploy Staging` 버튼을 눌러야 시작된다
- 현재 `Deploy Staging` 은 manual staging app deploy 이다
- 즉 VM/Terraform/Ansible 뒤에 GitLab archive 기반 앱 `docker-compose` 배포와 HTTP healthcheck 까지 연결된다. DB 자동화는 아직 없다

## 1. 지금 자동으로 되는 것과 안 되는 것

### 자동으로 되는 것

- GitLab inventory 를 수동 sync 할 수 있다
- GitLab System Hook 이 들어오면 inventory sync 를 트리거할 수 있다
- `.heimdall/project.yaml` 최소 검증 상태를 GitLab Workspace 에서 보여준다
- 이 웹에서 새 GitLab repo 를 만들고 `README 초기화`를 켜면 기본 `.heimdall/project.yaml` draft를 함께 넣는다
- 다만 이 draft 는 의도적으로 불완전하며 `deploy.compose_file`, `deploy.app_port`, `deploy.healthcheck_path` 를 채우기 전에는 `valid` 가 되지 않는다

### 자동으로 안 되는 것

- GitLab merge 후 자동 bootstrap
- GitLab merge 후 자동 VM 생성
- valid manifest 가 생겼다고 자동 staging 배포 시작
- database 자동 생성과 `DATABASE_URL` 주입
- GitLab merge/webhook 기반 자동 재배포

즉 현재 구조는 `GitLab 정보를 읽고 준비 상태를 판단하는 control-plane` 과 `명시적 수동 Deploy Staging 버튼` 이 분리돼 있다.

## 2. bootstrap 이 현재 의미하는 것

현재 코드에서 bootstrap 은 `프로젝트를 Heimdall staging 후보로 등록하기 위한 준비 상태`에 가깝다.

실제로는 아래를 뜻한다.

1. 이 프로젝트를 staging 대상으로 볼 것인지 결정
2. 프로젝트 설정을 저장
3. `.heimdall/project.yaml` 을 저장소에 추가
4. manifest 검증이 `valid` 가 되도록 맞춤
5. staging 인프라 프로필을 저장
6. 그 다음에 사람이 `Deploy Staging` 을 눌러 실제 staging 인프라와 앱 배포 시작

중요한 점:

- 현재 bootstrap 자동 실행 기능은 없다
- `bootstrap_strategy` 도 아직 실행 엔진이 아니라 `의도 저장값` 이다
- `merge_request`, `direct_commit`, `manual` 중 무엇을 고르든 현재는 버튼/설정 상태에만 남고, 실제 MR 생성이나 커밋 실행은 하지 않는다

## 3. 시작 전 준비물

아래가 준비돼 있어야 한다.

- 루트 `.env` 에 GitLab 설정
- backend migration 적용
- Proxmox 에 clone 가능한 템플릿 존재
- 템플릿에서 cloud-init 동작
- SSH 공개키 주입 가능
- DHCP 환경이면 가능하면 `qemu-guest-agent` 포함

필수 GitLab 환경변수 예시는 아래다.

- `GITLAB_BASE_URL`
- `GITLAB_API_TOKEN`
- `GITLAB_VERIFY_SSL`
- `GITLAB_DEFAULT_NAMESPACE_PATH`
- `GITLAB_SYSTEM_HOOK_SECRET`
- `PLATFORM_PUBLIC_BASE_URL`

로컬 실행 기준 준비 절차는 [LOCAL_RUN_GUIDE.md](/Users/yoon/project/proxmox_web/docs/LOCAL_RUN_GUIDE.md) 를 본다.

## 4. 실제 운영 순서

### Step 1. GitLab inventory 를 sync 한다

GitLab Workspace 에서 먼저 프로젝트 목록이 들어와야 한다.

방법:

- 수동으로 `Sync inventory`
- 또는 GitLab System Hook 등록 후 hook 으로 inventory 반영

이 단계에서 하는 일:

- GitLab 프로젝트 목록을 Heimdall DB 에 저장
- 프로젝트 메타데이터를 UI 에 표시
- manifest 상태 조회 기반을 마련

이 단계만으로는 bootstrap 도 deploy 도 시작되지 않는다.

### Step 2. 대상 프로젝트의 Project Setup 을 연다

각 프로젝트에서 `Open setup` 을 열면 설정을 저장할 수 있다.

여기서 입력하는 값은 두 종류다.

- control-plane 준비 상태
- 실제 staging VM 프로비저닝 입력값

## 5. Project Setup 항목 설명

### 5-1. Enable staging flow

의미:

- 이 프로젝트를 나중에 staging 대상으로 다룰지 표시

현재 동작:

- `Deploy Staging` 의 선행 조건이다
- 꺼져 있으면 `Ready for bootstrap` 도 의미가 없다

권장값:

- staging 대상 프로젝트면 켠다

### 5-2. Ready for bootstrap

의미:

- 사람이 기본 검토를 끝냈고 다음 단계로 넘길 수 있다고 표시

현재 동작:

- `Deploy Staging` 의 필수 조건이다
- 이 값만 켠다고 bootstrap 이 자동 실행되지는 않는다
- 이 값은 준비 완료 플래그다

실무 의미:

- manifest 방향이 정해졌고
- deploy branch 를 확정했고
- staging 인프라 프로필을 적을 준비가 끝났다는 표시로 쓰면 된다

### 5-3. Database required

의미:

- 이 프로젝트가 staging 전에 DB 자동화가 필요한지 표시

현재 동작:

- `true` 이면 현재 `Deploy Staging` 이 막힌다
- 이유는 Postgres 자동 프로비저닝과 `DATABASE_URL` 주입이 아직 완성되지 않았기 때문이다

즉 현재는:

- DB 없는 앱부터 먼저 staging 경로를 검증하는 것이 맞다

### 5-4. Database engine / mode / migration command

의미:

- 나중에 DB 자동화를 붙일 때 참고할 control-plane 메타데이터다

현재 동작:

- 값은 저장된다
- 하지만 현재 staging deploy 에서 실제 DB 생성이나 migration 실행에는 아직 연결되지 않는다

권장 사용:

- 미래 운영 계약을 먼저 적어두는 용도

### 5-5. Deploy branch

의미:

- staging 기준으로 어떤 브랜치를 배포 기준으로 볼지 저장

현재 동작:

- task metadata 와 wrapper 정보에 기록된다
- `.heimdall/project.yaml` 조회 기준 ref 로 사용된다
- GitLab source archive 다운로드 기준 ref 로 사용된다
- 즉 실제 수동 staging app deploy 의 소스 버전을 결정한다

권장값:

- 보통 `main` 또는 실제 운영 기준 브랜치

### 5-6. Bootstrap strategy

선택값:

- `merge_request`
- `direct_commit`
- `manual`

현재 동작:

- 저장만 된다
- 현재 코드에서는 MR 생성, direct commit, bootstrap 실행으로 이어지지 않는다

권장 사용:

- 앞으로 어떤 bootstrap 방식을 쓸지 팀 정책을 남기는 메모성 설정으로 보면 된다

### 5-7. Staging infrastructure profile

이 섹션이 실제 VM 생성 입력값이다.

각 필드가 현재 어디에 쓰이는지 정리하면 아래와 같다.

- `Server name`
  - 생성될 VM 이름
- `Target node`
  - Proxmox 타겟 노드
- `Template ID`
  - clone 할 템플릿 식별자
  - 예: `node/vmid`
- `Storage ID`
  - 디스크 저장소
- `Network IDs`
  - 붙일 브리지 목록
- `CPU cores`
  - clone 후 적용할 CPU 수
- `Memory GB`
  - clone 후 적용할 메모리 크기
- `Disk size GB`
  - 디스크 크기
- `Static VM IP`
  - static IP 를 쓸 때 CIDR 형식으로 입력
- `VM gateway`
  - static IP 를 쓸 때 같이 입력
- `Ansible packages`
  - playbook extra vars 로 넘길 패키지 목록
- `Ansible roles`
  - playbook extra vars 로 넘길 역할 목록

중요한 현재 동작:

- `CPU cores` 와 `Memory GB` 는 Terraform 생성 단계에서 바로 넣지 않는다
- 템플릿 clone 뒤 VM 을 식별하고 필요하면 `shutdown/stop -> resize -> start` 순서로 적용한다
- 그 뒤 Ansible 로 넘어간다

즉 템플릿은 OS 베이스 용도로 두고, 하드웨어 스펙은 프로젝트별 프로필에서 조정하는 방식이다.

### 5-8. Notes

의미:

- 사람끼리 기억해야 할 운영 메모

현재 동작:

- 저장만 된다
- 실행 로직에는 직접 영향 없다

## 6. `.heimdall/project.yaml` 을 어떻게 준비해야 하나

현재 `Deploy Staging` 은 valid manifest 가 없으면 막힌다.

대상 경로:

- `.heimdall/project.yaml`

최소 예시는 아래다.

```yaml
name: billing-api
runtime: node

deploy:
  strategy: docker-compose
  compose_file: deploy/docker-compose.yml
  app_port: 3000
  healthcheck_path: /health

database:
  required: false

environments:
  staging:
    enabled: true
```

현재 런타임 최소 검증은 아래만 본다.

- `name` 이 비어 있지 않은 문자열인가
- `runtime` 이 비어 있지 않은 문자열인가
- `deploy.strategy == docker-compose` 인가
- `deploy.compose_file` 이 비어 있지 않은 문자열인가
- `deploy.app_port` 가 양의 정수인가
- `deploy.healthcheck_path` 가 `/` 로 시작하는 비어 있지 않은 문자열인가
- `environments.staging.enabled == true` 인가
- `database.required == true` 면 `database.engine == postgres` 인가

아직 안 보는 것:

- bootstrap MR 생성 가능 여부
- GitLab merge/webhook 자동 재배포 정책
- DB 자동화 계약

manifest 상태는 아래처럼 보인다.

- `valid`: 최소 규칙 통과
- `missing`: 파일 없음
- `invalid`: YAML 또는 최소 스키마 오류
- `unchecked`: GitLab API 접근 문제 등으로 확인 실패

## 7. GitLab merge 이후 실제로 무슨 일이 일어나나

가장 많이 헷갈리는 부분이라 단계별로 정리한다.

### 경우 1. 그냥 merge 만 했다

현재 일어나는 일:

- 자동 VM 생성 없음
- 자동 bootstrap 없음
- 자동 staging deploy 없음

### 경우 2. merge 후 System Hook 까지 들어왔다

현재 일어나는 일:

- inventory sync 반영 가능
- 프로젝트 메타데이터/UI 상태 갱신 가능

여전히 안 일어나는 일:

- 자동 VM 생성 없음
- 자동 staging deploy 없음

### 경우 3. setup 저장 + manifest valid 까지 맞췄다

현재 일어나는 일:

- `Deploy Staging` 버튼이 활성화될 수 있다
- 여기서 valid 는 `docker-compose` 전략뿐 아니라 `compose_file`, `app_port`, `healthcheck_path` 까지 채워졌다는 뜻이다

여전히 안 일어나는 일:

- 버튼을 누르기 전까지 실제 배포 시작 안 함

### 경우 4. 사용자가 `Deploy Staging` 버튼을 눌렀다

이때부터 실제 staging infra + app deploy 가 시작된다.

## 8. `Deploy Staging` 을 누르면 현재 실제로 하는 일

현재 구현 기준 흐름은 아래다.

1. 프로젝트가 archived 가 아닌지 확인
2. project settings 존재 확인
3. `staging_enabled == true` 확인
4. `ready_for_bootstrap == true` 확인
5. `database_required != true` 확인
6. `.heimdall/project.yaml` 이 `valid` 인지 확인
7. staging infra profile 필수값이 채워졌는지 확인
8. wrapper task 생성
9. 실제 deploy task 생성
10. Terraform 으로 템플릿 clone 기반 VM 생성
11. 생성된 VM 식별
12. 필요하면 VM stop 후 CPU/메모리 조정
13. VM 다시 start
14. SSH readiness 확인
15. backend 가 `deploy_branch` 기준 GitLab source archive 다운로드
16. Ansible 후처리 실행
17. release 디렉터리에 archive 압축 해제
18. compose 파일 존재 확인
19. `docker compose up -d --build`
20. `127.0.0.1:<app_port><healthcheck_path>` HTTP healthcheck 확인

현재 여기까지 되는 것:

- VM 생성
- post-clone CPU/메모리 조정
- SSH 공개키 주입
- Ansible packages/roles 적용
- GitLab archive 기반 앱 소스 전달
- `docker compose` 앱 실행
- HTTP healthcheck 성공 시에만 task success 처리

현재 여기서 안 되는 것:

- DB 자동 생성
- `DATABASE_URL` 주입

즉 현재 `Deploy Staging` 은 이제 `staging 인프라 + 앱 수동 배포` 까지는 수행하고, DB 자동화와 merge/webhook 자동 재배포는 아직 없다.

## 9. 버튼이 비활성화될 때 확인할 것

### `Ready for bootstrap` 이 꺼져 있음

증상:

- Deploy 버튼이 비활성화

해결:

- `Enable staging flow` 켜기
- `Ready for bootstrap` 켜기

### manifest 가 `missing` 또는 `invalid`

증상:

- valid manifest 필요 메시지 표시

해결:

- 저장소 기본 브랜치에 `.heimdall/project.yaml` 추가
- 최소 스키마 맞추기
- `deploy.compose_file`, `deploy.app_port`, `deploy.healthcheck_path` 채우기

### `database_required=true`

증상:

- 현재 지원하지 않는다는 메시지 표시

해결:

- 지금 단계에서는 DB 없는 서비스부터 먼저 staging 검증

### staging infra profile 미완성

증상:

- 인프라 프로필 필수값 부족 메시지 표시

최소 필수값:

- `staging_server_name`
- `staging_server_id`
- `staging_template_id`
- `staging_storage_id`
- `staging_network_ids`

권장 추가값:

- `staging_cpu_cores`
- `staging_memory_gb`
- `staging_disk_size_gb`
- static IP 를 쓸 경우 `staging_vm_ip` + `staging_vm_gateway`

## 10. 지금 가장 현실적인 운영 방식

현재 기준으로는 아래 순서가 제일 안전하다.

1. Ubuntu 템플릿 1개만 먼저 운영 기준으로 정한다
2. GitLab Workspace 에서 대상 프로젝트 1개를 setup 한다
3. `.heimdall/project.yaml` 을 넣고 `deploy.compose_file`, `deploy.app_port`, `deploy.healthcheck_path` 까지 채워 `valid` 상태를 만든다
4. `database_required=false` 인 앱으로 시작한다
5. staging infra profile 을 저장한다
6. `Deploy Staging` 을 수동으로 눌러 실제 VM 생성과 앱 배포 경로를 검증한다
7. Task Board 에서 wrapper task 와 실제 deploy task 를 확인한다

이렇게 한 프로젝트를 끝까지 통과시킨 뒤에 Rocky 템플릿, DB 자동화, bootstrap MR 자동화 순으로 넓히는 게 맞다.

## 11. 운영자가 기억해야 할 한 줄 요약

- merge 는 자동 배포 트리거가 아니다
- hook 도 자동 배포 트리거가 아니다
- bootstrap 관련 체크박스는 준비 상태 저장이다
- valid manifest 는 이제 `compose_file`, `app_port`, `healthcheck_path` 까지 채워진 상태를 뜻한다
- valid manifest + infra profile + 수동 `Deploy Staging` 버튼까지 가야 실제 VM 생성과 앱 배포가 시작된다
