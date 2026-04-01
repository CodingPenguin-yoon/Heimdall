# Local Run Guide

이 문서는 현재 저장소를 로컬에서 띄우는 최소 절차만 정리한다.

## 1. Prerequisites

로컬에 아래가 설치돼 있어야 한다.

- `python3`
- `pnpm`
- `terraform`
- `ansible-playbook`

백엔드는 로컬 CLI 를 직접 실행하므로 Python 패키지만 설치돼 있어도 충분하지 않다.

## 2. `.env`

- 위치: 저장소 루트 `.env`
- 백엔드는 시작 시 루트 `.env` 를 자동 로드한다.

최소한 아래 계열은 준비해야 한다.

- `PROXMOX_*`
- `ANSIBLE_SSH_*`
- 필요 시 `IP_POOL_*`
- 필요 시 `GEMINI_*`

GitLab Workspace, inventory sync, project 생성, system hook 연동을 쓸 때만 아래를 추가한다.

- `GITLAB_BASE_URL`
- `GITLAB_API_TOKEN`
- `GITLAB_VERIFY_SSL`
- `GITLAB_DEFAULT_NAMESPACE_PATH`
- `GITLAB_SYSTEM_HOOK_SECRET`
- `PLATFORM_PUBLIC_BASE_URL`

## 3. Python venv 준비

```bash
cd backend
python3 -m venv venv
. venv/bin/activate
pip install -r requirements.txt
```

## 4. Platform DB migration

task persistence 는 `data/platform_state.db` 를 쓴다.

- 현재 DB: `data/platform_state.db`
- legacy import source: `data/task_history.json`

최초 실행 전 또는 migration 변경 후:

```bash
cd backend
. venv/bin/activate
alembic upgrade head
```

## 5. Run

루트에서:

```bash
pnpm backend
pnpm frontend
```

또는 둘 다 함께:

```bash
pnpm dev
```

기본 포트:

- backend: `8000`
- frontend: `5173`

## 6. Quick Check

1. `http://127.0.0.1:8000/health`
2. 프론트 열기
3. 서버/템플릿 목록 확인
4. Task Board 진입 확인
5. 선택 사항: GitLab Workspace 탭에서 inventory 조회 또는 수동 sync 확인

GitLab System Hook 까지 확인하려면 GitLab 에서 backend 의 `POST /api/webhooks/gitlab/system` 을 등록하고,
`X-Gitlab-Token` 에 `GITLAB_SYSTEM_HOOK_SECRET` 과 같은 값을 넣어야 한다.

## 7. VM 준비 조건

이 섹션은 Heimdall 의 low-level VM engine 조건이다. GitLab Workspace 와 별개로,
실제 VM 배포/후처리는 여전히 Proxmox + Terraform + Ansible 경로를 사용한다.

- Proxmox 쪽에 clone 가능한 템플릿이 있어야 한다
- 템플릿에 cloud-init 이 동작해야 한다
- Ansible 까지 자동으로 이어가려면 SSH 공개키 주입이 가능해야 한다
- DHCP 배포에서 IP 자동 감지를 안정적으로 하려면 `qemu-guest-agent` 가 필요하다
- static IP 는 반드시 CIDR 형식이어야 한다
  - 예: `192.168.2.120/24`

## 8. 자주 막히는 지점

### GitLab Workspace 가 비어 있거나 sync 가 비활성화된 경우

대개 `GITLAB_BASE_URL` 또는 `GITLAB_API_TOKEN` 이 비어 있거나 형식이 맞지 않은 경우다.

### GitLab System Hook 이 403 또는 503 으로 실패하는 경우

- `GITLAB_SYSTEM_HOOK_SECRET` 과 GitLab hook token 값이 일치하는지 확인한다
- 외부 GitLab 이 접근할 수 있는 `PLATFORM_PUBLIC_BASE_URL` 과 ingress 경로가 맞는지 확인한다
- bootstrap / Deploy Staging 실행 기능은 아직 없으므로 hook 은 inventory 반영까지만 담당한다

### `terraform` 또는 `ansible-playbook` 미설치

백엔드는 로컬 PATH 의 CLI 를 직접 실행한다.

### DHCP 배포에서 Ansible 단계가 건너뛰는 경우

대개 guest agent 가 없어서 Terraform 이 VM IP 를 안정적으로 읽지 못한 경우다.

### static IP 입력 오류

CIDR 없이 `192.168.2.120` 만 넣으면 실패한다.

### backend 가 task DB 때문에 안 뜨는 경우

아래를 먼저 실행한다.

```bash
cd backend
. venv/bin/activate
alembic upgrade head
```

## 9. 안전한 `.env` 운영 메모

- `.env` 는 커밋하지 않는다
- `GITLAB_API_TOKEN` 은 API 접근에 필요한 최소 권한만 준다
- `PROXMOX_TLS_INSECURE=true` 나 `GITLAB_VERIFY_SSL=false` 는 격리된 테스트 환경에서만 임시로 쓴다
- `ANSIBLE_SSH_PRIVATE_KEY_FILE` 은 절대경로를 사용하고 권한을 제한한다
