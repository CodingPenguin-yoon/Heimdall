# API Requirements

이 문서는 Infrastructure Control Dashboard 프론트엔드가 요구하는 백엔드 API 명세입니다.

## Base URL

모든 API는 `/api` 경로를 통해 접근하며, Vite 프록시 설정에 의해 `http://localhost:8000`으로 전달됩니다.

---

## 1. 인스턴스 관리 API

### 1.1 인스턴스 목록 조회

**GET** `/api/instances`

인프라에 배포된 모든 인스턴스 목록을 조회합니다.

**Response:**
```json
{
  "instances": [
    {
      "id": "string",
      "server_name": "string",
      "name": "string",
      "status": "running" | "stopped" | "deploying" | "failed",
      "cpu_cores": 4,
      "memory_gb": 8,
      "region": "string",
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

**Status Codes:**
- `200 OK`: 성공
- `500 Internal Server Error`: 서버 오류

---

### 1.2 인스턴스 배포

**POST** `/api/deploy`

새로운 인스턴스를 배포합니다.

**Request Body (마법사 스타일):**
```json
{
  "server_id": "string",
  "storage_id": "string",
  "storage_type": "server" | "nas",
  "network_ids": ["string"],
  "server_name": "string"
}
```

**Request Body (레거시 스타일 - 호환성 유지):**
```json
{
  "server_name": "string",
  "cpu_cores": 4,
  "memory_gb": 8,
  "disk_size_gb": 50,
  "network_type": "private" | "public" | "both",
  "region": "string"
}
```

**Response:**
```json
{
  "task_id": "string",
  "id": "string",
  "status": "pending",
  "message": "Deployment initiated"
}
```

**Status Codes:**
- `200 OK`: 배포 시작 성공
- `400 Bad Request`: 잘못된 요청
- `500 Internal Server Error`: 서버 오류

---

### 1.3 인스턴스 삭제

**POST** `/api/destroy`

인스턴스를 종료하고 리소스를 회수합니다.

**Request Body:**
```json
{
  "server_name": "string"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Instance terminated successfully"
}
```

**Status Codes:**
- `200 OK`: 성공
- `404 Not Found`: 인스턴스를 찾을 수 없음
- `500 Internal Server Error`: 서버 오류

---

### 1.4 배포 상태 확인

**GET** `/api/status/:taskId`

배포 작업의 현재 상태를 조회합니다.

**Response:**
```json
{
  "task_id": "string",
  "status": "pending" | "in_progress" | "success" | "completed" | "failed" | "error",
  "progress": 50,
  "message": "string"
}
```

**Status Codes:**
- `200 OK`: 성공
- `404 Not Found`: 작업을 찾을 수 없음
- `500 Internal Server Error`: 서버 오류

---

## 2. 서버/템플릿 관리 API

### 2.1 서버 템플릿 목록 조회

**GET** `/api/servers`

사용 가능한 서버 템플릿 목록을 조회합니다.

**Response:**
```json
{
  "servers": [
    {
      "id": "string",
      "server_id": "string",
      "name": "string",
      "server_name": "string",
      "cpu_cores": 4,
      "memory_gb": 8,
      "description": "string"
    }
  ]
}
```

**Status Codes:**
- `200 OK`: 성공
- `500 Internal Server Error`: 서버 오류

---

### 2.2 서버 스토리지 목록 조회

**GET** `/api/servers/:serverId/storage`

특정 서버에 연결된 스토리지 옵션을 조회합니다.

**Path Parameters:**
- `serverId`: 서버 ID

**Response:**
```json
{
  "storages": [
    {
      "id": "string",
      "storage_id": "string",
      "name": "string",
      "storage_name": "string",
      "size_gb": 100,
      "available_gb": 50,
      "type": "local" | "network"
    }
  ]
}
```

**Status Codes:**
- `200 OK`: 성공
- `404 Not Found`: 서버를 찾을 수 없음
- `500 Internal Server Error`: 서버 오류

---

### 2.3 서버 네트워크 목록 조회

**GET** `/api/servers/:serverId/networks`

특정 서버에 연결된 네트워크 목록을 조회합니다.

**Path Parameters:**
- `serverId`: 서버 ID

**Response:**
```json
{
  "networks": [
    {
      "id": "string",
      "network_id": "string",
      "name": "string",
      "network_name": "string",
      "type": "private" | "public",
      "cidr": "192.168.1.0/24",
      "description": "string"
    }
  ]
}
```

**Status Codes:**
- `200 OK`: 성공
- `404 Not Found`: 서버를 찾을 수 없음
- `500 Internal Server Error`: 서버 오류

---

## 3. 에러 처리

모든 API는 표준 HTTP 상태 코드를 사용하며, 에러 발생 시 다음 형식으로 응답합니다:

```json
{
  "error": "string",
  "message": "string",
  "details": {}
}
```

---

## 4. 폴링 (Polling)

프론트엔드는 배포 시작 후 5초 간격으로 상태를 확인합니다:
- 성공 상태(`success`, `completed`) 도달 시 폴링 중지
- 실패 상태(`failed`, `error`) 도달 시 폴링 중지
- 최대 5분 후 타임아웃

---

## 5. 데이터 필드 호환성

프론트엔드는 다음 필드명을 모두 지원합니다 (우선순위 순):

**서버:**
- `id` 또는 `server_id`
- `name` 또는 `server_name`

**스토리지:**
- `id` 또는 `storage_id`
- `name` 또는 `storage_name`

**네트워크:**
- `id` 또는 `network_id`
- `name` 또는 `network_name`

---

## 6. CORS 및 인증

- CORS는 Vite 프록시를 통해 처리됩니다
- 인증이 필요한 경우, 백엔드에서 적절한 인증 헤더를 요구할 수 있습니다
