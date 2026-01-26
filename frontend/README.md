# Infrastructure Control Dashboard

인프라를 한눈에 관리하고 명령을 내릴 수 있는 React 기반 웹 대시보드입니다.

## 기술 스택

- **Framework**: React 18 (Vite)
- **Styling**: Tailwind CSS
- **Icons**: Lucide React
- **State Management**: React Query
- **HTTP Client**: Axios

## 주요 기능

- **Deploy Form**: 서버 이름, CPU 코어 수, 메모리 크기 입력
- **Control Center**: 배포 시작(Deploy), 자원 회수(Destroy) 버튼
- **Real-time Status**: 현재 인프라 상태를 나타내는 배지와 프로그레스 바
- **Log Viewer**: 백엔드 실행 로그를 터미널 스타일로 표시
- **Responsive Design**: 다크 모드 기반 반응형 레이아웃

## 설치 및 실행

### 1. 의존성 설치

```bash
npm install
```

### 2. 개발 서버 실행

```bash
npm run dev
```

개발 서버는 `http://localhost:3000`에서 실행됩니다.

### 3. 빌드

```bash
npm run build
```

빌드된 파일은 `dist` 디렉토리에 생성됩니다.

## API 엔드포인트

프록시 설정을 통해 `/api` 요청이 백엔드(`http://localhost:8000`)로 전달됩니다.

### 배포 시작
- **POST** `/api/deploy`
- **Body**: `{ server_name: string, cpu_cores: number, memory_gb: number }`

### 자원 회수
- **POST** `/api/destroy`
- **Body**: `{ server_name: string }`

### 상태 확인
- **GET** `/api/status/:taskId`

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

배포 시작 후 5초 간격으로 상태를 확인하며, 최대 5분 후 타임아웃됩니다.

- 성공 상태(`success`, `completed`) 도달 시 폴링 중지
- 실패 상태(`failed`, `error`) 도달 시 폴링 중지
- 진행 중 상태는 계속 폴링

## 개발 참고사항

- 백엔드 API가 `http://localhost:8000`에서 실행 중이어야 합니다.
- Vite 프록시 설정으로 CORS 문제를 해결했습니다.
- 모든 컴포넌트는 다크 모드 스타일로 구성되어 있습니다.
