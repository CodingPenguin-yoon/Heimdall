# API 엔드포인트 상세

## API 기본 정보

- **Base URL**: `http://localhost:8000` (기본값)
- **API Prefix**: `/api`
- **문서**: `http://localhost:8000/docs` (Swagger UI)

## 엔드포인트 목록

### 1. 배포 API (`/api/deploy`)

#### POST `/api/deploy`
배포 작업을 시작합니다.

**요청 본문 (JSON)**:
```json
{
  "server_id": "pve-node1",              // Proxmox 노드 ID
  "template_id": "pve-node1/100",        // 템플릿 ID (선택)
  "iso_image_id": "local:iso/ubuntu.iso", // ISO 이미지 ID (템플릿 없이 생성 시)
  "storage_id": "local",                  // 스토리지 ID
  "storage_type": "dir",                  // 스토리지 타입
  "network_ids": ["vmbr0"],               // 네트워크 ID 리스트
  "cpu_cores": 2,                         // CPU 코어 수
  "memory_gb": 4,                         // 메모리 (GB)
  "server_name": "my-vm",                 // VM 이름
  "ansible_packages": ["nginx", "docker"], // 설치할 패키지 리스트
  "ansible_roles": ["docker"],            // 적용할 Ansible 역할 리스트
  "skip_terraform": false,                // Terraform 단계 건너뛰기
  "skip_ansible": false                   // Ansible 단계 건너뛰기
}
```

**응답**:
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "배포 작업이 시작되었습니다.",
  "status": "pending"
}
```

**동작 과정**:
1. 요청 데이터 검증 (Pydantic 모델)
2. `DeploymentService.start_deployment_with_request()` 호출
3. 고유 `task_id` 생성
4. `TaskManager`에 작업 등록
5. `BackgroundTasks`에 배포 작업 등록
6. 즉시 `task_id` 반환 (비동기 처리)

**에러 응답**:
- `500 Internal Server Error`: 배포 시작 실패

---

### 2. 상태 조회 API (`/api/status`)

#### GET `/api/status/{task_id}`
특정 작업의 현재 상태를 조회합니다.

**경로 파라미터**:
- `task_id`: 작업 식별자 (UUID)

**응답**:
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "Running",  // Pending, Running, Success, Failed
  "created_at": "2024-01-01T12:00:00",
  "updated_at": "2024-01-01T12:05:00"
}
```

**상태 값**:
- `Pending`: 작업 대기 중
- `Running`: 작업 실행 중
- `Success`: 작업 성공
- `Failed`: 작업 실패

**동작 과정**:
1. `TaskManager.get_status(task_id)` 호출
2. 메모리에서 작업 상태 조회
3. 상태 정보 반환

**에러 응답**:
- `404 Not Found`: 작업을 찾을 수 없음

---

### 3. 로그 조회 API (`/api/logs`)

#### GET `/api/logs/{task_id}`
특정 작업의 실행 로그를 조회합니다.

**경로 파라미터**:
- `task_id`: 작업 식별자 (UUID)

