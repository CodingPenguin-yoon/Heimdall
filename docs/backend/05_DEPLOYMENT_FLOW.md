# 배포 플로우 상세

## 배포 프로세스 개요

배포 프로세스는 **Terraform**과 **Ansible**을 순차적으로 실행하여 인프라를 배포하고 설정합니다.

```
프론트엔드 요청
    ↓
POST /api/deploy
    ↓
DeploymentService 시작
    ↓
[1단계] Terraform Init
    ↓
[2단계] Terraform Plan
    ↓
[3단계] Terraform Apply
    ↓
[4단계] IP 주소 추출
    ↓
[5단계] Ansible Playbook 실행
    ↓
배포 완료
```

## 상세 플로우

### 1. 배포 요청 수신

**엔드포인트**: `POST /api/deploy`

**요청 예시**:
```json
{
  "server_id": "pve-node1",
  "template_id": "pve-node1/100",
  "storage_id": "local",
  "network_ids": ["vmbr0"],
  "cpu_cores": 2,
  "memory_gb": 4,
  "server_name": "my-vm",
  "ansible_packages": ["nginx", "docker"],
  "ansible_roles": ["docker"]
}
```

**처리 과정**:
1. `routes/deploy.py`의 `deploy()` 함수가 요청 수신
2. Pydantic 모델로 데이터 검증
3. `DeploymentService.start_deployment_with_request()` 호출

---

### 2. 배포 작업 시작

**서비스**: `DeploymentService.start_deployment_with_request()`

**처리 과정**:
1. 고유 `task_id` 생성 (UUID)
2. `TaskManager.create_task(task_id)` - 작업 등록
3. `TaskManager.update_status(task_id, PENDING)` - 상태 설정
4. `BackgroundTasks.add_task(_execute_deployment, ...)` - 백그라운드 작업 등록
5. 즉시 `task_id` 반환

**응답**:
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "배포 작업이 시작되었습니다.",
  "status": "pending"
}
```

**중요**: 이 시점에서 HTTP 응답이 반환되며, 실제 배포는 백그라운드에서 비동기로 실행됩니다.

---

### 3. 백그라운드 배포 실행

**서비스**: `DeploymentService._execute_deployment()`

이 메서드는 백그라운드에서 실행되며, 다음 단계를 순차적으로 수행합니다.

#### 3.1 작업 상태 변경
```python
task_manager.update_status(task_id, TaskStatus.RUNNING)
task_manager.append_log(task_id, "=== 배포 작업 시작 ===")
```

#### 3.2 배포 요청 정보 로깅
```python
if deploy_request:
    task_manager.append_log(task_id, f"배포 설정: {deploy_request}")
