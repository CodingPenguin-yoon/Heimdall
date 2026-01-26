# Feature Specification

Infrastructure Control Dashboard의 기능 명세서입니다.

## 1. 개요

인프라를 한눈에 관리하고 명령을 내릴 수 있는 웹 기반 대시보드입니다.

### 기술 스택
- **Framework**: React 18 (Vite)
- **Styling**: Tailwind CSS
- **Icons**: Lucide React
- **State Management**: React Query
- **HTTP Client**: Axios

---

## 2. 주요 기능

### 2.1 인스턴스 목록 (Instance List)

**목적**: 배포된 모든 인스턴스를 한눈에 확인하고 관리

**기능:**
- 인스턴스 목록 테이블 표시
- 컬럼: Name, Status, CPU, Memory, Region, Actions
- 각 인스턴스의 상태 배지 표시
  - Running (초록색)
  - Stopped (회색)
  - Deploying (파란색)
  - Failed (빨간색)
- Refresh 버튼으로 수동 새로고침
- 30초마다 자동 새로고침
- 각 인스턴스의 Terminate 버튼
- 빈 상태 메시지 (인스턴스가 없을 때)

**UI 구성:**
- 깔끔한 테이블 레이아웃
- 호버 효과
- 반응형 디자인

---

### 2.2 인스턴스 생성 (Create Instance)

**목적**: 단계별 마법사를 통해 새 인스턴스를 생성

**3단계 마법사:**

#### Step 1: Server Selection (서버 선택)
- 인스턴스 이름 입력 (선택사항)
- 사용 가능한 서버 템플릿 목록 표시
- 각 템플릿의 정보 표시:
  - 이름
  - CPU 코어 수
  - 메모리 크기
  - 설명
- 서버 선택 시 파란색으로 강조
- 선택 완료 표시 (체크 아이콘)

#### Step 2: Storage Selection (스토리지 선택)
- 스토리지 타입 선택:
  - Server Storage: 서버에 연결된 스토리지
  - NAS Storage: 네트워크 연결 스토리지
- 선택한 서버의 스토리지 옵션 표시
- 각 스토리지의 정보:
  - 이름
  - 전체 크기
  - 사용 가능한 크기
- 스토리지 선택

#### Step 3: Network Configuration (네트워크 설정)
- 선택한 서버의 네트워크 목록 표시
- 여러 네트워크 선택 가능 (체크박스)
- 각 네트워크의 정보:
  - 이름
  - 타입 (Private/Public)
  - CIDR
  - 설명
- 최소 1개 이상의 네트워크 선택 필수

**진행 상태 표시:**
- 상단에 3단계 진행 상태 표시
- 완료된 단계는 초록색 체크 표시
- 현재 단계는 파란색으로 강조
- 미완료 단계는 회색

**네비게이션:**
- Previous 버튼: 이전 단계로 이동
- Next 버튼: 다음 단계로 이동 (조건 충족 시에만 활성화)
- Launch Instance 버튼: 마지막 단계에서 배포 시작

---

### 2.3 실시간 상태 (Instance Status)

**목적**: 현재 배포 작업의 상태를 실시간으로 표시

**기능:**
- 상태 배지 표시:
  - Idle (회색)
  - Deploying (파란색, 스피너 애니메이션)
  - Success (초록색)
  - Failed (빨간색)
  - Destroying (주황색, 스피너 애니메이션)
- 프로그레스 바 (0-100%)
- 현재 상태 텍스트 표시

**UI 구성:**
- 상태별 색상 구분
- 부드러운 전환 애니메이션

---

### 2.4 활동 로그 (Activity Log)

**목적**: 모든 작업의 로그를 터미널 스타일로 표시

**기능:**
- 타임스탬프와 함께 로그 메시지 표시
- 로그 타입별 색상 구분:
  - Info (기본 색상)
  - Success (초록색)
  - Error (빨간색)
  - Warning (노란색)
- 자동 스크롤 (새 로그 추가 시)
- 터미널 스타일의 검은색 배경

**UI 구성:**
- 모노스페이스 폰트
- 검은색 배경
- 색상 구분된 텍스트

---

## 3. 사용자 경험 (UX)

### 3.1 탭 인터페이스
- 왼쪽 상단에 두 개의 탭:
  - Instance List
  - Create Instance
- 활성 탭은 파란색으로 강조

### 3.2 레이아웃
- 2열 그리드 레이아웃
- 왼쪽: 주요 작업 영역 (탭 + 콘텐츠)
- 오른쪽: 상태 및 로그 영역

### 3.3 반응형 디자인
- 데스크톱: 2열 레이아웃
- 태블릿/모바일: 1열 레이아웃

### 3.4 로딩 상태
- 데이터 로딩 중 스피너 표시
- 버튼 비활성화로 중복 요청 방지

### 3.5 에러 처리
- API 에러 시 로그에 표시
- 사용자 친화적인 에러 메시지

---

## 4. 데이터 흐름

### 4.1 인스턴스 목록
```
사용자 → InstanceList 컴포넌트 → GET /api/instances → 상태 업데이트 → UI 렌더링
```

### 4.2 인스턴스 생성
```
사용자 → CreateInstanceWizard → Step 1: GET /api/servers
                              → Step 2: GET /api/servers/:id/storage
                              → Step 3: GET /api/servers/:id/networks
                              → POST /api/deploy → 폴링 시작 → 상태 업데이트
```

### 4.3 폴링 메커니즘
```
배포 시작 → 5초 간격으로 GET /api/status/:taskId → 상태 확인
         → Success/Failed 도달 시 중지
         → 최대 5분 후 타임아웃
```

---

## 5. 상태 관리

### 5.1 전역 상태
- `activeTab`: 현재 활성 탭 ('list' | 'create')
- `deployConfig`: 배포 설정
  - `selectedServerId`: 선택한 서버 ID
  - `selectedStorageId`: 선택한 스토리지 ID
  - `storageType`: 스토리지 타입 ('server' | 'nas')
  - `selectedNetworkIds`: 선택한 네트워크 ID 배열
  - `serverName`: 인스턴스 이름
- `status`: 현재 배포 상태
- `logs`: 활동 로그 배열

### 5.2 로컬 상태
- 각 컴포넌트의 내부 상태 (로딩, 에러 등)

---

## 6. 스타일 가이드

### 6.1 색상
- Primary: Blue (#2563EB)
- Success: Green (#10B981)
- Error: Red (#EF4444)
- Warning: Yellow (#F59E0B)
- Background: Light Gray (#F9FAFB)
- Text: Dark Gray (#111827)

### 6.2 타이포그래피
- 헤더: Semibold, 18-24px
- 본문: Regular, 14-16px
- 로그: Monospace, 12-14px

### 6.3 간격
- 카드 간격: 24px (space-y-6)
- 섹션 간격: 16-24px
- 요소 간격: 8-16px

---

## 7. 향후 개선 사항

- [ ] 인스턴스 상세 정보 모달
- [ ] 인스턴스 편집 기능
- [ ] 필터링 및 검색 기능
- [ ] 정렬 기능
- [ ] 페이지네이션
- [ ] 다크 모드 지원
- [ ] 키보드 단축키
- [ ] 실시간 WebSocket 연결 (폴링 대신)
