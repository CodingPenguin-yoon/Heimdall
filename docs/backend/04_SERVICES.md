# 서비스 레이어 상세

## 서비스 개요

서비스 레이어는 실제 비즈니스 로직을 처리하는 핵심 부분입니다. 각 서비스는 특정 책임을 가지며, 외부 시스템과 통신하거나 내부 작업을 관리합니다.

## 1. DeploymentService (배포 통합 서비스)

### 역할
전체 배포 프로세스를 통합 관리하는 서비스입니다. Terraform과 Ansible을 순차적으로 실행하여 인프라를 배포합니다.

### 위치
`backend/app/services/deployment/service.py`

### 주요 메서드

#### `start_deployment_with_request()`
배포 요청 정보와 함께 배포 작업을 시작합니다.

**파라미터**:
- `background_tasks`: FastAPI BackgroundTasks 인스턴스
- `deploy_request`: 배포 요청 정보 딕셔너리
- `skip_terraform`: Terraform 단계 건너뛰기 여부
- `skip_ansible`: Ansible 단계 건너뛰기 여부

**반환값**: `task_id` (UUID 문자열)

**동작 과정**:
1. 고유 `task_id` 생성 (UUID)
2. `TaskManager`에 작업 등록
3. 작업 상태를 `Pending`으로 설정
4. `BackgroundTasks`에 `_execute_deployment()` 등록
5. 즉시 `task_id` 반환

#### `_execute_deployment()` (내부 메서드)
실제 배포 작업을 실행합니다. 백그라운드에서 비동기로 실행됩니다.

**실행 순서**:
1. 작업 상태를 `Running`으로 변경
2. **Terraform 단계** (skip_terraform이 False인 경우):
   - `terraform init` 실행
   - `terraform plan` 실행 (선택적)
   - `terraform apply` 실행 (프론트엔드 입력값을 변수로 전달)
   - `terraform output`에서 IP 주소 추출
3. **Ansible 단계** (skip_ansible이 False인 경우):
   - Terraform에서 추출한 IP 주소로 inventory 생성
   - `ansible-playbook` 실행
4. 작업 상태를 `Success` 또는 `Failed`로 변경

**특징**:
- 각 단계마다 실시간 로그를 `TaskManager`에 저장
- 에러 발생 시 즉시 중단하고 상태를 `Failed`로 변경
- Cloud-init user-data 자동 생성 (템플릿 없이 생성 시 SSH 키 주입)

---

## 2. TerraformService (Terraform 실행 서비스)

### 역할
Terraform 명령어를 OS 레벨에서 실행하고 결과를 관리합니다.

### 위치
`backend/app/services/terraform_service.py`

### 작업 디렉토리
`backend/iac/terraform/`

### 주요 메서드

#### `init(task_id)`
Terraform 초기화를 실행합니다.

**동작**:
- `terraform init` 명령어 실행
- 실시간 로그를 `TaskManager`에 저장
- 성공/실패 여부 반환

#### `plan(task_id)`
Terraform 계획을 실행합니다.

**동작**:
- `terraform plan` 명령어 실행
- 변경 사항 미리보기
- 실패해도 치명적이지 않으므로 계속 진행 가능

#### `apply(task_id, auto_approve, variables)`
Terraform 적용을 실행합니다.

**파라미터**:
- `task_id`: 작업 식별자
- `auto_approve`: 자동 승인 여부 (기본값: True)
- `variables`: Terraform 변수 딕셔너리

**동작**:
- `terraform apply -auto-approve` 명령어 실행
- `-var` 옵션으로 변수 전달
- 리스트 변수는 JSON 문자열로 변환

**예시 변수**:
```python
{
  "vm_name": "my-vm",
  "target_node": "pve-node1",
  "template_id": "pve-node1/100",
  "cpu_cores": 2,
  "memory_gb": 4,
  "disk_size_gb": 50,
  "storage_id": "local",
  "network_ids": ["vmbr0"],
  "cloudinit_user_data": "#cloud-config\n..."
}
```

#### `get_output(output_name)`
Terraform output 값을 조회합니다.

**파라미터**:
- `output_name`: 조회할 output 이름 (None이면 모든 output)

**반환값**: output 값 딕셔너리

**예시**:
```python
{
  "vm_ip": "192.168.1.100",
  "instance_ip": "192.168.1.100"
}
```

#### `destroy(task_id, auto_approve)`
Terraform 인프라 삭제를 실행합니다.

**동작**:
- `terraform destroy -auto-approve` 명령어 실행
- 모든 리소스 삭제

### 내부 메서드

#### `_run_command(command, task_id, cwd)`
Terraform 명령어를 실행하는 내부 메서드입니다.

**동작**:
1. subprocess로 명령어 실행
2. stdout을 실시간으로 읽어서 로그 저장
3. 종료 코드 확인하여 성공/실패 판단

---

## 3. AnsibleService (Ansible 실행 서비스)

### 역할
Ansible Playbook을 OS 레벨에서 실행하고 결과를 관리합니다.

