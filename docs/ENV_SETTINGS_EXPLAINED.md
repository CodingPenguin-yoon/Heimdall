# Environment Settings Explained

이 문서는 현재 코드가 실제로 읽는 환경변수만 정리한다. 기준 파일은 `run.sh`, `backend/app/main.py`, `backend/app/services/*`, `frontend/src/services/api.js` 이다.

## 1. 핵심 요약

- 루트 `.env` 가 사실상 운영 중심 설정 파일이다.
- 백엔드는 시작 시 루트 `.env` 를 로드한다.
- `run.sh` 도 같은 `.env` 를 읽어 `TF_VAR_proxmox_*` 값을 export 한다.
- Terraform 관련 자격증명은 `PROXMOX_*` 로 넣어도 되고, 필요하면 `TF_VAR_proxmox_*` 로 직접 넣을 수도 있다.
- 저장소에는 현재 `env.example` 이 없다.

## 2. 서버 실행 관련

| 변수 | 기본값 | 사용 위치 | 설명 |
| --- | --- | --- | --- |
| `BACKEND_PORT` | `8000` | `run.sh` | `uvicorn` 실행 포트 |
| `FRONTEND_PORT` | `5173` | `run.sh`, `backend/app/main.py` | 프론트 개발 서버 포트, 백엔드 CORS 허용 포트 |
| `VITE_API_TIMEOUT_MS` | `120000` | `frontend/src/services/api.js` | 프론트 axios 타임아웃 |

주의:

- 백엔드는 `0.0.0.0` 로 바인딩하지만, CORS 허용 origin 은 기본적으로 `localhost` 와 `127.0.0.1` 만 포함한다.

## 3. Proxmox API 관련

| 변수 | 기본값 | 사용 위치 | 설명 |
| --- | --- | --- | --- |
| `PROXMOX_API_URL` | 없음 | ProxmoxService, TerraformService, `run.sh` | Proxmox API URL |
| `PROXMOX_API_TOKEN_ID` | 없음 | ProxmoxService, TerraformService, `run.sh` | API 토큰 ID |
| `PROXMOX_API_TOKEN_SECRET` | 없음 | ProxmoxService, TerraformService, `run.sh` | API 토큰 secret |
| `PROXMOX_TLS_INSECURE` | `false` in ProxmoxService | ProxmoxService, TerraformService, `run.sh` | TLS 검증 비활성화 여부 |
| `PROXMOX_API_CONNECT_TIMEOUT_SECONDS` | 없음 | ProxmoxService | 연결 타임아웃 |
| `PROXMOX_API_READ_TIMEOUT_SECONDS` | 없음 | ProxmoxService | 읽기 타임아웃 |
| `PROXMOX_API_TIMEOUT_SECONDS` | 없음 | ProxmoxService | 개별 타임아웃 미설정 시 fallback |

## 4. Terraform 관련

| 변수 | 기본값 | 사용 위치 | 설명 |
| --- | --- | --- | --- |
| `TF_VAR_proxmox_api_url` | 없음 | Terraform CLI subprocess | Terraform provider 입력값 |
| `TF_VAR_proxmox_api_token_id` | 없음 | Terraform CLI subprocess | Terraform provider 입력값 |
| `TF_VAR_proxmox_api_token_secret` | 없음 | Terraform CLI subprocess | Terraform provider 입력값 |
| `TF_VAR_proxmox_tls_insecure` | 없음 | Terraform CLI subprocess | Terraform provider 입력값 |
| `TF_AUTO_MIGRATE_LEGACY_STATE` | `false` | DeploymentService | legacy local state 자동 이관 여부 |
| `TF_AUTO_MIGRATE_LEGACY_STATE_FORCE` | `false` | DeploymentService | 대상 workspace 에 state 가 있어도 강제 push |
| `TF_AUTO_MIGRATE_LEGACY_STATE_STRICT` | `false` | DeploymentService | 이관 실패 시 배포 중단 여부 |

동작 메모:

- `backend/app/services/terraform/__init__.py` 가 `PROXMOX_*` 값을 보고 `TF_VAR_proxmox_*` 로 자동 매핑한다.
- 즉 `.env` 에 `PROXMOX_*` 만 있어도 Terraform 실행은 가능하다.
- workspace 별 state 를 사용하므로 요청별 `server_name` 이 중요하다.

## 5. Ansible / SSH 관련

| 변수 | 기본값 | 사용 위치 | 설명 |
| --- | --- | --- | --- |
| `ANSIBLE_SSH_USER` | `root` | DeploymentService, AnsibleService | Ansible 접속 사용자, cloud-init 주입 사용자 |
| `ANSIBLE_SSH_PRIVATE_KEY_FILE` | 없음 | AnsibleService | 동적 inventory 에 넣는 개인키 경로 |
| `ANSIBLE_SSH_PUBLIC_KEY_FILE` | `~/.ssh/id_rsa.pub` fallback `~/.ssh/id_ed25519.pub` | DeploymentService | Terraform cloud-init 으로 VM 에 주입할 공개키 |

