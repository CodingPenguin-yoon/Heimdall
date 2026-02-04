## 모니터링 플로우 (웹 대시보드 → Proxmox 지표)

이 문서는 **프론트엔드 모니터링 대시보드에서 Proxmox 노드/VM의 상태와 지표를 가져오는 전체 흐름**을 단계별로 정리합니다.

### 1. 사용자 액션 (Monitoring 탭)

- **화면**: `MonitoringDashboard` (`frontend/src/components/MonitoringDashboard.jsx`)
- **탭**: `App.jsx` 의 `/monitoring` 탭
- **주요 기능**
  - 전체 노드 목록 및 상태 요약 조회
  - 특정 노드 선택 시 상세 리소스 사용량 조회
  - 특정 VM 선택 시 CPU/메모리/디스크/네트워크 지표 조회

### 2. 프론트엔드 → 모니터링 API 호출

- **유틸 함수들** (`frontend/src/services/api.js`)
  - `getNodesMonitoring()` → `GET /api/monitoring/nodes`
  - `getNodeMonitoring(nodeId)` → `GET /api/monitoring/nodes/{node_id}`
  - `getVMMonitoring(nodeId, vmid)` → `GET /api/monitoring/vms/{node_id}/{vmid}`

각 함수는 Axios 클라이언트(`apiClient`) 를 통해 `/api` 프리픽스 하위 엔드포인트를 호출합니다.

### 3. 백엔드 라우터 처리 (`backend/app/routes/proxmox.py`)

모니터링 관련 엔드포인트는 Proxmox 조회 라우터에 정의되어 있습니다.

- **파일**: `backend/app/routes/proxmox.py`
- **서비스**: `ProxmoxService` (`backend/app/services/proxmox/__init__.py`)

#### 3-1. 모든 노드 모니터링 (`GET /api/monitoring/nodes`)

```python
@router.get("/monitoring/nodes")
async def get_nodes_monitoring():
    monitoring_data = proxmox_service.get_all_nodes_monitoring()
    return {"nodes": monitoring_data}
```

- 역할:
  1. Proxmox 전체 노드 목록 조회
  2. 각 노드의 상태와 리소스 사용량을 수집
  3. CPU/메모리/디스크 사용률 등을 계산한 요약 데이터를 리스트로 반환

#### 3-2. 특정 노드 모니터링 (`GET /api/monitoring/nodes/{node_id}`)

```python
@router.get("/monitoring/nodes/{node_id}")
async def get_node_monitoring(node_id: str):
    status = proxmox_service.get_node_status(node_id)
    rrd_data = proxmox_service.get_node_rrddata(node_id, timeframe="hour")
    return {"node": node_id, "status": status, "rrd_data": rrd_data}
```

- 역할:
  1. 노드의 현재 상태(`status`) 정보를 Proxmox API로부터 조회
  2. RRD(Round Robin Database) 형태의 시계열 메트릭(`rrd_data`) 조회
  3. 프론트엔드가 그래프/차트로 표현할 수 있는 데이터 구조로 전달

#### 3-3. 특정 VM 모니터링 (`GET /api/monitoring/vms/{node_id}/{vmid}`)

```python
@router.get("/monitoring/vms/{node_id}/{vmid}")
async def get_vm_monitoring(node_id: str, vmid: int):
    status = proxmox_service.get_vm_status(node_id, vmid)
    rrd_data = proxmox_service.get_vm_rrddata(node_id, vmid, timeframe="hour")
    return {"node": node_id, "vmid": vmid, "status": status, "rrd_data": rrd_data}
```

- 역할:
  1. 특정 VM 의 상태 정보 조회 (전원 상태, 리소스 할당 등)
  2. CPU/메모리/디스크/네트워크 사용량 시계열 데이터 조회
  3. 프론트엔드가 선택된 VM 에 대한 상세 모니터링 화면을 구성할 수 있도록 지원

### 4. ProxmoxService 내부 동작

- **파일**: `backend/app/services/proxmox/__init__.py` (대형 모듈)
- **역할 요약**
  - Proxmox HTTP API 호출 래퍼
  - 노드/VM/스토리지/네트워크/ISO/모니터링 데이터 조회
  - 조회 전용(Read-only) 원칙 유지 (생성/수정/삭제는 Terraform 을 통해 수행)

모니터링 관련 주요 메서드(요약):

- `get_all_nodes_monitoring()`
  - 모든 노드에 대해:
    - 상태 정보 조회 (`/nodes/{node}/status`)
    - RRD 데이터 조회 (`/nodes/{node}/rrddata`)
    - CPU/메모리/디스크 사용률 계산
  - 리스트 형태의 요약 데이터 반환

- `get_node_status(node)`
- `get_node_rrddata(node, timeframe)`
- `get_vm_status(node, vmid)`
- `get_vm_rrddata(node, vmid, timeframe)`

### 5. 프론트엔드 표시 흐름

1. Monitoring 탭 진입 시:
   - `getNodesMonitoring()` 호출 → 전체 노드 리스트와 리소스 요약 수신
   - 카드/테이블 형태로 노드별 상태/사용률 표시
2. 특정 노드 선택 시:
   - `getNodeMonitoring(nodeId)` 호출
   - 노드의 상세 리소스 그래프/상태 패널 구성
3. 특정 VM 선택 시:
   - `getVMMonitoring(nodeId, vmid)` 호출
   - VM 의 CPU/메모리/디스크/네트워크 타임라인 그래프 렌더링

### 6. 배포/LLM 플로우와의 관계

- 모니터링 플로우는 **조회 전용(Read-only)** 이며, 배포/삭제와는 분리되어 있습니다.
- 그러나 다음과 같이 유기적으로 연결됩니다.
  1. 배포 플로우에서 생성된 VM 들은 Proxmox 상에 정상 등록되며
  2. 모니터링 플로우에서 동일한 노드/VM ID 를 사용해 상태/지표를 조회
  3. LLM 플로우에서 `list_vms`/`get_vm_detail` 액션으로 조회한 결과도,  
     ProxmoxService 를 통해 같은 소스(Proxmox API)에서 가져옵니다.

### 7. 모니터링 플로우 요약

1. 사용자: Monitoring 탭에서 노드/VM 선택
2. 프론트엔드: `getNodesMonitoring` / `getNodeMonitoring` / `getVMMonitoring` API 호출
3. 백엔드:
   - `routes/proxmox.py` 모니터링 엔드포인트가 요청 처리
   - `ProxmoxService` 가 Proxmox API 를 호출해 상태/지표 수집
4. 프론트엔드: 받은 JSON 데이터를 기반으로 그래프/카드 UI 렌더링

이 플로우는 **실시간 인프라 상태 파악**에 초점을 두며, 배포/LLM 기능과 함께 전체 시스템의 운영 가시성을 제공합니다.

