## 전체 배포 플로우 (웹 UI → VM 생성까지)

이 문서는 **프론트엔드에서 배포 버튼을 누른 순간부터 Proxmox 상에 VM이 생성되고 Ansible 설정이 끝날 때까지**의 전체 흐름을 단계별로 정리합니다.

### 1. 사용자 입력 (프론트엔드)

- **화면**: `CreateInstanceWizard` (`frontend/src/components/CreateInstanceWizard.jsx`)
- **컨테이너**: `App.jsx`의 Create 탭 (`/` 경로)
- **사용자 액션**
  - Proxmox 노드(서버) 선택
  - 템플릿 또는 ISO/리소스 옵션 선택
  - CPU / 메모리 / 디스크 / 스토리지 / 네트워크 선택
  - 서버 이름, Ansible 패키지/역할 선택

사용자 입력은 `App.jsx`의 `deployConfig` 상태로 모입니다.

### 2. 프론트엔드 → 백엔드 배포 요청

- **호출 위치**: `App.jsx` 의 `handleDeploy` 함수
- **사용하는 API 유틸**: `deployInfrastructure` (`frontend/src/services/api.js`)
- **요청 엔드포인트**
  - `POST /api/deploy`
- **요청 페이로드 예시 (프론트에서 백엔드로 전달)**

```json
{
  "server_id": "pve-node1",
  "template_id": "pve-node1/100",
  "iso_image_id": "local:iso/ubuntu-22.04.iso",
  "cpu_cores": 2,
  "memory_gb": 4,
  "disk_size_gb": 50,
  "storage_id": "local",
  "network_ids": ["vmbr0"],
  "server_name": "my-vm",
  "ansible_packages": ["nginx", "docker"],
  "ansible_roles": ["docker"],
  "skip_terraform": false,
  "skip_ansible": false
}
```

프론트엔드는 응답에서 `task_id` 를 받아서 이후 상태/로그 폴링에 사용합니다.

### 3. 백엔드 도메인 라우터 처리 (`/api/deploy`)

- **파일**: `backend/app/domains/deploy/router.py`
- **핵심 구성**
  - `DeployRequest` (Pydantic 모델)
  - `DeployResponse` (Pydantic 모델)
  - `@router.post("/deploy")` → `deploy()` 함수
- **역할**
  1. JSON 요청을 `DeployRequest` 로 검증
  2. `request.model_dump(exclude_none=True)` 로 딕셔너리 변환
  3. `DeploymentService.start_deployment_with_request(...)` 호출
  4. 생성된 `task_id` 를 포함한 `DeployResponse` 반환

이 시점에 HTTP 요청은 **즉시 응답**되며, 실제 배포 작업은 백그라운드에서 진행됩니다.

### 4. 배포 작업 등록 및 초기 상태 설정

- **서비스**: `DeploymentService`  
  - 위치: `backend/app/services/deployment/service.py`
- **작업 관리**: `TaskManager`  
  - 위치: `backend/app/services/task/manager.py`

#### 4-1. 작업 생성

1. UUID 기반 `task_id` 생성
2. `task_manager.create_task(task_id)`
3. `task_manager.update_status(task_id, TaskStatus.PENDING)`
4. `background_tasks.add_task(self._execute_deployment, ...)` 로 백그라운드 작업 등록

#### 4-2. 프론트엔드로 1차 응답

