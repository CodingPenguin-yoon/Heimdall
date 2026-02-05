# Proxmox 웹 관리 플랫폼 - 프론트엔드

Proxmox 가상화 환경을 웹 기반으로 관리할 수 있는 React 기반 대시보드입니다.

## 🎯 주요 기능

### 1. 인스턴스 생성 (Create Instance)
- **단계별 마법사**: 4단계 마법사를 통한 VM 생성
  - Step 1: 서버 및 템플릿/ISO 선택
  - Step 2: 사양 및 스토리지 선택
  - Step 3: 네트워크 설정
  - Step 4: Ansible 설정 (패키지, 역할)
- **실시간 상태 표시**: 배포 진행 상황을 실시간으로 확인
- **로그 뷰어**: 배포 과정의 실시간 로그를 터미널 스타일로 표시

### 2. 인스턴스 목록 (Instance List)
- **VM 목록 조회**: 배포된 모든 VM을 테이블 형식으로 표시
- **상태 표시**: 각 인스턴스의 상태 배지 (Running, Stopped, Deploying, Failed)
- **자동 새로고침**: 30초마다 자동으로 목록 갱신
- **수동 새로고침**: Refresh 버튼으로 즉시 갱신

### 3. 모니터링 대시보드 (Monitoring Dashboard)
- **노드 모니터링**: 모든 Proxmox 노드의 리소스 사용률 표시
- **VM 모니터링**: 특정 VM의 상세 모니터링 정보
- **리소스 사용률**: CPU, 메모리, 디스크 사용률 시각화

## 🛠️ 기술 스택

- **Framework**: React 18 (Vite)
- **Styling**: Tailwind CSS
- **Icons**: Lucide React
- **State Management**: React Hooks (useState, useEffect)
- **HTTP Client**: Axios
- **Routing**: React Router DOM v7

## 📦 설치 및 실행

### 1. 사전 요구사항

- Node.js 16 이상
- npm 또는 yarn
- 백엔드 서버가 `http://localhost:8000`에서 실행 중이어야 함

### 2. 의존성 설치

```bash
npm install
```

### 3. 개발 서버 실행

```bash
npm run dev
```

개발 서버는 `http://localhost:5173`에서 실행됩니다.

### 4. 빌드

```bash
npm run build
```

빌드된 파일은 `dist` 디렉토리에 생성됩니다.

### 5. 프리뷰

```bash
npm run preview
```

빌드된 파일을 로컬에서 미리 볼 수 있습니다.

## 🏗️ 프로젝트 구조

```
frontend/
├── src/
│   ├── App.jsx                  # 메인 앱 컴포넌트
│   │                           # - 라우팅 설정
│   │                           # - 전역 상태 관리
│   │                           # - 배포 로직
│   ├── main.jsx                 # React 진입점
│   ├── index.css                # 전역 스타일 (Tailwind CSS)
│   ├── components/              # UI 컴포넌트
│   │   ├── CreateInstanceWizard.jsx  # 인스턴스 생성 마법사
│   │   │                           # - 4단계 마법사
│   │   │                           # - 서버/템플릿 선택
│   │   │                           # - 사양/스토리지 선택
│   │   │                           # - 네트워크 설정
│   │   │                           # - Ansible 설정
│   │   ├── InstanceList.jsx         # 인스턴스 목록 컴포넌트
│   │   │                           # - VM 목록 테이블
│   │   │                           # - 상태 배지
│   │   │                           # - 자동/수동 새로고침
│   │   ├── MonitoringDashboard.jsx # 모니터링 대시보드
│   │   │                           # - 노드 모니터링
│   │   │                           # - VM 모니터링
│   │   │                           # - 리소스 시각화
│   │   ├── StatusPanel.jsx         # 상태 패널
│   │   │                           # - 배포 상태 표시
│   │   │                           # - 진행률 표시
│   │   ├── LogViewer.jsx           # 로그 뷰어
│   │   │                           # - 실시간 로그 표시
│   │   │                           # - 로그 타입별 색상
│   │   ├── ControlCenter.jsx       # 제어 센터 (레거시)
│   │   └── DeployForm.jsx          # 배포 폼 (레거시)
│   └── services/                  # API 통신 로직
│       └── api.js                 # Axios 기반 API 클라이언트
│                               # - 배포 API
│                               # - 상태 조회 API
│                               # - 로그 조회 API
│                               # - Proxmox 조회 API
├── index.html                    # HTML 템플릿
├── vite.config.js                # Vite 설정
│                               # - 프록시 설정 (/api -> localhost:8000)
│                               # - 포트 설정 (5173)
├── tailwind.config.js            # Tailwind CSS 설정
├── postcss.config.js             # PostCSS 설정
├── package.json                  # 의존성 및 스크립트
└── 프론트_README.md              # 이 파일
```

## 🔧 주요 컴포넌트

### CreateInstanceWizard

인스턴스 생성을 위한 4단계 마법사 컴포넌트입니다.

**기능:**
- Step 1: 서버 선택, 템플릿/ISO 선택, 인스턴스 이름 입력
- Step 2: CPU 코어 수, 메모리 크기, 스토리지 선택
- Step 3: 네트워크 인터페이스 선택 (다중 선택 가능)
- Step 4: Ansible 패키지 및 역할 선택

**Props:**
- `config`: 배포 설정 객체
- `onConfigChange`: 설정 변경 핸들러
- `onDeploy`: 배포 시작 핸들러

### InstanceList

VM 인스턴스 목록을 표시하는 컴포넌트입니다.

**기능:**
- VM 목록 테이블 표시
- 상태 배지 (Running, Stopped, Deploying, Failed)
- 30초마다 자동 새로고침
- 수동 새로고침 버튼

