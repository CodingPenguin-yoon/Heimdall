# Backend

현재 백엔드는 FastAPI 기반이며, 구조는 `domains/*`, `integrations/*`, `shared/*`, `alembic` 으로 나뉜다.
Heimdall 관점에서는 Proxmox/Terraform/Ansible 이 VM engine 이고, GitLab inventory/webhook 은 선택형 control-plane 기능이다.

## 현재 구조

- `app/domains/deploy`
  - 배포 요청과 Terraform/Ansible 오케스트레이션
- `app/domains/gitlab`
  - GitLab inventory 조회/sync, 프로젝트 생성, 프로젝트 설정 관리
- `app/domains/proxmox`
  - Proxmox 조회, monitoring, instance lifecycle, resize
- `app/domains/task`
  - task 상태/로그/SSE
- `app/domains/webhooks`
  - GitLab system hook ingress
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
- GitLab inventory 조회 / 수동 sync
- GitLab namespace 조회 / 프로젝트 생성
- GitLab 프로젝트별 설정 조회 / 저장
- GitLab 프로젝트별 수동 staging deploy 요청 기록 / task 추적 시작
- GitLab 프로젝트별 `.heimdall/project.yaml` 최소 검증 상태 조회
- GitLab system hook 수신 후 inventory sync
- instance `terminate`
- instance `action` (`start`, `shutdown`, `stop`, `reboot`)
- instance resource update (`cpu`, `memory`)
- LLM Assistant

현재 GitLab 관련 기능은 실제 사용 가능하지만 선택 사항이다.
bootstrap 실행은 아직 이 백엔드에서 제공하지 않고, `Deploy Staging` 의 현재 슬라이스는 valid `.heimdall/project.yaml` 을 통과한 프로젝트만 수동 요청을 task로 기록하는 수준까지만 제공한다.
실제 VM/DB/Terraform/Ansible 오케스트레이션은 다음 단계에서 연결한다.

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

## GitLab / Webhook 메모

- GitLab API 기능에는 `GITLAB_BASE_URL`, `GITLAB_API_TOKEN` 이 필요하다
- System Hook 검증에는 `GITLAB_SYSTEM_HOOK_SECRET` 이 필요하다
- 외부 GitLab 이 접근할 수 있는 webhook 주소를 쓰려면 `PLATFORM_PUBLIC_BASE_URL` 을 함께 맞춘다
- TLS 비활성화 계열 설정은 테스트 환경에서만 임시로 사용하는 편이 안전하다
