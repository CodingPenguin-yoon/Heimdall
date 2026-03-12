# Flow 02: LLM Infra Assistant

이 문서는 `/assistant` 화면의 채팅 기능이 백엔드 LLM 도메인과 어떻게 연결되는지 설명한다.

기준 파일:

- `frontend/src/components/LlmInfraChat.jsx`
- `frontend/src/services/api.js`
- `backend/app/domains/llm/router.py`
- `backend/app/domains/llm/commands/infra_action.py`
- `backend/app/services/llm/llm_core.py`

## 1. 프론트 세션 상태

프론트는 `localStorage` 에 `llm_chat_session_id` 를 저장한다.

목적:

- 새로고침 후 대화 이력 복원
- 같은 세션으로 연속 질의

## 2. 세션 복원 시도

컴포넌트 마운트 시 프론트는 아래 API 를 호출하려고 한다.

```text
GET /api/llm/session/{session_id}/messages
```

현재 백엔드는 GET 과 POST 를 모두 지원한다. 프론트는 GET 기준으로 세션을 복원한다.

## 3. 사용자가 메시지를 보낼 때

프론트는 `POST /api/llm/chat` 으로 다음 payload 를 보낸다.

- `session_id`
- `messages`
- `latest_message`
- `context`

세션 ID 가 있으면 프론트는 과거 메시지를 거의 비우고, 백엔드가 Redis 에서 읽기를 기대한다.

## 4. 백엔드 채팅 처리

`domains/llm/router.py` 의 `llm_chat()` 흐름:

1. 세션 ID 없으면 새로 생성
2. Redis 사용 가능하면 저장된 메시지 로드
3. `latest_message` 를 대화열에 추가
4. `LLMService.chat()` 로 Gemini 호출
5. 응답의 `actions` 추출
6. read-only 액션이면 서버에서 자동 실행
7. 결과를 `assistant_message`, `actions`, `data` 로 응답
8. 사용자/어시스턴트 메시지를 Redis 에 저장

## 5. 자동 실행되는 액션

백엔드가 안전한 조회 액션은 바로 실행한다.

- `list_vms`
- `list_nodes`
- `get_vm_detail`
- `list_templates`
- `list_storages`
- `list_networks`

이 결과는 응답의 `data` 필드에 담긴다.

프론트는 이 타입들을 다시 실행하지 않고, 조회용 카드 렌더링에 사용한다.

## 6. 사용자가 직접 실행해야 하는 액션

프론트는 자동 실행 대상이 아닌 액션만 “실행 후보”로 남긴다.

대표적으로:

- `create_vm`

사용자가 실행 버튼을 누르면:

```text
POST /api/llm/execute-action
```

이 API 는 `InfraActionService.execute_action()` 으로 전달된다.

## 7. `create_vm` 액션 흐름

`create_vm` 이 들어오면:

1. 액션 params 를 deploy request 형태로 변환
2. `DeploymentService.start_deployment_with_request()` 호출
3. 일반 배포와 같은 task 가 시작
4. 결과로 `task_id` 반환

즉 LLM VM 생성은 결국 일반 `/api/deploy` 흐름의 다른 진입점이다.

## 8. 현재 구현의 중요한 제한

### ISO 기반 안내

현재 `create_vm` 경로는 `template_id` 기반 생성만 허용한다. 템플릿 선택 전에는 조회 액션으로 후보를 모으고, 템플릿이 확정된 뒤에만 생성 액션을 낸다.

### Redis 선택 의존

Redis 가 없으면 세션 저장/복원 경험이 약해진다.

### 프론트/백엔드 세션 이력 API 불일치

현재는 해소됐다. 외부 클라이언트도 GET 경로를 기준으로 맞추는 편이 안전하다.

## 9. 운영자가 봐야 할 포인트

- LLM 이 제안한 액션 타입과 실제 인프라 기능이 일치하는지
- `create_vm` payload 가 일반 deploy payload 와 같은 전제조건을 만족하는지
- 조회 액션 자동 실행 결과가 프론트 렌더링 포맷과 맞는지