```

---

### 4. Terraform 단계

Terraform 단계는 `skip_terraform`이 `False`인 경우에만 실행됩니다.

#### 4.1 Terraform Init

**서비스**: `TerraformService.init(task_id)`

**실행 명령어**:
```bash
terraform init
```

**작업 디렉토리**: `backend/iac/terraform/`

**동작**:
- Terraform 프로바이더 다운로드
- 백엔드 초기화
- 모듈 다운로드 (있는 경우)

**로그 예시**:
```
[2024-01-01 12:00:01] [1/4] Terraform Init 실행 중...
[2024-01-01 12:00:02] === Terraform Init 시작 ===
[2024-01-01 12:00:02] 실행 명령어: terraform init
[2024-01-01 12:00:02] 작업 디렉토리: /path/to/iac/terraform
[2024-01-01 12:00:05] Initializing the backend...
[2024-01-01 12:00:06] Initializing provider plugins...
[2024-01-01 12:00:10] Terraform has been successfully initialized!
```

**실패 시**: 작업 상태를 `Failed`로 변경하고 중단

---

#### 4.2 Terraform Plan

**서비스**: `TerraformService.plan(task_id)`

**실행 명령어**:
```bash
terraform plan
```

**동작**:
- 변경 사항 미리보기
- 리소스 생성/수정/삭제 계획 표시

**로그 예시**:
```
[2024-01-01 12:00:11] [2/4] Terraform Plan 실행 중...
[2024-01-01 12:00:11] === Terraform Plan 시작 ===
[2024-01-01 12:00:11] 실행 명령어: terraform plan
[2024-01-01 12:00:12] Terraform will perform the following actions:
[2024-01-01 12:00:12]   # proxmox_vm.my_vm will be created
[2024-01-01 12:00:12]   + resource "proxmox_vm" "my_vm" {
[2024-01-01 12:00:15] Plan: 1 to add, 0 to change, 0 to destroy.
```

**특징**: Plan 실패는 치명적이지 않으므로 경고만 기록하고 계속 진행

---

#### 4.3 Terraform Apply

**서비스**: `TerraformService.apply(task_id, auto_approve=True, variables=terraform_vars)`

**실행 명령어**:
```bash
terraform apply -auto-approve \
  -var vm_name="my-vm" \
  -var target_node="pve-node1" \
  -var template_id="pve-node1/100" \
  -var cpu_cores=2 \
  -var memory_gb=4 \
  -var disk_size_gb=50 \
  -var storage_id="local" \
  -var network_ids='["vmbr0"]' \
  -var cloudinit_user_data="#cloud-config\n..."
```

**변수 변환 과정**:
```python
terraform_vars = {}
if deploy_request.get("server_name"):
    terraform_vars["vm_name"] = deploy_request["server_name"]
if deploy_request.get("server_id"):
    terraform_vars["target_node"] = deploy_request["server_id"]
if deploy_request.get("template_id"):
    terraform_vars["template_id"] = deploy_request["template_id"]
# ... 기타 변수들
```

**Cloud-init user-data 생성**:
- 템플릿이 없는 경우 (ISO 사용 시) 자동 생성
- SSH 공개키를 자동으로 주입
- 형식: `#cloud-config` YAML

**로그 예시**:
```
[2024-01-01 12:00:16] [3/4] Terraform Apply 실행 중...
[2024-01-01 12:00:16] === Terraform Apply 시작 ===
[2024-01-01 12:00:16] Terraform 변수: {'vm_name': 'my-vm', 'target_node': 'pve-node1', ...}
[2024-01-01 12:00:17] Cloud-init user-data 생성 완료 (SSH 키 자동 주입)
[2024-01-01 12:00:17] 실행 명령어: terraform apply -auto-approve ...
[2024-01-01 12:00:20] proxmox_vm.my_vm: Creating...
[2024-01-01 12:00:25] proxmox_vm.my_vm: Creation complete after 5s
[2024-01-01 12:00:25] Terraform Apply 완료
```

**실패 시**: 작업 상태를 `Failed`로 변경하고 중단

---

#### 4.4 IP 주소 추출

**서비스**: `TerraformService.get_output()`

**실행 명령어**:
```bash
terraform output -json
```

**동작**:
1. Terraform output을 JSON 형식으로 조회
2. IP 주소 키 찾기 (`vm_ip`, `instance_ip`, `ip_address` 등)
3. IP 주소 추출

**로그 예시**:
```
[2024-01-01 12:00:26] Terraform Output에서 IP 주소 추출 중...
[2024-01-01 12:00:26] Terraform Outputs: {'vm_ip': {'value': '192.168.1.100'}}
[2024-01-01 12:00:26] 추출된 IP 주소: 192.168.1.100
```

**IP 주소가 없는 경우**: 경고만 기록하고 Ansible 단계는 건너뛰거나 수동 입력 필요

---

### 5. Ansible 단계

Ansible 단계는 `skip_ansible`이 `False`인 경우에만 실행됩니다.

#### 5.1 Inventory 생성

**서비스**: `AnsibleService.create_inventory(inventory_hosts, task_id)`

**입력 데이터**:
```python
inventory_hosts = [{
    "name": "proxmox_vm",
    "ip": "192.168.1.100",  # Terraform에서 추출한 IP
    "user": "root"  # ANSIBLE_SSH_USER 환경 변수 또는 기본값
}]
```

**생성되는 inventory.yml**:
```yaml
all:
  children:
    proxmox_vms:
      hosts:
        proxmox_vm:
          ansible_host: 192.168.1.100
          ansible_user: root
          ansible_ssh_private_key_file: /path/to/ssh/key
  vars:
    ansible_ssh_common_args: "-o StrictHostKeyChecking=no"
```

**로그 예시**:
```
[2024-01-01 12:00:27] [4/4] Ansible Playbook 실행 중...
[2024-01-01 12:00:27] Inventory 파일 생성 완료: /path/to/iac/ansible/inventory.yml
[2024-01-01 12:00:27] 호스트 수: 1
[2024-01-01 12:00:27] Ansible Inventory에 IP 192.168.1.100 추가
```

---

#### 5.2 Ansible Playbook 실행

**서비스**: `AnsibleService.run_playbook(playbook_file, task_id, extra_vars, inventory_hosts)`

**실행 명령어**:
```bash
ansible-playbook playbook.yml \
  -i inventory.yml \
  -e 'packages_to_install=["nginx","docker"]' \
  -e 'roles_to_apply=["docker"]'
```

**작업 디렉토리**: `backend/iac/ansible/`

**extra_vars 구성**:
```python
extra_vars = {}
if deploy_request.get("ansible_packages"):
    extra_vars["packages_to_install"] = deploy_request["ansible_packages"]
if deploy_request.get("ansible_roles"):
    extra_vars["roles_to_apply"] = deploy_request["ansible_roles"]
```

**로그 예시**:
```
[2024-01-01 12:00:28] 실행 명령어: ansible-playbook playbook.yml -i inventory.yml ...
[2024-01-01 12:00:28] 작업 디렉토리: /path/to/iac/ansible
[2024-01-01 12:00:28] === Ansible Playbook 실행 시작 ===
[2024-01-01 12:00:28] 설치할 패키지: nginx, docker
[2024-01-01 12:00:28] 적용할 역할: docker
[2024-01-01 12:00:29] PLAY [proxmox_vms] ****************************************
[2024-01-01 12:00:30] TASK [Gathering Facts] ************************************
[2024-01-01 12:00:32] ok: [proxmox_vm]
[2024-01-01 12:00:33] TASK [Install packages] ************************************
[2024-01-01 12:00:35] changed: [proxmox_vm] => (item=nginx)
[2024-01-01 12:00:37] changed: [proxmox_vm] => (item=docker)
[2024-01-01 12:00:40] PLAY RECAP **************************************************
[2024-01-01 12:00:40] proxmox_vm: ok=5 changed=2 unreachable=0 failed=0
[2024-01-01 12:00:40] === Ansible Playbook 실행 완료 ===
```

**실패 시**: 작업 상태를 `Failed`로 변경하고 중단

---

### 6. 배포 완료

**처리 과정**:
```python
task_manager.update_status(task_id, TaskStatus.SUCCESS)
task_manager.append_log(task_id, "\n=== 배포 작업 완료 ===")
```

**최종 상태**:
- `status`: `Success`
- 로그에 전체 배포 과정 기록

---

## 상태 조회 플로우

프론트엔드는 배포 시작 후 `task_id`를 받아서 주기적으로 상태를 조회합니다.

### 1. 상태 조회

**엔드포인트**: `GET /api/status/{task_id}`

**처리 과정**:
1. `routes/status.py`의 `get_status()` 함수가 요청 수신
2. `TaskManager.get_status(task_id)` 호출
3. 메모리에서 작업 상태 조회
4. 상태 정보 반환

**응답 예시**:
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "Running",
  "created_at": "2024-01-01T12:00:00",
  "updated_at": "2024-01-01T12:05:00"
}
```

### 2. 로그 조회

**엔드포인트**: `GET /api/logs/{task_id}`

**처리 과정**:
1. `routes/logs.py`의 `get_logs()` 함수가 요청 수신
2. 작업 존재 여부 확인
3. `TaskManager.get_logs(task_id)` 호출
4. 누적된 모든 로그 반환

**응답 예시**:
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "logs": [
    "[2024-01-01 12:00:00] === 배포 작업 시작 ===",
    "[2024-01-01 12:00:01] [1/4] Terraform Init 실행 중...",
    ...
  ],
  "total_lines": 150
}
```

