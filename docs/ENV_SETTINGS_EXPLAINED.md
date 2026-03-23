# Environment Settings Explained

이 문서는 현재 코드가 실제로 읽는 환경변수만 정리한다.

## 서버 실행

| 변수 | 기본값 | 설명 |
| --- | --- | --- |
| `BACKEND_PORT` | `8000` | backend 실행 포트 |
| `FRONTEND_PORT` | `5173` | frontend 개발 포트, backend CORS 허용 포트 |
| `VITE_API_TIMEOUT_MS` | `120000` | frontend API timeout |

## Proxmox / Terraform

| 변수 | 기본값 | 설명 |
| --- | --- | --- |
| `PROXMOX_API_URL` | 없음 | Proxmox API URL |
| `PROXMOX_API_TOKEN_ID` | 없음 | Proxmox API token id |
| `PROXMOX_API_TOKEN_SECRET` | 없음 | Proxmox API token secret |
| `PROXMOX_TLS_INSECURE` | `false` | TLS 검증 비활성화 여부 |
| `TF_VAR_proxmox_api_url` | 없음 | Terraform provider 입력 |
| `TF_VAR_proxmox_api_token_id` | 없음 | Terraform provider 입력 |
| `TF_VAR_proxmox_api_token_secret` | 없음 | Terraform provider 입력 |
| `TF_VAR_proxmox_tls_insecure` | 없음 | Terraform provider 입력 |
| `TF_AUTO_MIGRATE_LEGACY_STATE` | `false` | legacy terraform state 자동 이관 |
| `TF_AUTO_MIGRATE_LEGACY_STATE_FORCE` | `false` | state 존재 시 강제 이관 |
| `TF_AUTO_MIGRATE_LEGACY_STATE_STRICT` | `false` | 이관 실패 시 배포 중단 |

## Ansible / SSH

| 변수 | 기본값 | 설명 |
| --- | --- | --- |
| `ANSIBLE_SSH_USER` | `root` | Ansible 접속 사용자 |
| `ANSIBLE_SSH_PRIVATE_KEY_FILE` | 없음 | inventory 에 넣을 개인키 경로 |
| `ANSIBLE_SSH_PUBLIC_KEY_FILE` | `~/.ssh/id_rsa.pub` 또는 `~/.ssh/id_ed25519.pub` | cloud-init 주입용 공개키 |

## IP Pool

| 변수 | 기본값 | 설명 |
| --- | --- | --- |
| `IP_POOL_START` | 없음 | IP 풀 시작 주소 |
| `IP_POOL_END` | 없음 | IP 풀 끝 주소 |
| `IP_GATEWAY` | 없음 | 게이트웨이 |
| `IP_SUBNET` | `24` | subnet 크기 |

## Task / Platform DB

| 변수 | 기본값 | 설명 |
| --- | --- | --- |
| `TASK_EVENT_BUFFER_SIZE` | `5000` | task SSE 이벤트 버퍼 크기 |
| `TASK_AUTO_ARCHIVE_DAYS` | `14` | 완료 task 자동 아카이브 일수 |
| `TASK_AUTO_ARCHIVE_CHECK_INTERVAL_SECONDS` | `300` | 아카이브 검사 주기 |
| `PLATFORM_STATE_DATABASE_URL` | 없음 | platform state DB SQLAlchemy URL |
| `PLATFORM_STATE_DB_PATH` | `data/platform_state.db` | SQLite 경로 fallback |

메모:

- 현재 task persistence 는 `data/platform_state.db` 기준이다.
- legacy `data/task_history.json` 은 초기 import source 로만 사용된다.
- `PLATFORM_STATE_DATABASE_URL` 이 있으면 그 값을 우선 사용한다.
- URL 이 없으면 `PLATFORM_STATE_DB_PATH` 또는 기본값 `data/platform_state.db` 를 사용한다.

## GitLab 준비용 설정

이 항목들은 아직 GitLab inventory/API 구현 전이라 현재 런타임에서 적극 사용되지는 않는다. 다음 단계 GitLab 연동을 바로 시작할 수 있게 준비용으로 문서화하는 값들이다.

| 변수 | 기본값 | 설명 |
| --- | --- | --- |
| `GITLAB_BASE_URL` | 없음 | GitLab base URL (`https://gitlab.example.com`) |
| `GITLAB_API_TOKEN` | 없음 | backend 가 GitLab API 호출에 쓸 토큰 |
| `GITLAB_VERIFY_SSL` | `true` | GitLab TLS 검증 여부 |
| `GITLAB_DEFAULT_NAMESPACE_PATH` | `heimdall` | GitLab 프로젝트 생성 시 강제할 기본 namespace path/name |
| `GITLAB_SYSTEM_HOOK_SECRET` | 없음 | System Hook 검증용 secret |
| `PLATFORM_PUBLIC_BASE_URL` | 없음 | GitLab 이 backend webhook 을 호출할 플랫폼 공개 URL |

## LLM / Redis

| 변수 | 기본값 | 설명 |
| --- | --- | --- |
| `GEMINI_API_KEY` | 없음 | Gemini API 키 |
| `GEMINI_MODEL_NAME` | `gemini-2.0-flash` | 모델명 |
| `GEMINI_TIMEOUT_SECONDS` | `30` | LLM timeout |
| `REDIS_HOST` | `localhost` | Redis host |
| `REDIS_PORT` | `6379` | Redis port |
| `REDIS_DB` | `0` | Redis DB 번호 |
| `REDIS_PASSWORD` | 없음 | Redis 비밀번호 |
| `CHAT_SESSION_TTL_SECONDS` | `604800` | 세션 TTL |
| `CHAT_MAX_MESSAGES` | `100` | 저장 메시지 최대 개수 |

## 권장 `.env` 베이스라인

```dotenv
BACKEND_PORT=8000
FRONTEND_PORT=5173

PROXMOX_API_URL=https://your-proxmox.example.com:8006/api2/json
PROXMOX_API_TOKEN_ID=root@pam!token-name
PROXMOX_API_TOKEN_SECRET=replace-me
PROXMOX_TLS_INSECURE=true

ANSIBLE_SSH_USER=root
ANSIBLE_SSH_PRIVATE_KEY_FILE=/absolute/path/to/id_rsa
ANSIBLE_SSH_PUBLIC_KEY_FILE=/absolute/path/to/id_rsa.pub

PLATFORM_STATE_DB_PATH=data/platform_state.db

GITLAB_BASE_URL=https://gitlab.example.com
GITLAB_API_TOKEN=replace-me
GITLAB_VERIFY_SSL=true
GITLAB_DEFAULT_NAMESPACE_PATH=heimdall
GITLAB_SYSTEM_HOOK_SECRET=replace-me
PLATFORM_PUBLIC_BASE_URL=https://platform.example.com

IP_POOL_START=192.168.2.100
IP_POOL_END=192.168.2.150
IP_GATEWAY=192.168.2.1
IP_SUBNET=24
```
