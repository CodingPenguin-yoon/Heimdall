# Change Summary 2026-03-12

이 문서는 현재 브랜치에서 반영된 주요 구조 변경을 빠르게 파악하기 위한 요약이다. 세부 동작 설명은 각 개별 문서를 우선 본다.

## 1. 핵심 결정

- VM 생성 표준 경로를 템플릿 클론 기반으로 단일화했다.
- ISO 직접 생성 경로와 관련 레거시 UI, API, LLM 액션, Terraform 변수는 제거했다.
- 인스턴스 정리 표준 경로는 `/api/instances/terminate` 로 유지하고 `/destroy` 계열 흔적은 정리했다.
- Ansible 은 더 이상 `ignore_errors` 로 실패를 숨기지 않고 즉시 실패하도록 맞췄다.

## 2. 백엔드 변경

- 배포 요청은 `template_id` 기반 경로만 허용한다.
- 배포 서비스 메타데이터와 Terraform 입력에서 ISO 관련 값을 제거했다.
- Proxmox 조회 API 에서 ISO 이미지 목록 엔드포인트를 제거했다.
- LLM 인프라 액션에서 `list_iso_images` 를 제거하고 `create_vm` 도 템플릿 기반만 허용하도록 맞췄다.
- `/api/llm/session/{session_id}/messages` 는 GET 과 POST 를 모두 지원하도록 정리했다.
- 사용되지 않던 일부 `services/llm` 중복 구현 파일을 삭제했다.

관련 파일:

- `backend/app/domains/deploy/router.py`
- `backend/app/services/deployment/service.py`
- `backend/app/domains/proxmox/router.py`
- `backend/app/services/proxmox/__init__.py`
- `backend/app/domains/llm/router.py`
- `backend/app/domains/llm/commands/infra_action.py`

## 3. 프론트엔드 변경

- VM 생성 화면에서 ISO 선택 UI 를 제거하고 템플릿 선택만 남겼다.
- 죽은 `/destroy` 호출을 제거하고 현재 백엔드 표준 경로에 맞췄다.
- LLM 인프라 채팅 화면에서 ISO 관련 자동 액션과 결과 프리뷰를 제거했다.
- 사용되지 않던 레거시 컴포넌트를 정리했다.

관련 파일:

- `frontend/src/App.jsx`
- `frontend/src/components/CreateInstanceWizard.jsx`
- `frontend/src/components/LlmInfraChat.jsx`
- `frontend/src/services/api.js`

## 4. 인프라 변경

- Terraform 에서 더 이상 쓰지 않는 `iso_file`, `cloudinit_user_data` 변수를 제거했다.
- Terraform 서비스에서 미사용 `destroy()` 메서드를 제거했다.
- Ansible 플레이북은 실패를 감추지 않도록 정리했다.
- 인프라 표준 디렉터리는 `infra/terraform`, `infra/ansible` 기준으로 문서화했다.

관련 파일:

- `infra/terraform/main.tf`
- `infra/ansible/playbook.yml`
- `backend/app/services/terraform/__init__.py`

## 5. 문서 재작성

- `docs/` 전체를 현재 코드 기준으로 다시 정리했다.
- 운영 기준은 "현재 구현된 동작" 우선으로 맞췄다.
- 백엔드 구조, API, 배포 흐름, LLM 흐름, 로컬 실행, 환경변수, 템플릿 준비 문서를 모두 최신화했다.
- 프로젝트 전용 멀티 에이전트 설정 문서와 프롬프트 템플릿도 추가했다.

주요 문서:

- `docs/README.md`
- `docs/LOCAL_RUN_GUIDE.md`
- `docs/ENV_SETTINGS_EXPLAINED.md`
- `docs/VM_CREATION_METHODS.md`
- `docs/TEMPLATE_PREPARATION.md`
- `docs/backend/03_API_ENDPOINTS.md`
- `docs/backend/05_DEPLOYMENT_FLOW.md`
- `docs/flows/01_DEPLOYMENT_WEB_TO_VM.md`
- `.codex/config.toml`
- `.codex/PROMPTS.md`
- `AGENTS.md`

## 6. 현재 운영 의미

- 이 저장소는 이제 "템플릿 준비 -> 클론 배포 -> Ansible 후처리" 경로만 전제로 한다.
- 운영 품질은 Proxmox 템플릿 상태, cloud-init 설정, SSH 접근성에 직접적으로 의존한다.
- ISO 직접 설치가 필요하면 별도 설계와 구현을 다시 추가해야 한다.

## 7. 검증

다음 검증을 통과했다.

- `frontend`: `npm run build`
- Python: 수정된 FastAPI/서비스 파일 `py_compile`
- Ansible: `ansible-playbook --syntax-check infra/ansible/playbook.yml -i localhost,`
