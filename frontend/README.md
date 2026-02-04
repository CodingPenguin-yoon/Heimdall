# Infrastructure Control Dashboard

인프라를 한눈에 관리하고 명령을 내릴 수 있는 React 기반 웹 대시보드입니다.

## 기술 스택

- **Framework**: React 18 (Vite)
- **Styling**: Tailwind CSS
- **Icons**: Lucide React
- **State Management**: React Query
- **HTTP Client**: Axios

## 주요 기능

- **Instance List**: Proxmox에서 조회한 VM/인스턴스 목록을 테이블로 표시
- **Create Instance Wizard**: Proxmox 노드/템플릿/스토리지/네트워크를 선택해 VM 생성 설정을 단계별로 구성
- **Control Center**: 배포 시작(Deploy) 및 자원 회수(Destroy) 버튼
- **Real-time Status**: 현재 배포 작업 상태를 나타내는 배지와 프로그레스 바
- **Log Viewer**: 백엔드 실행 로그를 터미널 스타일로 표시
- **Monitoring Dashboard**: 노드/VM 모니터링 정보를 시각적으로 표시
- **LLM Infra Assistant (새 탭)**: 자연어로 VM 조회/생성 요청을 하고, LLM이 제안한 인프라 액션을 확인 후 실행

## 설치 및 실행

### 1. 의존성 설치

```bash
npm install
```

### 2. 개발 서버 실행

```bash
npm run dev
```

개발 서버는 일반적으로 `http://localhost:5173`에서 실행됩니다.

### 3. 빌드

```bash
npm run build
```

빌드된 파일은 `dist` 디렉토리에 생성됩니다.

## API 연동 개요

프록시 설정을 통해 `/api` 요청이 백엔드(`http://localhost:8000`)로 전달됩니다.

- 배포/상태/로그:
  - `POST /api/deploy`
  - `GET /api/status/:taskId`
  - `GET /api/logs/:taskId`
- Proxmox 조회:
  - `GET /api/servers`, `GET /api/templates`, `GET /api/vms`, ...
- 모니터링:
  - `GET /api/monitoring/nodes`, `GET /api/monitoring/vms/:node/:vmid`
- LLM 인프라 어시스턴트:
  - `POST /api/llm/chat`
  - `POST /api/llm/execute-action`

## 프로젝트 구조

```
frontend/
├── src/
│   ├── components/
│   │   ├── DeployForm.jsx      # 배포 설정 입력 폼
│   │   ├── ControlCenter.jsx   # 배포/회수 제어 버튼
│   │   ├── StatusPanel.jsx      # 실시간 상태 표시
│   │   └── LogViewer.jsx        # 로그 뷰어
│   ├── services/
│   │   └── api.js               # API 통신 로직
│   ├── App.jsx                  # 메인 앱 컴포넌트
│   ├── main.jsx                 # 진입점
│   └── index.css                # 전역 스타일
├── index.html
├── vite.config.js
├── tailwind.config.js
└── package.json
```

## 기능 상세

### 폴링 (Polling)

배포 시작 후 2초 간격으로 상태를 확인하며, 최대 10분 후 타임아웃됩니다.

- 성공 상태(`success`, `completed`) 도달 시 폴링 중지
- 실패 상태(`failed`, `error`) 도달 시 폴링 중지
- 진행 중 상태는 계속 폴링

### LLM Infra Assistant 사용법

1. 상단 탭에서 **LLM Assistant**를 선택합니다.
2. 채팅 입력창에 자연어로 요청을 입력합니다.
   - 예: `"현재 VM들 상태 보여줘"`, `"CPU 4코어 8GB Ubuntu VM 하나 만들어줘"`.
3. LLM이 응답과 함께 **제안된 인프라 액션** 목록을 우측 패널에 표시합니다.
4. 액션의 타입/파라미터를 확인한 뒤, **실행** 버튼을 눌러 실제 Proxmox / Terraform / Ansible 플로우를 트리거합니다.
5. VM 생성 액션의 경우 기존 배포 플로우와 동일하게 `task_id`가 발급되며, 상태/로그 탭에서 진행 상황을 확인할 수 있습니다.

## 개발 참고사항

- 백엔드 API가 `http://localhost:8000`에서 실행 중이어야 합니다.
- Vite 프록시 설정으로 CORS 문제를 해결했습니다.
- 주요 컴포넌트는 Tailwind 기반의 라이트 테마 레이아웃으로 구성되어 있습니다.
