# Backend

현재 백엔드는 FastAPI 기반이며, 구조는 `domains/*`, `integrations/*`, `shared/*`, `alembic` 으로 나뉜다.

## 현재 구조

- `app/domains/deploy`
  - 배포 요청과 Terraform/Ansible 오케스트레이션
- `app/domains/proxmox`
  - Proxmox 조회, monitoring, instance lifecycle, resize
- `app/domains/task`
  - task 상태/로그/SSE
- `app/domains/llm`
  - LLM Assistant
- `app/integrations/terraform`
  - Terraform CLI 연동
- `app/integrations/ansible`
  - Ansible CLI 연동
- `app/shared`
  - task 저장소, platform DB, IP pool 유틸
- `alembic`
  - platform state DB migration

## 현재 활성 기능

- `POST /api/deploy`
- task 상태/로그/목록/SSE
- Proxmox server/template/vm/storage/network 조회
- monitoring
- IP pool 조회
- instance `terminate`
- instance `action` (`start`, `shutdown`, `stop`, `reboot`)
- instance resource update (`cpu`, `memory`)
- LLM Assistant

## 상태 저장

- task persistence: `data/platform_state.db`
- legacy import source: `data/task_history.json`
- migration: `cd backend && alembic upgrade head`

## 실행

루트에서:

```bash
pnpm backend
```

백엔드 디렉터리에서 직접:

```bash
. venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

루트 `.env` 를 자동으로 로드한다.