**응답**:
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "logs": [
    "[2024-01-01 12:00:00] === 배포 작업 시작 ===",
    "[2024-01-01 12:00:01] [1/4] Terraform Init 실행 중...",
    "[2024-01-01 12:00:05] Terraform has been successfully initialized!",
    "[2024-01-01 12:00:10] [2/4] Terraform Plan 실행 중...",
    ...
  ],
  "total_lines": 150
}
```

**동작 과정**:
1. 작업 존재 여부 확인
2. `TaskManager.get_logs(task_id)` 호출
3. 누적된 모든 로그 반환

**에러 응답**:
- `404 Not Found`: 작업을 찾을 수 없음

---

### 4. Proxmox 조회 API (`/api/proxmox`)

모든 Proxmox 조회 API는 **GET 메서드만 사용**하며, 리소스 생성/수정/삭제는 Terraform을 통해 수행합니다.

#### GET `/api/servers`
Proxmox 노드(서버) 목록을 조회합니다.

**응답**:
```json
{
  "servers": [
    {
      "id": "pve-node1",
      "server_id": "pve-node1",
      "name": "pve-node1",
      "server_name": "pve-node1",
      "status": "online",
      "cpu": 8,
      "memory": 17179869184,
      "uptime": 86400
    }
  ]
}
```

**동작 과정**:
1. `ProxmoxService.get_nodes()` 호출
2. Proxmox API `/nodes` 엔드포인트 호출
3. 데이터 변환 및 반환

---

#### GET `/api/templates`
Proxmox 템플릿 목록을 조회합니다.

**응답**:
```json
{
  "templates": [
    {
      "id": "pve-node1/100",
      "template_id": "pve-node1/100",
      "name": "ubuntu-template",
      "template_name": "ubuntu-template",
      "vmid": 100,
      "node": "pve-node1",
      "cpu_cores": 2,
      "memory_gb": 4.0
    }
  ]
}
```

---

#### GET `/api/vms`
Proxmox VM 목록을 조회합니다 (템플릿 제외).

**응답**:
```json
{
  "vms": [
    {
      "id": "pve-node1/101",
      "vm_id": "pve-node1/101",
      "vmid": 101,
      "name": "my-vm",
      "node": "pve-node1",
      "status": "running",
      "cpu_cores": 2,
      "memory_gb": 4.0,
      "disk_gb": 50.0,
      "disks": [
        {
          "device": "scsi0",
          "size_gb": 50.0,
          "storage": "local"
        }
      ],
      "uptime": 3600
    }
  ]
}
```

---

#### GET `/api/instances`
인스턴스 목록을 조회합니다 (VM 목록과 동일, 프론트엔드 호환성).

**응답**: `/api/vms`와 동일한 데이터를 인스턴스 형식으로 변환하여 반환

---

#### GET `/api/servers/{server_id}/storage`
특정 서버의 스토리지 목록을 조회합니다.

**경로 파라미터**:
- `server_id`: 서버(노드) ID

**응답**:
```json
{
  "storages": [
    {
      "id": "local",
      "storage_id": "local",
      "name": "local",
      "storage_name": "local",
      "type": "dir",
      "content": ["images", "iso", "vztmpl"],
      "size_gb": 500.0,
      "available_gb": 300.0
    }
  ]
}
```

---

#### GET `/api/servers/{server_id}/networks`
특정 서버의 네트워크 목록을 조회합니다.

**경로 파라미터**:
- `server_id`: 서버(노드) ID

**응답**:
```json
{
  "networks": [
    {
      "id": "vmbr0",
      "network_id": "vmbr0",
      "name": "vmbr0",
      "network_name": "vmbr0",
      "type": "bridge",
      "cidr": "192.168.1.0/24",
      "gateway": "192.168.1.1",
      "description": "bridge interface"
    }
  ]
}
```

---

#### GET `/api/servers/{server_id}/iso-images`
특정 서버의 ISO 이미지 목록을 조회합니다.

**경로 파라미터**:
- `server_id`: 서버(노드) ID

**응답**:
```json
{
  "iso_images": [
    {
      "id": "local:iso/ubuntu-22.04.iso",
      "iso_id": "local:iso/ubuntu-22.04.iso",
      "name": "ubuntu-22.04.iso",
      "iso_name": "ubuntu-22.04.iso",
      "storage": "local",
      "size": 2147483648,
      "size_gb": 2.0
    }
  ]
}
```

---

#### GET `/api/servers/{server_id}/vms`
특정 서버의 VM 목록을 조회합니다.

**경로 파라미터**:
- `server_id`: 서버(노드) ID

**응답**: `/api/vms`와 동일하지만 특정 노드만 필터링

---

### 5. 모니터링 API (`/api/monitoring`)

#### GET `/api/monitoring/nodes`
모든 노드의 모니터링 정보를 조회합니다.

**응답**:
```json
{
  "nodes": [
    {
      "node": "pve-node1",
      "name": "pve-node1",
      "status": "online",
      "cpu_total": 8,
      "cpu_usage_percent": 25.5,
      "memory_total_gb": 16.0,
      "memory_used_gb": 8.0,
      "memory_usage_percent": 50.0,
      "disk_total_gb": 500.0,
      "disk_used_gb": 200.0,
      "disk_usage_percent": 40.0,
      "storages": [...],
      "uptime": 86400,
      "load_avg": [0.5, 0.6, 0.7]
    }
  ]
}
```

---

#### GET `/api/monitoring/nodes/{node_id}`
특정 노드의 상세 모니터링 정보를 조회합니다.

**경로 파라미터**:
- `node_id`: 노드 ID

**응답**:
```json
{
  "node": "pve-node1",
  "status": {...},
  "rrd_data": [...]
}
```

---

#### GET `/api/monitoring/vms/{node_id}/{vmid}`
특정 VM의 모니터링 정보를 조회합니다.

**경로 파라미터**:
- `node_id`: 노드 ID
- `vmid`: VM ID

**응답**:
```json
{
  "node": "pve-node1",
  "vmid": 101,
  "status": {...},
  "rrd_data": [...]
}
```

---

### 6. LLM 인프라 어시스턴트 API (`/api/llm`)

자연어 기반 인프라 제어를 위한 LLM(Gemini) 연동 엔드포인트입니다.

#### POST `/api/llm/chat`
LLM과의 채팅을 수행하고, 제안된 인프라 액션 목록을 반환합니다.

**요청 본문 (JSON)**:
```json
{
  "messages": [
    { "role": "user", "content": "현재 VM 상태 보여줘" },
    { "role": "assistant", "content": "이전 어시스턴트 응답..." }
  ],
  "latest_message": {
    "role": "user",
    "content": "CPU 4코어, 메모리 8GB로 Ubuntu VM 하나 만들어줘"
  },
  "context": {
    "note": "선택적 Proxmox/VM 요약 정보를 넣을 수 있는 필드"
  }
}
```

**응답**:
```json
{
  "assistant_message": "요청하신 조건으로 VM을 생성할 수 있습니다. 아래 액션을 확인 후 실행 버튼을 눌러 주세요.",
  "actions": [
    {
      "type": "create_vm",
      "description": "pve-node1에 CPU 4코어, 메모리 8GB, 디스크 50GB Ubuntu VM을 생성",
      "params": {
        "server_id": "pve-node1",
        "server_name": "ubuntu-llm-vm",
        "template_id": "pve-node1/100",
        "cpu_cores": 4,
        "memory_gb": 8,
        "disk_size_gb": 50,
        "storage_id": "local-lvm",
        "network_ids": ["vmbr0"]
      }
    }
  ]
}
```

#### POST `/api/llm/execute-action`
LLM이 제안한 인프라 액션을 실제로 실행합니다.

> ⚠️ **중요**: 이 엔드포인트는 프론트엔드에서 사용자의 명시적 확인(버튼 클릭) 후에만 호출해야 합니다.

**요청 본문 (JSON)**:
```json
{
  "action": {
    "type": "create_vm",
    "description": "pve-node1에 CPU 4코어, 메모리 8GB, 디스크 50GB Ubuntu VM을 생성",
    "params": {
      "server_id": "pve-node1",
      "server_name": "ubuntu-llm-vm",
      "template_id": "pve-node1/100",
      "cpu_cores": 4,
      "memory_gb": 8,
      "disk_size_gb": 50,
      "storage_id": "local-lvm",
      "network_ids": ["vmbr0"]
    }
  }
}
```

**응답**:
```json
{
  "result_message": "VM 생성 배포 작업을 시작했습니다. 이름: ubuntu-llm-vm, task_id: \"...\"",
  "raw_result": {
    "task_id": "550e8400-e29b-41d4-a716-446655440000",
    "deploy_request": {
      "server_id": "pve-node1",
      "server_name": "ubuntu-llm-vm",
      "template_id": "pve-node1/100",
      "cpu_cores": 4,
      "memory_gb": 8,
      "disk_size_gb": 50,
      "storage_id": "local-lvm",
      "network_ids": ["vmbr0"]
    }
  }
}
```

**지원 액션 타입 예시**:
- `list_vms`      : VM 목록 조회 (옵션: `node`)
- `list_nodes`    : Proxmox 노드 목록 조회
- `get_vm_detail` : 특정 VM 상태 조회 (`vm_id` = `"node/vmid"`)
- `create_vm`     : 새 VM 생성 (DeploymentService 재사용)

---

## 헬스체크 엔드포인트

### GET `/`
기본 헬스체크

**응답**:
```json
{
  "message": "Terraform & Ansible Control API",
  "status": "running"
}
```

### GET `/health`
상세 헬스체크

**응답**:
```json
{
  "status": "healthy",
  "service": "backend"
}
```

## 에러 처리

모든 API는 표준 HTTP 상태 코드를 사용합니다:

- `200 OK`: 성공
- `404 Not Found`: 리소스를 찾을 수 없음
- `500 Internal Server Error`: 서버 내부 오류

에러 응답 형식:
```json
{
  "detail": "에러 메시지"
}
```

## 다음 문서

- [04_SERVICES.md](./04_SERVICES.md) - 서비스 레이어 상세
- [05_DEPLOYMENT_FLOW.md](./05_DEPLOYMENT_FLOW.md) - 배포 플로우 상세
