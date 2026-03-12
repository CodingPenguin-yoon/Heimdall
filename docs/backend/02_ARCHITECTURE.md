# Backend Architecture

## 1. 현재 구조 한눈에 보기

```text
frontend
  -> /api/*
FastAPI routers
  -> domain services
    -> TaskManager
    -> Proxmox HTTP API
    -> Terraform CLI
    -> Ansible CLI
```

## 2. 레이어

### API Layer

`backend/app/domains/*/router.py`

역할:

- HTTP request/response 처리
- Pydantic 모델 정의
- 서비스 호출
- 예외를 HTTP 에러로 변환

### Service Layer

`backend/app/services/*`

역할:

- 실제 업무 로직
- CLI 호출
- 외부 API 호출
- 상태/로그 기록

### Persistence Layer

현재는 정식 DB 계층이 없다.

- 작업 이력: JSON 파일
- LLM 세션: Redis 있으면 사용, 없으면 제한적

## 3. 도메인별 연결

### Deploy

`domains/deploy/router.py`
-> `services/deployment/service.py`
-> `services/terraform`
-> `services/ansible`

### Task

`domains/task/router.py`
-> `services/task/manager.py`

### Proxmox

`domains/proxmox/router.py`
-> `services/proxmox`
-> `services/network`

### LLM

`domains/llm/router.py`
-> `domains/llm/commands/infra_action.py`
-> `domains/llm/commands/chat_session.py`
-> `services/deployment`
-> `services/proxmox`
-> `services/llm/llm_core.py`

## 4. 중요한 상태 흐름

### 배포 상태

- 요청 수신 시 Task 생성
- BackgroundTasks 로 실제 실행 예약
- Terraform / Ansible 로그를 Task 로그에 누적
- 프론트는 `/api/tasks/stream` SSE 로 구독

### 작업 이력

- 메모리에서 즉시 관리
- 주기적으로 `backend/data/task_history.json` 에 flush

### LLM 세션

- `session_id` 가 있으면 Redis 우선 조회
- Redis 가 없으면 현재 요청 메시지 위주로 동작

## 5. 현재 기준 정리 포인트

### LLM 구조

- 활성 API 라우트와 명령 해석은 `backend/app/domains/llm/*` 에 있다.
- 공통 모델 호출과 세션 보조 로직은 `backend/app/services/llm/llm_core.py` 가 담당한다.

### 삭제 API 표준 경로

- 활성 삭제/종료 경로는 `/api/instances/terminate` 다.
- `/destroy` 계열 레거시 경로는 현재 기준에서 사용하지 않는다.

### VM 생성 표준 경로

- 현재 VM 생성은 템플릿 클론 기반 경로만 지원한다.
- ISO 직접 생성 관련 모델, 액션, 엔드포인트, 프론트 선택 UI 는 제거됐다.

## 6. 왜 이 구조가 중요한가

이 프로젝트는 단순 CRUD API 가 아니다. 상태가 여러 레이어를 가로지른다.

- FastAPI BackgroundTasks
- in-memory task state
- file persistence
- CLI subprocess
- Proxmox async task polling

따라서 구조를 이해하지 않고 수정하면 회귀가 쉽게 생긴다.

## 7. 추천 정리 방향

1. LLM 경로를 하나로 정리
2. API 계약과 프론트 헬퍼 정합성 맞추기
3. destroy / ISO 생성 같은 미완성 경로는 숨기거나 완성
4. 작업 저장소를 파일 기반에서 더 명시적인 저장소 계층으로 옮기기
