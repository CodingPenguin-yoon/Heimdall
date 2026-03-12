# Documentation Index

이 디렉터리는 현재 코드베이스를 기준으로 다시 정리한 운영 문서 모음이다. 문서 내용은 `backend`, `frontend`, `infra`, `run.sh` 의 실제 구현을 우선 기준으로 한다.

## Start Here

- [CHANGE_SUMMARY_2026-03-12.md](CHANGE_SUMMARY_2026-03-12.md): 이번 구조 정리와 템플릿 전용 전환 요약
- [LOCAL_RUN_GUIDE.md](LOCAL_RUN_GUIDE.md): 로컬 실행, 필수 도구, `.env`, 점검 순서
- [ENV_SETTINGS_EXPLAINED.md](ENV_SETTINGS_EXPLAINED.md): 실제 코드가 읽는 환경변수 설명
- [VM_CREATION_METHODS.md](VM_CREATION_METHODS.md): 현재 지원되는 VM 생성 방식과 제한
- [TEMPLATE_PREPARATION.md](TEMPLATE_PREPARATION.md): 템플릿 기반 배포를 위한 Proxmox 준비
- [ANSIBLE_AUTOMATION.md](ANSIBLE_AUTOMATION.md): Ansible 인벤토리 생성과 플레이북 동작

## Backend

- [backend/README.md](backend/README.md)
- [backend/01_OVERVIEW.md](backend/01_OVERVIEW.md)
- [backend/02_ARCHITECTURE.md](backend/02_ARCHITECTURE.md)
- [backend/03_API_ENDPOINTS.md](backend/03_API_ENDPOINTS.md)
- [backend/04_SERVICES.md](backend/04_SERVICES.md)
- [backend/05_DEPLOYMENT_FLOW.md](backend/05_DEPLOYMENT_FLOW.md)
- [backend/06_RUNNING.md](backend/06_RUNNING.md)

## End-to-End Flows

- [flows/01_DEPLOYMENT_WEB_TO_VM.md](flows/01_DEPLOYMENT_WEB_TO_VM.md)
- [flows/02_LLM_INFRA_ASSISTANT_FLOW.md](flows/02_LLM_INFRA_ASSISTANT_FLOW.md)
- [flows/03_MONITORING_FLOW.md](flows/03_MONITORING_FLOW.md)

## Reading Notes

- 이 문서는 “의도한 설계”보다 “현재 구현된 동작”을 우선 설명한다.
- 문서와 코드가 충돌하면 코드를 우선 본다.
- 현재 구현에는 몇 가지 구조적 불일치가 남아 있다.
  - VM 생성은 현재 `template_id` 기반 경로만 지원하며, ISO 기반 생성 요청은 백엔드에서 거절한다.
  - `/api/llm/session/{id}/messages` 는 GET 과 POST 를 모두 지원하지만, 프론트는 GET 기준으로 사용한다.
  - 인스턴스 정리의 활성 경로는 `/api/instances/terminate` 이고, 별도 `/api/destroy` 라우트는 없다.