### 위치
`backend/app/services/ansible/__init__.py`

### 작업 디렉토리
`backend/iac/ansible/`

### 주요 메서드

#### `create_inventory(hosts, task_id)`
Ansible inventory 파일을 동적으로 생성합니다.

**파라미터**:
- `hosts`: 호스트 정보 리스트 `[{"name": "vm1", "ip": "192.168.1.100", "user": "root"}]`
- `task_id`: 작업 식별자

**생성되는 inventory.yml**:
```yaml
all:
  children:
    proxmox_vms:
      hosts:
        proxmox_vm:
          ansible_host: 192.168.1.100
          ansible_user: root
          ansible_ssh_private_key_file: /path/to/key
  vars:
    ansible_ssh_common_args: "-o StrictHostKeyChecking=no"
```

#### `run_playbook(playbook_file, task_id, extra_vars, inventory_hosts)`
Ansible Playbook을 실행합니다.

**파라미터**:
- `playbook_file`: 실행할 playbook 파일명 (기본값: "playbook.yml")
- `task_id`: 작업 식별자
- `extra_vars`: 추가 변수 딕셔너리 (ansible-playbook -e 옵션)
- `inventory_hosts`: 호스트 정보 리스트 (inventory 자동 생성)

**동작**:
1. Playbook 파일 존재 여부 확인
2. `inventory_hosts`가 제공되면 inventory 파일 생성
3. `ansible-playbook` 명령어 구성
4. `-e` 옵션으로 extra_vars 전달
5. subprocess로 실행하고 실시간 로그 수집

**예시 extra_vars**:
```python
{
  "packages_to_install": ["nginx", "docker"],
  "roles_to_apply": ["docker"]
}
```

**실행 명령어 예시**:
```bash
ansible-playbook playbook.yml \
  -i inventory.yml \
  -e 'packages_to_install=["nginx","docker"]' \
  -e 'roles_to_apply=["docker"]'
```

---

## 4. ProxmoxService (Proxmox API 연동 서비스)

### 역할
Proxmox API와 통신하여 리소스 정보를 조회합니다.

### 위치
`backend/app/services/proxmox/__init__.py`

### 중요 원칙
**조회 전용**: 이 서비스는 리소스 조회만 담당하며, 생성/수정/삭제는 Terraform을 통해 수행합니다.

### 초기화
환경 변수에서 Proxmox API 설정을 읽습니다:
- `PROXMOX_API_URL`: Proxmox API URL
- `PROXMOX_API_TOKEN_ID`: API Token ID
- `PROXMOX_API_TOKEN_SECRET`: API Token Secret
- `PROXMOX_TLS_INSECURE`: TLS 검증 비활성화 여부

### 주요 메서드

#### `_make_request(endpoint, method, params)` (내부 메서드)
Proxmox API 요청을 실행하는 내부 메서드입니다.

**동작**:
1. API URL과 인증 헤더 구성
2. `requests` 라이브러리로 HTTP 요청
3. 응답 JSON 파싱 및 반환
4. 에러 발생 시 빈 리스트 반환

**인증 방식**:
```
Authorization: PVEAPIToken={token_id}={token_secret}
```

#### `get_nodes()`
Proxmox 노드(서버) 목록을 조회합니다.

**API 엔드포인트**: `GET /nodes`

**반환값**: 노드 정보 리스트

#### `get_templates(node)`
Proxmox 템플릿 목록을 조회합니다.

**API 엔드포인트**: `GET /nodes/{node}/qemu` (템플릿 필터링)

**반환값**: 템플릿 정보 리스트

#### `get_vms(node)`
Proxmox VM 목록을 조회합니다 (템플릿 제외).

**API 엔드포인트**: `GET /nodes/{node}/qemu` (템플릿 제외 필터링)

**반환값**: VM 정보 리스트 (디스크 정보 포함)

#### `get_storages(node)`
Proxmox 스토리지 목록을 조회합니다.

**API 엔드포인트**: `GET /nodes/{node}/storage`

**반환값**: 스토리지 정보 리스트

#### `get_networks(node)`
Proxmox 네트워크 목록을 조회합니다.

**API 엔드포인트**: `GET /nodes/{node}/network`

**반환값**: 네트워크 정보 리스트

#### `get_iso_images(node)`
Proxmox ISO 이미지 목록을 조회합니다.

**API 엔드포인트**: `GET /storage/{storage}/content` (ISO 필터링)

**반환값**: ISO 이미지 정보 리스트

#### `get_all_nodes_monitoring()`
모든 노드의 모니터링 정보를 조회합니다.

**동작**:
1. 모든 노드 목록 조회
2. 각 노드의 상태 및 RRD 데이터 조회
3. CPU, 메모리, 디스크 사용률 계산
4. 통합 모니터링 데이터 반환

---

## 5. TaskManager (작업 상태 관리)

### 역할
배포 작업의 상태와 로그를 메모리에 저장하고 관리합니다.

