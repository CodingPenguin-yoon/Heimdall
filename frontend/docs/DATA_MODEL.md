# Data Model

Infrastructure Control Dashboard에서 사용하는 데이터 모델 정의입니다.

## 1. 인스턴스 (Instance)

배포된 인프라 인스턴스를 나타냅니다.

```typescript
interface Instance {
  id: string                    // 인스턴스 고유 ID
  server_name: string           // 인스턴스 이름
  name?: string                 // 대체 이름 필드
  status: InstanceStatus        // 인스턴스 상태
  cpu_cores: number             // CPU 코어 수
  memory_gb: number             // 메모리 크기 (GB)
  region?: string               // 리전
  created_at?: string          // 생성 시간 (ISO 8601)
}

type InstanceStatus = 
  | 'running'                   // 실행 중
  | 'stopped'                   // 중지됨
  | 'deploying'                 // 배포 중
  | 'failed'                   // 실패
```

---

## 2. 서버 템플릿 (Server Template)

인스턴스 생성에 사용할 수 있는 서버 템플릿입니다.

```typescript
interface ServerTemplate {
  id: string                    // 서버 템플릿 고유 ID
  server_id?: string           // 대체 ID 필드
  name: string                 // 템플릿 이름
  server_name?: string         // 대체 이름 필드
  cpu_cores: number            // CPU 코어 수
  memory_gb: number            // 메모리 크기 (GB)
  description?: string         // 설명
}
```

---

## 3. 스토리지 (Storage)

서버에 연결된 스토리지 옵션입니다.

```typescript
interface Storage {
  id: string                    // 스토리지 고유 ID
  storage_id?: string          // 대체 ID 필드
  name: string                 // 스토리지 이름
  storage_name?: string        // 대체 이름 필드
  size_gb: number             // 전체 크기 (GB)
  available_gb: number         // 사용 가능한 크기 (GB)
  type?: 'local' | 'network'   // 스토리지 타입
}
```

---

## 4. 네트워크 (Network)

서버에 연결된 네트워크 옵션입니다.

```typescript
interface Network {
  id: string                    // 네트워크 고유 ID
  network_id?: string          // 대체 ID 필드
  name: string                 // 네트워크 이름
  network_name?: string        // 대체 이름 필드
  type: 'private' | 'public'   // 네트워크 타입
  cidr?: string                // CIDR 블록 (예: "192.168.1.0/24")
  description?: string         // 설명
}
```

---

## 5. 배포 설정 (Deploy Config)

인스턴스 생성 시 사용하는 설정입니다.

```typescript
interface DeployConfig {
  // 마법사 스타일
  selectedServerId?: string    // 선택한 서버 ID
  selectedStorageId?: string   // 선택한 스토리지 ID
  storageType?: 'server' | 'nas' // 스토리지 타입
  selectedNetworkIds?: string[] // 선택한 네트워크 ID 배열
  serverName?: string          // 인스턴스 이름
  
  // 레거시 스타일 (호환성)
  serverName?: string          // 서버 이름
  cpuCores?: string            // CPU 코어 수
  memory?: string              // 메모리 크기
  diskSize?: string            // 디스크 크기
  networkType?: string         // 네트워크 타입
  region?: string              // 리전
}
```

---

## 6. 배포 요청 (Deploy Request)

백엔드로 전송하는 배포 요청 데이터입니다.

### 마법사 스타일
```typescript
interface DeployRequest {
  server_id: string            // 서버 ID
  storage_id: string           // 스토리지 ID
  storage_type: 'server' | 'nas' // 스토리지 타입
  network_ids: string[]        // 네트워크 ID 배열
  server_name: string         // 인스턴스 이름
}
```

### 레거시 스타일
```typescript
interface DeployRequestLegacy {
  server_name: string          // 서버 이름
  cpu_cores: number           // CPU 코어 수
  memory_gb: number           // 메모리 크기 (GB)
  disk_size_gb: number        // 디스크 크기 (GB)
  network_type: 'private' | 'public' | 'both' // 네트워크 타입
  region: string              // 리전
}
```

---

## 7. 작업 상태 (Task Status)

배포 작업의 상태 정보입니다.

```typescript
interface TaskStatus {
  task_id: string              // 작업 ID
  status: TaskStatusType       // 작업 상태
  progress?: number           // 진행률 (0-100)
  message?: string            // 상태 메시지
}

type TaskStatusType = 
  | 'pending'                 // 대기 중
  | 'in_progress'            // 진행 중
  | 'processing'            // 처리 중
  | 'success'               // 성공
  | 'completed'             // 완료
  | 'failed'                // 실패
  | 'error'                 // 오류
```

---

## 8. 로그 항목 (Log Entry)

활동 로그에 표시되는 항목입니다.

```typescript
interface LogEntry {
  timestamp: string           // 타임스탬프 (예: "오후 3:00:00")
  message: string           // 로그 메시지
  type: LogType             // 로그 타입
}

type LogType = 
  | 'info'                  // 정보
  | 'success'              // 성공
  | 'error'                // 오류
  | 'warning'              // 경고
```

---

## 9. API 응답 형식

### 성공 응답
```typescript
interface ApiResponse<T> {
  data?: T                  // 응답 데이터
  [key: string]: any        // 추가 필드
}
```

### 에러 응답
```typescript
interface ApiError {
  error: string             // 에러 타입
  message: string           // 에러 메시지
  details?: any            // 상세 정보
}
```

---

## 10. 필드 호환성

프론트엔드는 다음 필드명을 모두 지원합니다 (우선순위 순):

### 서버 템플릿
- ID: `id` > `server_id`
- 이름: `name` > `server_name`

### 스토리지
- ID: `id` > `storage_id`
- 이름: `name` > `storage_name`

### 네트워크
- ID: `id` > `network_id`
- 이름: `name` > `network_name`

이를 통해 백엔드 API의 다양한 응답 형식을 유연하게 처리할 수 있습니다.

---

## 11. 배열 응답 형식

API는 다음 두 가지 형식을 모두 지원합니다:

### 형식 1: 래핑된 배열
```json
{
  "servers": [...],
  "storages": [...],
  "networks": [...]
}
```

### 형식 2: 직접 배열
```json
[...]
```

프론트엔드는 `response.data?.servers || response.data` 형식으로 처리합니다.