- **응답 형식**

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "배포 작업이 시작되었습니다.",
  "status": "pending"
}
```

프론트엔드는 이 `task_id` 를 저장하고, 이후 `/api/status/{task_id}`, `/api/logs/{task_id}` 를 주기적으로 호출합니다.

### 5. Terraform 단계 (인프라 생성)

- **서비스**: `TerraformService`  
  - 위치: `backend/app/services/terraform_service.py`
- **작업 디렉토리**: `backend/iac/terraform`

`DeploymentService._execute_deployment()` 내부에서 다음 순서로 실행됩니다.

#### 5-1. `terraform init`

1. 로그: `"[1/4] Terraform Init 실행 중..."`
2. `TerraformService.init(task_id)` 호출
3. 명령어: `terraform init`
4. 결과 로그를 `TaskManager` 에 실시간 축적
5. 실패 시:
   - 상태를 `Failed` 로 변경
   - 에러 로그 남기고 전체 플로우 중단

#### 5-2. `terraform plan` (선택적)

1. 로그: `"[2/4] Terraform Plan 실행 중..."`
2. `TerraformService.plan(task_id)` 호출
3. 명령어: `terraform plan -input=false`
4. 실패해도 **경고만 기록**하고 `apply` 단계로 진행

#### 5-3. `terraform apply`

1. 로그: `"[3/4] Terraform Apply 실행 중..."`
2. 프론트엔드에서 전달한 `deploy_request` 를 Terraform 변수로 변환  
   - 예: `server_name` → `vm_name`, `server_id` → `target_node`, `network_ids` → `network_ids` 등
3. 필요 시 Cloud-init user-data 자동 생성  
   - `~/.ssh/id_rsa.pub` 를 읽어 SSH 공개키를 주입
   - Base64 인코딩된 `cloudinit_user_data` 로 Terraform에 전달
4. 명령어: `terraform apply -auto-approve ... -var vm_name=... -var target_node=...`
5. 실패 시:
   - 상태를 `Failed` 로 변경
   - 에러 로그 남기고 전체 플로우 중단

#### 5-4. Terraform Output에서 VM IP 추출

1. 로그: `"Terraform Output에서 IP 주소 추출 중..."`
2. `self.terraform_service.get_output()` 호출
3. 가능한 키 후보들에서 IP 탐색
   - `vm_ip`, `instance_ip`, `ip_address`, `ip`, `default_ipv4_address`
4. 찾으면 `"추출된 IP 주소: {vm_ip}"` 로그 기록
5. 찾지 못하면 경고 로그만 남기고 Ansible 단계에서 inventory 없이 실행 시도 또는 스킵

### 6. Ansible 단계 (VM 설정)

- **서비스**: `AnsibleService`  
  - 위치: `backend/app/services/ansible/__init__.py`
- **작업 디렉토리**: `backend/iac/ansible`

#### 6-1. Inventory 생성

1. Terraform 단계에서 IP 를 성공적으로 추출했다면:
   - `inventory_hosts = [{"name": "proxmox_vm", "ip": vm_ip, "user": ANSIBLE_SSH_USER}]`
2. `AnsibleService.create_inventory(inventory_hosts, task_id)` 호출
3. `inventory.yml` 생성 및 로그 기록

#### 6-2. Playbook 실행

1. `extra_vars` 구성
   - `ansible_packages` → `packages_to_install`
   - `ansible_roles` → `roles_to_apply`
2. `AnsibleService.run_playbook("playbook.yml", task_id, extra_vars, inventory_hosts)` 호출
3. 명령어:  
   `ansible-playbook playbook.yml -i inventory.yml -e 'packages_to_install=[...]' -e 'roles_to_apply=[...]'`
4. stdout 을 한 줄씩 읽어 `TaskManager` 에 로그로 저장
5. 실패 시:
   - 상태를 `Failed` 로 변경
   - 에러 로그 기록

### 7. 작업 종료 및 상태 확정

모든 단계가 정상적으로 완료되면:

1. `task_manager.update_status(task_id, TaskStatus.SUCCESS)`
2. 로그: `"=== 배포 작업 완료 ==="`

에러/예외가 발생하면:

1. `task_manager.update_status(task_id, TaskStatus.FAILED)`
2. `"ERROR"` 또는 `"EXCEPTION"` 이 포함된 로그를 남김

### 8. 프론트엔드 폴링 (상태/로그 조회)

- **상태 조회**: `GET /api/status/{task_id}`
  - 사용 위치: `App.jsx` 의 `startPolling` 함수
  - 유틸 함수: `checkStatus` (`frontend/src/services/api.js`)
  - 응답의 `status` 값을 기반으로 UI 상태를 `idle / deploying / success / failed / error` 등으로 갱신

- **로그 조회**: `GET /api/logs/{task_id}`
  - 유틸 함수: `getLogs`
  - 누적 로그 배열을 받아 새 로그만 필터링하여 `LogViewer` 에 표시
  - `"ERROR"`, `"EXCEPTION"`, `"실패"`, `"경고"`, `"완료"` 등의 키워드로 로그 타입을 분류

`startPolling` 은 일정 간격(기본 2초)으로 두 API를 호출하여 **실시간에 가까운 배포 상태 모니터링**을 제공합니다.

### 9. 최종 사용자 경험 정리

1. 사용자가 마법사에서 옵션을 모두 채우고 **Deploy** 버튼 클릭
2. 프론트엔드가 `/api/deploy` 호출 후 `task_id` 를 획득
3. 즉시 우측 패널에서 상태/로그 영역이 **실시간 업데이트** 시작
4. Terraform/Ansible 실행 로그가 순서대로 스트리밍
5. 성공 시:
   - 상태가 `success` 로 변경
   - `"Deployment completed successfully!"` 로그 출력
6. 실패 시:
   - 상태가 `failed` 또는 `error` 로 변경
   - 에러 로그가 강조 표시

이 문서는 `docs/backend/05_DEPLOYMENT_FLOW.md` 의 백엔드 중심 설명을 **프론트엔드까지 포함한 end-to-end 플로우** 관점에서 확장한 것입니다.

