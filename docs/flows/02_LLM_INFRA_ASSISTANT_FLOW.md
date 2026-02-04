## LLM 인프라 어시스턴트 플로우 (자연어 → 인프라 액션)

이 문서는 **LLM 기반 인프라 어시스턴트가 자연어 입력을 받아 실제 Proxmox / Terraform / Ansible 동작으로 이어지는 전체 흐름**을 단계별로 정리합니다.

### 1. 사용자 입력 (프론트엔드 LLM 채팅)

- **화면**: `LlmInfraChat` (`frontend/src/components/LlmInfraChat.jsx`)
- **탭**: `App.jsx` 의 `/assistant` 탭
- **사용자 예시 입력**
  - "현재 클러스터에 떠 있는 VM 목록 보여줘"
  - "CPU 4코어, 메모리 8GB Ubuntu VM 하나 만들어줘"

프론트엔드는 기존 대화 이력과 방금 보낸 메시지를 포함해 **LLM 채팅 요청 페이로드**를 구성합니다.

### 2. 프론트엔드 → `/api/llm/chat` 요청

- **유틸 함수**: `llmChat` (`frontend/src/services/api.js`)
- **엔드포인트**: `POST /api/llm/chat`

#### 2-1. 요청 형식

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
    "note": "선택적 인프라 컨텍스트 (예: 현재 선택된 노드/VM 요약)"
  }
}
```

### 3. 백엔드 LLM 라우터 처리 (`/api/llm/chat`)

- **파일**: `backend/app/routes/llm.py`
- **핵심 모델**
  - `ChatMessage`, `ChatRequest`, `ChatResponse`
  - `LLMMessage`, `LLMService` (`backend/app/services/llm/service.py`)
- **핵심 함수**
  - `@router.post("/llm/chat")` → `llm_chat()`

#### 3-1. 메시지 변환 및 LLM 호출

1. `ChatRequest.messages` + `latest_message` 를 합쳐 `List[LLMMessage]` 로 변환
2. `llm_service.chat(messages=..., extra_context=request.context)` 호출
3. Gemini LLM 이 다음을 포함한 결과를 반환:
   - 자연어 응답 (`assistant_message`)
   - 제안된 인프라 액션 리스트 (`actions`: type/description/params)

#### 3-2. 액션 직렬화 및 조회 액션 자동 실행

1. `InfraAction` 모델로 변환 가능한 액션들을 순회
2. **읽기 전용(safe) 액션 타입**에 대해 자동 실행:
   - `list_vms`
   - `list_nodes`
   - `get_vm_detail`
3. 각 액션은 `InfraActionService.execute_action()` 으로 위임
   - Proxmox 조회 서비스 (`ProxmoxService`) 를 내부에서 사용
4. 자동 실행 결과를:
   - `assistant_message` 끝에 `[자동 실행 결과]` 섹션으로 요약 추가
   - `data` 필드에 원본 JSON (`{"vms": [...], "nodes": [...]} 등`) 으로 포함

#### 3-3. 응답 형식

```json
{
  "assistant_message": "요청하신 조건으로 VM을 생성할 수 있습니다. 아래 액션을 확인 후 실행 버튼을 눌러 주세요.\n\n[자동 실행 결과]\n...",
  "actions": [
    {
      "type": "create_vm",
      "description": "pve-node1에 CPU 4코어, 메모리 8GB, 디스크 50GB Ubuntu VM 생성",
      "params": { "...": "..." }
    }
  ],
  "data": {
    "vms": [...],
    "nodes": [...]
  }
}
```

### 4. 프론트엔드에서 액션 표시 및 선택

- 프론트엔드는 `actions` 배열을 **"추천 인프라 액션" 목록**으로 렌더링합니다.
- 각 액션에 대해:
  - 타입/설명 표시 (`type`, `description`)
  - 주요 파라미터 요약 (예: `server_id`, `server_name`, `cpu_cores`, `memory_gb`)
  - "이 액션 실행" 버튼 제공
- 사용자는 LLM 응답을 검토한 뒤, **명시적으로 실행 버튼을 눌러야** 실제 인프라 변경이 발생합니다.

### 5. 프론트엔드 → `/api/llm/execute-action` 요청

- **유틸 함수**: `executeLlmAction` (`frontend/src/services/api.js`)
- **엔드포인트**: `POST /api/llm/execute-action`

#### 5-1. 요청 형식

```json
{
  "action": {
    "type": "create_vm",
    "description": "pve-node1에 CPU 4코어, 메모리 8GB, 디스크 50GB Ubuntu VM 생성",
    "params": {
      "server_id": "pve-node1",
      "server_name": "ubuntu-llm-vm",
      "template_id": "pve-node1/100",
      "cpu_cores": 4,
      "memory_gb": 8,
      "disk_size_gb": 50,
      "storage_id": "local-lvm",
      "network_ids": ["vmbr0"],
      "ansible_packages": ["nginx"],
      "ansible_roles": ["docker"]
    }
  }
}
```

### 6. 백엔드 InfraAction 실행 (`/api/llm/execute-action`)

- **파일**: `backend/app/routes/llm.py`
- **모델/서비스**
  - `InfraAction`, `InfraActionType`, `InfraActionService`  
    - 위치: `backend/app/services/llm/infra_action_service.py`
  - `DeploymentService` (내부에서 재사용)

#### 6-1. 요청 검증

1. `ExecuteActionRequest.action` 필수
2. `action.type` 이 누락되면 `400 Bad Request`
3. `InfraActionType` Enum 으로 타입 검증  
   - 지원 타입:
     - `list_vms`
     - `list_nodes`
     - `get_vm_detail`
     - `create_vm`

#### 6-2. 액션 타입별 분기

- `list_vms`, `list_nodes`, `get_vm_detail`
  - Proxmox 조회용 API 를 호출
  - 사용자에게 요약 메시지 + 원본 JSON 반환
- `create_vm`
  - **핵심: 기존 배포 파이프라인 재사용**
  - `DeploymentService.start_deployment_with_request(...)` 호출
  - `deploy_request` 는 `action.params` 에서 필요한 필드만 추려 구성
  - 내부적으로는 `/api/deploy` 와 동일한 배포 흐름을 사용

#### 6-3. `create_vm` 결과

1. 새로운 `task_id` 가 생성되어 배포 작업이 시작됨
2. 응답 예시:

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

이 `task_id` 는 일반 배포와 동일하게 `/api/status/{task_id}`, `/api/logs/{task_id}` 에서 조회 가능합니다.

### 7. 배포/상태/로그 플로우와의 접점

LLM을 통한 VM 생성은 **일반 배포 플로우와 완전히 동일한 파이프라인**을 사용합니다.

1. `InfraActionService._execute_create_vm()` → `DeploymentService.start_deployment_with_request(...)`
2. 이후 흐름:
   - Terraform Init/Plan/Apply
   - Terraform Output에서 IP 추출
   - Ansible Inventory 생성 및 Playbook 실행
   - `TaskManager` 를 통한 상태/로그 관리
3. 프론트엔드는 `task_id` 만 알면:
   - 기존 폴링 로직(`checkStatus`, `getLogs`) 또는
   - 별도 LLM 탭 UI를 통해 상태/로그를 재활용해서 보여줄 수 있습니다.

### 8. LLM 플로우 요약

1. 사용자: LLM 채팅 탭에서 자연어로 인프라 요청
2. 프론트엔드: `/api/llm/chat` 호출 → LLM 응답 + 액션 리스트 수신
3. 사용자: 제안된 액션 중 하나를 선택해 실행 버튼 클릭
4. 프론트엔드: `/api/llm/execute-action` 호출
5. 백엔드: 액션 타입 검사 후
   - 조회 액션 → 즉시 결과 반환
   - `create_vm` → 기존 배포 파이프라인(DeploymentService) 으로 위임
6. 프론트엔드: 반환된 `task_id` 를 이용해 일반 배포와 동일하게 상태/로그를 추적

이 문서는 LLM 기능의 흐름을 **"대화 → 액션 제안 → 사용자 승인 → 실제 인프라 변경"** 단계로 분리하여 이해하도록 돕습니다.

