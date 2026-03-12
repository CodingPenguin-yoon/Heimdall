# Backend Docs

백엔드 문서는 현재 FastAPI 구현을 기준으로 정리했다. 시작점은 `backend/app/main.py` 이다.

## 문서 순서

1. [01_OVERVIEW.md](01_OVERVIEW.md): 백엔드가 담당하는 일과 주요 모듈
2. [02_ARCHITECTURE.md](02_ARCHITECTURE.md): 현재 레이어 구조와 남아 있는 설계 불일치
3. [03_API_ENDPOINTS.md](03_API_ENDPOINTS.md): 실제 활성 엔드포인트 목록
4. [04_SERVICES.md](04_SERVICES.md): 핵심 서비스 클래스 설명
5. [05_DEPLOYMENT_FLOW.md](05_DEPLOYMENT_FLOW.md): 배포 요청이 Terraform/Ansible 로 이어지는 순서
6. [06_RUNNING.md](06_RUNNING.md): 백엔드만 따로 실행하고 디버깅하는 방법

## 핵심 사실

- 모든 도메인 라우트는 `/api` prefix 로 등록된다.
- 루트 엔드포인트는 `/` 와 `/health` 만 별도 제공된다.
- 작업 상태는 메모리 + `backend/data/task_history.json` 에 저장된다.
- Terraform / Ansible / Proxmox 는 Python 라이브러리 래퍼가 아니라 외부 CLI 또는 HTTP API 호출에 크게 의존한다.
- 현재 활성 LLM 도메인은 `backend/app/domains/llm/*` 이다.