### 위치
`backend/app/services/task/manager.py`

### 설계 패턴
**싱글톤 패턴**: 전역 단일 인스턴스로 작업 상태를 중앙 관리합니다.

**Thread-safe**: `threading.Lock`을 사용하여 동시 요청을 안전하게 처리합니다.

### 데이터 구조

#### 작업 상태 (`_tasks`)
```python
{
  "task_id": {
    "status": TaskStatus.RUNNING,
    "created_at": "2024-01-01T12:00:00",
    "updated_at": "2024-01-01T12:05:00"
  }
}
```

#### 작업 로그 (`_logs`)
```python
{
  "task_id": [
    "[2024-01-01 12:00:00] === 배포 작업 시작 ===",
    "[2024-01-01 12:00:01] [1/4] Terraform Init 실행 중...",
    ...
  ]
}
```

### TaskStatus 열거형
```python
class TaskStatus(str, Enum):
    PENDING = "Pending"    # 작업 대기 중
    RUNNING = "Running"     # 작업 실행 중
    SUCCESS = "Success"     # 작업 성공
    FAILED = "Failed"       # 작업 실패
```

### 주요 메서드

#### `create_task(task_id)`
새로운 작업을 생성합니다.

**동작**:
- 작업 상태를 `Pending`으로 초기화
- 생성 시간 기록
- 빈 로그 리스트 생성

#### `update_status(task_id, status)`
작업 상태를 업데이트합니다.

**파라미터**:
- `task_id`: 작업 식별자
- `status`: 새로운 상태 (TaskStatus)

**동작**:
- 상태 업데이트
- 업데이트 시간 기록

#### `get_status(task_id)`
작업 상태를 조회합니다.

**반환값**: 작업 상태 정보 딕셔너리 또는 None

#### `append_log(task_id, log_line)`
작업 로그를 추가합니다.

**동작**:
- 타임스탬프를 포함하여 로그 라인 추가
- 형식: `[YYYY-MM-DD HH:MM:SS] {log_line}`

#### `get_logs(task_id)`
작업 로그를 조회합니다.

**반환값**: 로그 라인 리스트

#### `clear_task(task_id)`
작업 데이터를 삭제합니다 (메모리 정리용).

### 전역 인스턴스
```python
# app/services/task/manager.py
task_manager = TaskManager()
```

다른 모듈에서 사용:
```python
from app.services.task.manager import task_manager

task_manager.create_task(task_id)
task_manager.append_log(task_id, "로그 메시지")
```

---

## 6. LLMService & InfraActionService (LLM 인프라 어시스턴트)

### 역할

- Gemini LLM 과 통신하고, LLM이 제안한 인프라 액션을 실제 서비스 호출로 매핑합니다.
- 조회 액션은 ProxmoxService 를 통해 즉시 실행하고, 생성 액션(`create_vm`) 은 DeploymentService 를 통해 일반 배포 파이프라인을 재사용합니다.

### 위치

- `backend/app/services/llm/service.py` (LLMService 래퍼)
- `backend/app/services/llm/llm_core.py` (Gemini 호출 핵심)
- `backend/app/services/llm/infra_action_service.py` (액션 실행)

### 주요 구성요소

- `LLMService`
  - `chat(messages, extra_context)` 메서드로 Gemini 호출
  - 자연어 응답 + `actions` 리스트(`type`, `description`, `params`) 반환
- `InfraActionType`
  - `list_vms`, `list_nodes`, `get_vm_detail`, `create_vm` 등 지원 타입 정의
- `InfraActionService.execute_action(action, background_tasks)`
  - 타입에 따라 ProxmoxService 또는 DeploymentService 호출
  - `create_vm` 의 경우:
    - `DeploymentService.start_deployment_with_request(...)` 호출
    - `/api/deploy` 와 동일한 배포 플로우 사용

---

## 서비스 간 상호작용

### 배포 시퀀스 다이어그램

```
DeploymentService
    │
    ├─> TaskManager.create_task()
    ├─> TaskManager.update_status(RUNNING)
    │
    ├─> TerraformService.init()
    │   └─> TaskManager.append_log()
    │
    ├─> TerraformService.plan()
    │   └─> TaskManager.append_log()
    │
    ├─> TerraformService.apply()
    │   └─> TaskManager.append_log()
    │
    ├─> TerraformService.get_output()
    │   └─> IP 주소 추출
    │
    └─> AnsibleService.run_playbook()
        ├─> AnsibleService.create_inventory() (IP 주소 사용)
        └─> TaskManager.append_log()
```

### 조회 시퀀스 다이어그램

```
routes/proxmox.py
    │
    └─> ProxmoxService.get_nodes()
        └─> Proxmox API 호출
            └─> 데이터 변환 및 반환
```

## 다음 문서

- [05_DEPLOYMENT_FLOW.md](./05_DEPLOYMENT_FLOW.md) - 배포 플로우 상세
- [06_RUNNING.md](./06_RUNNING.md) - 실행 방법