주의:

- 공개키를 못 읽으면 Terraform 은 계속 진행하지만, 이후 Ansible SSH 접속이 실패할 수 있다.
- 개인키는 inventory 생성 시에만 들어간다.

## 6. IP Pool 관련

| 변수 | 기본값 | 사용 위치 | 설명 |
| --- | --- | --- | --- |
| `IP_POOL_START` | 없음 | NetworkService | IP 풀 시작 주소 |
| `IP_POOL_END` | 없음 | NetworkService | IP 풀 끝 주소 |
| `IP_GATEWAY` | 없음 | NetworkService | 게이트웨이 주소 |
| `IP_SUBNET` | `24` | NetworkService | CIDR subnet 크기 |

이 값들이 모두 있어야 `/api/network/ip-pool/*` 계열 엔드포인트가 의미 있게 동작한다.

제한:

- 사용 여부 확인은 DHCP lease 조회가 아니라 `ping` 기반이다.
- ICMP 차단 환경에서는 실제 사용 중인데도 사용 가능으로 보일 수 있다.

## 7. Task / SSE 관련

| 변수 | 기본값 | 사용 위치 | 설명 |
| --- | --- | --- | --- |
| `TASK_EVENT_BUFFER_SIZE` | `5000` | TaskManager | 메모리 이벤트 버퍼 크기 |
| `TASK_AUTO_ARCHIVE_DAYS` | `14` | TaskManager | 완료 작업 자동 아카이브 기준 일수 |
| `TASK_AUTO_ARCHIVE_CHECK_INTERVAL_SECONDS` | `300` | TaskManager | 자동 아카이브 검사 주기 |

작업 기록은 `backend/data/task_history.json` 에 저장된다.

## 8. LLM / Redis 관련

| 변수 | 기본값 | 사용 위치 | 설명 |
| --- | --- | --- | --- |
| `GEMINI_API_KEY` | 없음 | `backend/app/services/llm/llm_core.py` | Gemini 호출 키 |
| `GEMINI_MODEL_NAME` | `gemini-2.0-flash` | LLMCore | 사용 모델명 |
| `GEMINI_TIMEOUT_SECONDS` | `30` | LLMCore | 요청 타임아웃 |
| `REDIS_HOST` | `localhost` | ChatSessionService | Redis 호스트 |
| `REDIS_PORT` | `6379` | ChatSessionService | Redis 포트 |
| `REDIS_DB` | `0` | ChatSessionService | Redis DB 번호 |
| `REDIS_PASSWORD` | 없음 | ChatSessionService | Redis 비밀번호 |
| `CHAT_SESSION_TTL_SECONDS` | `604800` | ChatSessionService | 세션 TTL |
| `CHAT_MAX_MESSAGES` | `100` | ChatSessionService | 저장 메시지 최대 개수 |

메모:

- Redis 가 없어도 LLM 채팅 엔드포인트는 뜰 수 있지만, 세션 이력 저장은 제한된다.
- 현재 활성 LLM 라우트는 `backend/app/domains/llm/*` 쪽이다.

## 9. 권장 `.env` 베이스라인

```dotenv
BACKEND_PORT=8000
FRONTEND_PORT=5173

PROXMOX_API_URL=https://your-proxmox.example.com:8006
PROXMOX_API_TOKEN_ID=root@pam!token-name
PROXMOX_API_TOKEN_SECRET=replace-me
PROXMOX_TLS_INSECURE=true

ANSIBLE_SSH_USER=root
ANSIBLE_SSH_PRIVATE_KEY_FILE=/absolute/path/to/id_rsa
ANSIBLE_SSH_PUBLIC_KEY_FILE=/absolute/path/to/id_rsa.pub

IP_POOL_START=192.168.2.100
IP_POOL_END=192.168.2.150
IP_GATEWAY=192.168.2.1
IP_SUBNET=24
```

LLM 기능까지 쓰려면 추가:

```dotenv
GEMINI_API_KEY=replace-me
GEMINI_MODEL_NAME=gemini-2.0-flash
GEMINI_TIMEOUT_SECONDS=30
```

Redis 세션 저장까지 쓰려면 추가:

```dotenv
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=
CHAT_SESSION_TTL_SECONDS=604800
CHAT_MAX_MESSAGES=100
```

## 10. 현재 문서화 대상에서 제외한 것

- 저장소 안에 실제 비밀값 예시는 적지 않는다.
- 사용 흔적이 없는 외부 배포 환경 변수는 문서화하지 않았다.
- 요청 payload 필드 중 환경변수가 아닌 값은 이 문서가 아니라 API/배포 플로우 문서를 참고한다.
