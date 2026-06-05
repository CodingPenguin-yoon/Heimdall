# Frontend DevOps Dashboard

## 위치

- `frontend/src/App.jsx`
- `frontend/src/components/DevOpsDashboard.jsx`
- `frontend/src/services/devopsApi.js`
- `frontend/src/utils/devopsDashboard.js`
- `frontend/package.json`

## 현재 사용자 표면

- route: `/devops`
- 목적: 사람 운영자가 현재 DevOps 신호를 읽는 read-only dashboard

표시 영역:

- `Services`
- `CI/CD`
- `Database`
- `Deployment targets`

## API 사용 방식

frontend는 `/api` baseURL을 쓰는 GET 전용 client만 노출한다.

사용 endpoint:

- `GET /api/devops/dashboard`
- `GET /api/devops/services`
- `GET /api/devops/services/{service_id}/summary`
- `GET /api/devops/environments`
- `GET /api/devops/deployment-targets`
- `GET /api/devops/ci-runs`
- `GET /api/devops/db-status`

중요한 구분:

- frontend는 read-only다.
- backend 전체 API가 read-only라는 뜻은 아니다.
- 문서와 설명에서 이 둘을 분리해서 써야 한다.

## UI 상태

현재 dashboard는 다음 상태를 직접 다룬다.

- initial loading
- empty catalog
- partial data load issue
- summary cards
- section list rendering

추가 구현 포인트:

- `getServiceSummary`
- mounted/unmount guard
- refresh button

## 현재 하지 않는 것

- catalog mutation form
- deploy/retry 버튼
- provider-side execution
- raw shell action
- secret 입력/저장 UI

## 왜 read-only인가

지금 단계에서는 운영자가 안전하게 상태를 읽고 판단할 수 있는 표면을 먼저 고정하는 편이 낫다. mutation과 실행을 먼저 넣으면 approval/audit/rollback 경계 없이 side effect가 생긴다.
