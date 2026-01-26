# Infrastructure Control Dashboard - Documentation

이 폴더는 Infrastructure Control Dashboard의 모든 문서를 포함합니다.

## 문서 목록

### 1. [API Requirements](./API_REQUIREMENTS.md)
백엔드 API 명세서입니다. 프론트엔드가 요구하는 모든 API 엔드포인트, 요청/응답 형식, 에러 처리 등을 포함합니다.

**주요 내용:**
- 인스턴스 관리 API (목록, 배포, 삭제, 상태 확인)
- 서버/템플릿 관리 API (목록, 스토리지, 네트워크)
- 폴링 메커니즘
- 데이터 필드 호환성

---

### 2. [Feature Specification](./FEATURE_SPECIFICATION.md)
기능 명세서입니다. 대시보드의 모든 기능과 사용자 경험을 상세히 설명합니다.

**주요 내용:**
- 인스턴스 목록 기능
- 인스턴스 생성 마법사 (3단계)
- 실시간 상태 표시
- 활동 로그
- 데이터 흐름
- 상태 관리

---

### 3. [Data Model](./DATA_MODEL.md)
데이터 모델 정의입니다. 프론트엔드에서 사용하는 모든 데이터 구조를 TypeScript 인터페이스 형식으로 정의합니다.

**주요 내용:**
- 인스턴스 모델
- 서버 템플릿 모델
- 스토리지 모델
- 네트워크 모델
- 배포 설정 및 요청 모델
- 필드 호환성 규칙

---

## 빠른 시작

### 백엔드 개발자를 위한 가이드

1. **API Requirements** 문서를 먼저 확인하세요.
   - 필요한 모든 API 엔드포인트 목록
   - 요청/응답 형식
   - 에러 처리 방법

2. **Data Model** 문서를 참고하여 데이터 구조를 확인하세요.
   - 각 엔티티의 필드 정의
   - 필드명 호환성 규칙

3. **Feature Specification** 문서로 전체 기능을 이해하세요.
   - 사용자 흐름
   - 데이터 흐름
   - 폴링 메커니즘

---

## API 구현 우선순위

백엔드 개발 시 다음 순서로 구현하는 것을 권장합니다:

### Phase 1: 기본 기능
1. `GET /api/instances` - 인스턴스 목록 조회
2. `GET /api/servers` - 서버 템플릿 목록 조회
3. `POST /api/deploy` - 인스턴스 배포
4. `GET /api/status/:taskId` - 배포 상태 확인

### Phase 2: 마법사 기능
5. `GET /api/servers/:serverId/storage` - 서버 스토리지 조회
6. `GET /api/servers/:serverId/networks` - 서버 네트워크 조회

### Phase 3: 관리 기능
7. `POST /api/destroy` - 인스턴스 삭제

---

## 테스트 데이터 예시

백엔드 개발 시 테스트에 사용할 수 있는 예시 데이터:

### 서버 템플릿
```json
{
  "servers": [
    {
      "id": "server-1",
      "name": "Small Instance",
      "cpu_cores": 2,
      "memory_gb": 4,
      "description": "Basic instance for small workloads"
    },
    {
      "id": "server-2",
      "name": "Medium Instance",
      "cpu_cores": 4,
      "memory_gb": 8,
      "description": "Standard instance for medium workloads"
    }
  ]
}
```

### 스토리지
```json
{
  "storages": [
    {
      "id": "storage-1",
      "name": "Local SSD",
      "size_gb": 100,
      "available_gb": 50,
      "type": "local"
    },
    {
      "id": "storage-2",
      "name": "NAS Volume",
      "size_gb": 500,
      "available_gb": 200,
      "type": "network"
    }
  ]
}
```

### 네트워크
```json
{
  "networks": [
    {
      "id": "network-1",
      "name": "Private Network",
      "type": "private",
      "cidr": "192.168.1.0/24",
      "description": "Internal network for instances"
    },
    {
      "id": "network-2",
      "name": "Public Network",
      "type": "public",
      "cidr": "10.0.0.0/16",
      "description": "Public-facing network"
    }
  ]
}
```

---

## 문의 및 피드백

문서에 대한 질문이나 개선 사항이 있으면 이슈를 등록해주세요.
