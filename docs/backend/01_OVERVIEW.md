# Backend Overview

## 1. 역할

이 백엔드는 네 가지 역할을 수행한다.

1. Proxmox 리소스 조회와 제어
2. Terraform 기반 VM 배포 orchestration
3. Ansible 기반 후처리 구성
4. 작업 상태/SSE/LLM 인터페이스 제공

## 2. 진입점

실제 진입점은 `backend/app/main.py` 다.

여기서:

- 루트 `.env` 를 로드한다
- CORS 를 설정한다
- 라우터를 등록한다

등록되는 라우터:

- deploy
- task
- proxmox
- llm

## 3. 디렉터리 기준 주요 구성

### `backend/app/domains`

HTTP 라우트와 도메인별 request/response 모델이 있다.

- `deploy`
- `task`
- `proxmox`
- `llm`

### `backend/app/services`

실제 작업을 수행하는 서비스 레이어다.

- `deployment`
- `terraform`
- `ansible`
- `proxmox`
- `network`
- `task`
- `llm`

### `backend/data`

작업 이력 저장 파일이 위치한다.

- `task_history.json`

## 4. 현재 백엔드의 성격

이 프로젝트는 “API 서버가 외부 인프라 도구를 orchestration 하는 형태”에 가깝다.

즉:

- 요청을 받으면
- 백그라운드 작업을 등록하고
- Terraform CLI 를 실행하고
- 결과를 읽어
- 필요하면 Ansible CLI 를 실행한다

따라서 성공 여부는 Python 코드만이 아니라 아래 요소에도 좌우된다.

- 로컬 CLI 설치 상태
- `.env` 값
- Proxmox API 접근성
- SSH 키 존재 여부
- 템플릿 내부 guest agent / cloud-init 상태

## 5. 상태 저장 방식

TaskManager 는 싱글톤이다.

저장 위치:

- 메모리: 현재 실행 중 이벤트/상태
- 파일: `backend/data/task_history.json`

제공 기능:

- 상태 변경
- 로그 append
- 진행률 업데이트
- SSE 이벤트 버퍼
- 자동 아카이브

## 6. 가장 중요한 운영 리스크

- Terraform 과 Ansible 을 요청 처리 흐름에서 직접 셸 아웃한다.
- 동적 inventory 는 고정 경로 `infra/ansible/inventory.yml` 을 덮어쓴다.
- IP 사용 가능 확인은 `ping` 기반이다.
- LLM, 프론트 API 헬퍼, Terraform 파일 사이에 일부 경로 불일치가 남아 있다.

## 7. 문서 읽는 순서 추천

처음 보는 경우:

1. 이 문서
2. [02_ARCHITECTURE.md](02_ARCHITECTURE.md)
3. [05_DEPLOYMENT_FLOW.md](05_DEPLOYMENT_FLOW.md)
4. [03_API_ENDPOINTS.md](03_API_ENDPOINTS.md)