---

## 에러 처리

### Terraform 에러

**예시**:
```
[2024-01-01 12:00:20] Error: resource creation failed
[2024-01-01 12:00:20] Terraform Apply 실패: 명령어 실행 실패 (종료 코드: 1)
```

**처리**:
- 작업 상태를 `Failed`로 변경
- 에러 로그 기록
- Ansible 단계는 실행하지 않음

### Ansible 에러

**예시**:
```
[2024-01-01 12:00:35] fatal: [proxmox_vm]: UNREACHABLE! => ...
[2024-01-01 12:00:35] Ansible Playbook 실행 실패: Playbook 실행 실패 (종료 코드: 2)
```

**처리**:
- 작업 상태를 `Failed`로 변경
- 에러 로그 기록
- Terraform으로 생성된 리소스는 그대로 유지 (수동 정리 필요)

### 예외 처리

**예시**:
```python
except Exception as e:
    error_msg = f"배포 작업 중 예외 발생: {str(e)}"
    task_manager.update_status(task_id, TaskStatus.FAILED)
    task_manager.append_log(task_id, f"EXCEPTION: {error_msg}")
```

---

## 타임라인 예시

```
12:00:00 - 프론트엔드: POST /api/deploy
12:00:00 - 백엔드: task_id 생성 및 반환
12:00:01 - Terraform Init 시작
12:00:05 - Terraform Init 완료
12:00:06 - Terraform Plan 시작
12:00:10 - Terraform Plan 완료
12:00:11 - Terraform Apply 시작
12:00:25 - Terraform Apply 완료 (VM 생성)
12:00:26 - IP 주소 추출: 192.168.1.100
12:00:27 - Ansible Inventory 생성
12:00:28 - Ansible Playbook 실행 시작
12:00:40 - Ansible Playbook 완료
12:00:41 - 배포 작업 완료 (Success)
```

---

## 다음 문서

- [06_RUNNING.md](./06_RUNNING.md) - 실행 방법 및 설정
