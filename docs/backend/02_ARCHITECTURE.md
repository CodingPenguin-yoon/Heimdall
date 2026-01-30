# 백엔드 아키텍처

## 전체 아키텍처 개요

백엔드는 **계층형 아키텍처(Layered Architecture)**로 설계되어 있습니다. 각 계층은 명확한 책임을 가지며, 상위 계층은 하위 계층을 호출하는 구조입니다.

```
┌─────────────────────────────────────────┐
│         프론트엔드 (React)                │
└──────────────┬──────────────────────────┘
               │ HTTP 요청/응답
               ▼
┌─────────────────────────────────────────┐
│      FastAPI 라우터 (routes/)            │
│  - deploy.py, status.py, logs.py,        │
│    proxmox.py                            │
└──────────────┬──────────────────────────┘
               │ 서비스 호출
               ▼
┌─────────────────────────────────────────┐
│      서비스 레이어 (services/)            │
│  - deployment_service.py                 │
│  - terraform_service.py                 │
│  - ansible_service.py                   │
│  - proxmox_service.py                   │
│  - task_manager.py                      │
└──────────────┬──────────────────────────┘
               │ 외부 시스템 호출
               ▼
┌─────────────────────────────────────────┐
│      외부 시스템                          │
│  - Terraform (CLI)                      │
│  - Ansible (CLI)                        │
│  - Proxmox API                          │
└─────────────────────────────────────────┘
```

## 계층별 상세 설명

### 1. 라우터 레이어 (routes/)

**역할**: HTTP 요청을 받아서 적절한 서비스를 호출하고 응답을 반환합니다.

**파일 구조**:
- `deploy.py`: 배포 시작 API (`POST /api/deploy`)
- `status.py`: 작업 상태 조회 API (`GET /api/status/{task_id}`)
- `logs.py`: 작업 로그 조회 API (`GET /api/logs/{task_id}`)
- `proxmox.py`: Proxmox 리소스 조회 API (`GET /api/servers`, `/api/templates` 등)

**특징**:
- FastAPI의 `APIRouter`를 사용하여 모듈화
- Pydantic 모델로 요청/응답 데이터 검증
- 예외 처리 및 HTTP 상태 코드 반환

### 2. 서비스 레이어 (services/)

**역할**: 실제 비즈니스 로직을 처리합니다.

#### 2.1 DeploymentService
- **책임**: 전체 배포 프로세스를 통합 관리
- **기능**: Terraform과 Ansible을 순차적으로 실행
- **특징**: BackgroundTasks를 사용하여 비동기 처리

#### 2.2 TerraformService
- **책임**: Terraform 명령어 실행
- **기능**: `terraform init`, `plan`, `apply`, `destroy`, `output`
- **특징**: subprocess로 CLI 명령어 실행, 실시간 로그 스트리밍

#### 2.3 AnsibleService
- **책임**: Ansible Playbook 실행
- **기능**: `ansible-playbook` 명령어 실행, 동적 inventory 생성
- **특징**: Terraform에서 추출한 IP 주소를 inventory에 자동 추가

#### 2.4 ProxmoxService
- **책임**: Proxmox API와 통신하여 리소스 정보 조회
- **기능**: 노드, VM, 템플릿, 스토리지, 네트워크 조회
- **특징**: **조회 전용** (생성/수정/삭제는 Terraform 사용)

#### 2.5 TaskManager
- **책임**: 작업 상태와 로그를 메모리에 저장
- **기능**: task_id 기반 상태 추적, 로그 수집
- **특징**: Thread-safe 싱글톤 패턴

### 3. 외부 시스템

#### Terraform
- **역할**: Proxmox 리소스 생성/수정/삭제
- **위치**: `/backend/iac/terraform/`
- **실행 방식**: CLI 명령어 (`terraform apply`)

#### Ansible
- **역할**: VM에 소프트웨어 설치 및 설정
- **위치**: `/backend/iac/ansible/`
- **실행 방식**: CLI 명령어 (`ansible-playbook`)

#### Proxmox API
- **역할**: 리소스 정보 조회
- **통신 방식**: HTTP REST API
- **인증**: API Token (PVEAPIToken)

## 데이터 흐름

### 배포 요청 흐름

```
1. 프론트엔드 → POST /api/deploy
   └─> DeployRequest 모델로 데이터 검증

2. routes/deploy.py → deploy() 함수
   └─> DeploymentService.start_deployment_with_request() 호출

3. DeploymentService
   ├─> TaskManager.create_task() - 작업 생성
   ├─> BackgroundTasks.add_task() - 백그라운드 작업 등록
   └─> task_id 반환

4. 백그라운드에서 _execute_deployment() 실행
   ├─> TerraformService.init()
   ├─> TerraformService.plan()
   ├─> TerraformService.apply()
   ├─> TerraformService.get_output() - IP 주소 추출
   └─> AnsibleService.run_playbook() - IP 주소 전달

5. 각 단계마다 TaskManager에 로그 저장
   └─> task_manager.append_log(task_id, log_line)

6. 프론트엔드 → GET /api/status/{task_id}
   └─> TaskManager.get_status() - 상태 조회

7. 프론트엔드 → GET /api/logs/{task_id}
   └─> TaskManager.get_logs() - 로그 조회
```

### Proxmox 조회 흐름

```
1. 프론트엔드 → GET /api/servers
   └─> routes/proxmox.py → get_servers()

2. ProxmoxService.get_nodes()
   └─> _make_request("/nodes") - Proxmox API 호출

3. Proxmox API 응답
   └─> 데이터 변환 및 반환
```

## 아키텍처 원칙

### 1. 조회 vs 제어 분리

- **조회(Read)**: Proxmox API 직접 호출 (빠르고 실시간)
- **제어(Create/Update/Delete)**: Terraform 사용 (IaC의 이점, 안전성, 추적 가능성)

### 2. 비동기 처리

- 배포 작업은 `BackgroundTasks`를 사용하여 비동기로 실행
- 즉시 `task_id`를 반환하고, 프론트엔드는 폴링으로 상태 조회

### 3. 상태 관리

- 작업 상태는 `TaskManager`에서 메모리 기반으로 관리
- Thread-safe 구조로 동시 요청 안전하게 처리

### 4. 로그 스트리밍

- Terraform/Ansible 실행 시 실시간으로 로그를 수집
- subprocess의 stdout을 라인별로 읽어서 TaskManager에 저장

## 다음 문서

- [03_API_ENDPOINTS.md](./03_API_ENDPOINTS.md) - API 엔드포인트 상세
- [04_SERVICES.md](./04_SERVICES.md) - 서비스 레이어 상세
- [05_DEPLOYMENT_FLOW.md](./05_DEPLOYMENT_FLOW.md) - 배포 플로우 상세