**Props:**
- `onLogsUpdate`: 로그 업데이트 핸들러
- `onStatusChange`: 상태 변경 핸들러

### MonitoringDashboard

Proxmox 노드 및 VM의 모니터링 정보를 표시하는 컴포넌트입니다.

**기능:**
- 모든 노드의 모니터링 정보 표시
- 노드별 리소스 사용률 (CPU, 메모리, 디스크)
- VM 상세 모니터링 정보

### StatusPanel

배포 작업의 상태를 표시하는 컴포넌트입니다.

**기능:**
- 배포 상태 배지 표시
- 진행률 표시
- 상태별 색상 구분

**Props:**
- `status`: 현재 상태 (idle, deploying, success, failed, error)

### LogViewer

배포 과정의 로그를 표시하는 컴포넌트입니다.

**기능:**
- 실시간 로그 스트리밍
- 로그 타입별 색상 구분 (info, success, warning, error)
- 터미널 스타일 UI

**Props:**
- `logs`: 로그 배열

## 🔌 API 통신

프록시 설정을 통해 `/api` 요청이 백엔드(`http://localhost:8000`)로 전달됩니다.

### 주요 API 함수 (`services/api.js`)

#### 배포 API
- `deployInfrastructure(data)`: 배포 시작
  - `POST /api/deploy`
  - Body: 배포 설정 객체

#### 상태 및 로그 API
- `checkStatus(taskId)`: 작업 상태 조회
  - `GET /api/status/{task_id}`
- `getLogs(taskId)`: 작업 로그 조회
  - `GET /api/logs/{task_id}`

#### Proxmox 조회 API
- `getServers()`: 서버 목록 조회
  - `GET /api/servers`
- `getTemplates()`: 템플릿 목록 조회
  - `GET /api/templates`
- `getVMs()`: VM 목록 조회
  - `GET /api/vms`
- `getInstances()`: 인스턴스 목록 조회
  - `GET /api/instances`
- `getServerStorage(serverId)`: 스토리지 목록 조회
  - `GET /api/servers/{server_id}/storage`
- `getServerNetworks(serverId)`: 네트워크 목록 조회
  - `GET /api/servers/{server_id}/networks`
- `getServerISOImages(serverId)`: ISO 이미지 목록 조회
  - `GET /api/servers/{server_id}/iso-images`

#### 모니터링 API
- `getNodesMonitoring()`: 노드 모니터링 정보 조회
  - `GET /api/monitoring/nodes`
- `getNodeMonitoring(nodeId)`: 특정 노드 모니터링 정보 조회
  - `GET /api/monitoring/nodes/{node_id}`
- `getVMMonitoring(nodeId, vmid)`: VM 모니터링 정보 조회
  - `GET /api/monitoring/vms/{node_id}/{vmid}`

## 🔄 배포 워크플로우

1. **사용자가 배포 설정 입력**
   - CreateInstanceWizard에서 단계별로 설정 입력
   - "Launch Instance" 버튼 클릭

2. **배포 요청 전송**
   - `deployInfrastructure()` 호출
   - `POST /api/deploy`로 요청 전송
   - `task_id` 수신

3. **실시간 폴링 시작**
   - `startPolling(taskId)` 함수 실행
   - 2초 간격으로 상태 및 로그 조회
   - 새로운 로그를 UI에 실시간 표시

4. **상태 업데이트**
   - 성공/실패 상태 도달 시 폴링 중지
   - 최대 10분 후 타임아웃

## 🎨 UI/UX 특징

### 디자인
- **모던한 UI**: Tailwind CSS를 사용한 깔끔한 디자인
- **반응형 레이아웃**: 다양한 화면 크기에 대응
- **색상 구분**: 상태별 색상으로 직관적인 정보 전달
  - 성공: 초록색
  - 실패: 빨간색
  - 진행 중: 파란색
  - 대기: 회색

### 사용자 경험
- **단계별 마법사**: 복잡한 설정을 단계별로 안내
- **실시간 피드백**: 배포 진행 상황을 실시간으로 확인
- **에러 처리**: 명확한 에러 메시지 표시
- **로딩 상태**: 데이터 로딩 중 로딩 인디케이터 표시

## 🐛 문제 해결

### 백엔드 연결 실패
- 백엔드가 `http://localhost:8000`에서 실행 중인지 확인
- `vite.config.js`의 프록시 설정 확인
- 브라우저 콘솔에서 네트워크 오류 확인

### CORS 오류
- 백엔드의 CORS 설정 확인 (`backend/app/main.py`)
- 프록시 설정이 올바른지 확인

### 데이터가 표시되지 않음
- 브라우저 콘솔에서 API 응답 확인
- 네트워크 탭에서 요청/응답 확인
- 백엔드 로그 확인

### 로그가 실시간으로 업데이트되지 않음
- 폴링 간격 확인 (기본 2초)
- `task_id`가 올바른지 확인
- 네트워크 연결 확인

## 🧪 개발

### 개발 서버 실행

```bash
npm run dev
```

### 코드 스타일
- ESLint 규칙 준수
- React Hooks 사용
- 함수형 컴포넌트 사용

### 주요 의존성

```json
{
  "react": "^18.2.0",
  "react-dom": "^18.2.0",
  "react-router-dom": "^7.13.0",
  "axios": "^1.6.2",
  "lucide-react": "^0.294.0",
  "tailwindcss": "^3.3.6",
  "vite": "^5.0.8"
}
```

## 📚 추가 문서

- [프론트엔드 기능 명세](./docs/FEATURE_SPECIFICATION.md)
- [API 요구사항](./docs/API_REQUIREMENTS.md)
- [데이터 모델](./docs/DATA_MODEL.md)
