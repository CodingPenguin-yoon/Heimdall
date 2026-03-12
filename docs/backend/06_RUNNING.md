# Running the Backend

이 문서는 프론트 없이 백엔드만 따로 실행하고 확인하는 방법을 정리한다.

## 1. 준비

필수:

- `python3`
- `terraform`
- `ansible-playbook`
- 루트 `.env`

백엔드는 시작 시 루트 `.env` 를 직접 읽는다.

## 2. 설치

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

의존성 목록은 `backend/requirements.txt` 기준이다.

주요 패키지:

- `fastapi`
- `uvicorn[standard]`
- `python-dotenv`
- `pydantic`
- `pyyaml`
- `requests`
- `redis`

## 3. 실행

```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

`run.sh` 없이도 동작하지만, Terraform/Ansible CLI 는 여전히 시스템에 있어야 한다.

## 4. 확인용 호출

### Health

```bash
curl http://localhost:8000/health
```

### 서버 목록

```bash
curl http://localhost:8000/api/servers
```

### 작업 목록

```bash
curl "http://localhost:8000/api/tasks?limit=20"
```

### SSE 확인

```bash
curl -N http://localhost:8000/api/tasks/stream
```

## 5. 백엔드만 볼 때 유용한 파일

- `backend/app/main.py`
- `backend/app/domains/*`
- `backend/app/services/*`
- `backend/data/task_history.json`

## 6. 자주 보는 문제

### Proxmox 설정 누락

`PROXMOX_API_URL`, `PROXMOX_API_TOKEN_ID`, `PROXMOX_API_TOKEN_SECRET` 가 비어 있으면 Proxmox 조회가 사실상 무의미해진다.

### CLI 미설치

Terraform / Ansible 서비스는 subprocess 로 명령을 실행한다. Python 패키지와 별개로 시스템 명령이 필요하다.

### CORS 혼동

브라우저에서 프론트를 다른 호스트/포트로 띄우면 CORS 가 막힐 수 있다. 백엔드 기본 허용 origin 은 `FRONTEND_PORT` 기반 localhost 계열만 포함한다.

### LLM 세션 복원 실패

현재는 `GET /api/llm/session/{id}/messages` 와 `POST /api/llm/session/{id}/messages` 를 모두 지원한다. 세션 복원이 안 되면 Redis 설정과 브라우저 저장된 `session_id` 를 먼저 확인한다.

## 7. 개발 시 추천 확인 순서

1. `/health`
2. `/api/servers`
3. `/api/templates`
4. `/api/network/ip-pool/config`
5. `/api/tasks`
6. 실제 `/api/deploy`

## 8. 운영상 기억할 점

- 작업 이력은 JSON 파일 persistence 가 전부다.
- 이벤트 버퍼는 메모리 기반이라 프로세스 재시작 시 초기화된다.
- 백엔드가 살아 있어도 Proxmox, Terraform, SSH, Ansible 중 하나가 깨지면 배포는 실패할 수 있다.
