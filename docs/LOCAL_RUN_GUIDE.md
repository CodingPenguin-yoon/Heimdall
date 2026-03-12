# Local Run Guide

이 문서는 현재 저장소의 실제 실행 구조를 기준으로 로컬 개발 환경을 설명한다. 기준 파일은 `run.sh`, `backend/app/main.py`, `backend/requirements.txt`, `frontend/package.json` 이다.

## 1. 실행 전에 필요한 것

- `python3`
- `node` / `npm`
- `terraform`
- `ansible-playbook`
- Proxmox API 접근 정보
- VM 내부 접속에 사용할 SSH 키

이 저장소는 루트 `.env` 파일 의존성이 크다. `.env` 가 없으면 백엔드는 일부 기능만 뜰 수 있고, Proxmox 조회나 Terraform 배포는 정상 동작하지 않는다.

## 2. `.env` 준비

루트에 `.env` 파일을 만든다.

최소 권장 항목:

```dotenv
PROXMOX_API_URL=https://your-proxmox.example.com:8006
PROXMOX_API_TOKEN_ID=root@pam!token-name
PROXMOX_API_TOKEN_SECRET=replace-me
PROXMOX_TLS_INSECURE=true

ANSIBLE_SSH_USER=root
ANSIBLE_SSH_PRIVATE_KEY_FILE=/absolute/path/to/private_key
ANSIBLE_SSH_PUBLIC_KEY_FILE=/absolute/path/to/public_key.pub

IP_POOL_START=192.168.2.100
IP_POOL_END=192.168.2.150
IP_GATEWAY=192.168.2.1
IP_SUBNET=24

BACKEND_PORT=8000
FRONTEND_PORT=5173
```

주의:

- 저장소에는 현재 `env.example` 이 없다.
- `run.sh` 는 `env.example` 존재 여부를 확인하지만, 실제 예제 파일은 체크인되어 있지 않다.
- Terraform 쪽 `TF_VAR_proxmox_*` 값은 백엔드 서비스와 `run.sh` 가 `PROXMOX_*` 에서 자동 매핑한다.

## 3. 가장 쉬운 실행 방법

프로젝트 루트에서:

```bash
./run.sh
```

`run.sh` 가 실제로 하는 일:

1. `backend/venv` 가 없으면 생성한다.
2. `backend/requirements.txt` 를 기준으로 백엔드 의존성을 설치한다.
3. `frontend/node_modules` 가 없으면 `npm install` 을 실행한다.
4. 루트 `.env` 를 읽어 `TF_VAR_proxmox_*` 환경변수까지 export 한다.
5. 백엔드를 `uvicorn app.main:app --host 0.0.0.0 --port $BACKEND_PORT` 로 실행한다.
6. 프론트엔드를 `npm run dev -- --port $FRONTEND_PORT` 로 실행한다.
7. `/health` 로 백엔드 헬스체크를 확인한다.

로그 파일:

- `backend.log`
- `frontend.log`

접속 경로:

- 프론트엔드: `http://localhost:${FRONTEND_PORT:-5173}`
- 백엔드 API: `http://localhost:${BACKEND_PORT:-8000}`
- Swagger UI: `http://localhost:${BACKEND_PORT:-8000}/docs`

## 4. 수동으로 나눠서 실행하기

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

백엔드는 시작 시 루트 `.env` 를 자동 로드한다.

### Frontend

```bash
cd frontend
npm install
npm run dev -- --port 5173
```

프론트는 `/api` 기준으로 백엔드에 붙는다.

## 5. 시작 후 확인할 것

### 백엔드 기본 응답

```bash
curl http://localhost:8000/health
```

예상 응답:

```json
{"status":"healthy","service":"backend"}
```

### Proxmox 연결 확인

```bash
curl http://localhost:8000/api/servers
```

서버 목록이 오면 Proxmox API 연결은 기본적으로 살아 있다.

### 프론트 핵심 화면

- `/` : VM 생성 마법사
- `/list` : 인스턴스 목록
- `/tasks` : 배포 작업 보드
- `/monitoring` : 노드 모니터링
- `/assistant` : LLM 인프라 어시스턴트

## 6. 배포를 실제로 성공시키기 위한 전제

현재 구현은 템플릿 클론 기반 배포가 중심이다.

필수에 가까운 조건:

- Proxmox 쪽에 클론 가능한 VM 템플릿이 있어야 한다.
- 템플릿 안에 cloud-init 이 동작해야 한다.
- DHCP 사용 시 `qemu-guest-agent` 가 템플릿에 설치되어 있어야 Terraform 출력에서 IP를 안정적으로 얻는다.
- Ansible까지 자동으로 이어가려면 SSH 공개키 주입이 가능해야 한다.
- 고정 IP를 쓰려면 `vm_ip` 는 CIDR 형식이어야 한다. 예: `192.168.2.120/24`

## 7. 자주 막히는 지점

### `terraform` 또는 `ansible-playbook` 명령을 못 찾는 경우

로컬 PATH 에 CLI 가 없다. 백엔드는 직접 셸 아웃하므로 Python 패키지 설치만으로 해결되지 않는다.

### VM은 생겼는데 Ansible 이 건너뛰는 경우

Terraform 출력에서 VM IP 를 못 읽으면 백엔드가 Ansible 단계를 건너뛴다. DHCP 배포에서는 템플릿 내부 `qemu-guest-agent` 설치 여부를 먼저 확인한다.

### IP 사용 가능 확인이 부정확한 경우

현재 IP 풀 체크는 ARP/lease 조회가 아니라 `ping` 기반이다. 방화벽이나 ICMP 차단 환경에서는 false negative 가 날 수 있다.

### 프론트는 떠 있는데 API 호출이 실패하는 경우

`backend/app/main.py` 의 CORS 허용 대상은 기본적으로 `localhost` 와 `127.0.0.1` 기반 포트뿐이다. 다른 도메인이나 외부 호스트에서 접근하면 추가 설정이 필요하다.

## 8. 현재 구현에서 알아둘 제한

- `/api/destroy` 백엔드 엔드포인트는 현재 없다.
- 인스턴스 종료/삭제의 활성 경로는 `/api/instances/terminate` 이다.
- ISO 기반 생성은 현재 지원되지 않으며, 관련 요청은 백엔드에서 거절한다.
- 작업 상태는 메모리 + `backend/data/task_history.json` 에 저장된다. 프로세스를 완전히 재시작하면 런타임 이벤트 버퍼는 초기화된다.

## 9. 추천 확인 순서

1. `.env` 준비
2. `./run.sh`
3. `/health` 확인
4. `/api/servers` 확인
5. 템플릿 목록 확인
6. 템플릿 기반 VM 생성 테스트
7. `/tasks` 에서 Terraform / Ansible 로그 확인
