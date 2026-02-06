# 백엔드 개요

## 백엔드란?

이 프로젝트의 백엔드는 **FastAPI** 기반의 REST API 서버입니다. 프론트엔드에서 요청을 받아서 Terraform과 Ansible을 실행하여 Proxmox 인프라를 자동으로 배포하고 관리합니다.

## 주요 역할

1. **API 서버**: 프론트엔드와 통신하여 요청을 받고 응답을 반환
2. **Terraform 제어**: Proxmox 리소스 생성/수정/삭제를 Terraform으로 수행
3. **Ansible 제어**: 배포된 VM에 소프트웨어 설치 및 설정을 Ansible로 수행
4. **Proxmox 조회**: Proxmox API를 직접 호출하여 리소스 정보 조회
5. **작업 관리**: 배포 작업의 상태와 로그를 실시간으로 추적

## 기술 스택

- **FastAPI**: Python 기반의 현대적인 웹 프레임워크
- **Uvicorn**: ASGI 서버 (FastAPI 실행)
- **Pydantic**: 데이터 검증 및 직렬화
- **Python-dotenv**: 환경 변수 관리
- **Requests**: HTTP 클라이언트 (Proxmox API 호출)
- **PyYAML**: YAML 파일 처리 (Ansible inventory 생성)

## 전체 구조 (도메인 기반)

```
backend/
├── app/
│   ├── main.py                      # FastAPI 앱 진입점 (도메인 라우터 등록)
│   ├── domains/                     # 도메인별 API 라우터
│   │   ├── deploy/
│   │   │   └── router.py            # 배포 API (`POST /api/deploy`)
│   │   ├── task/
│   │   │   └── router.py            # 작업 상태/로그 API (`GET /api/status/*`, `/api/logs/*`)
│   │   ├── proxmox/
│   │   │   └── router.py            # Proxmox 조회/모니터링 API
│   │   └── llm/
│   │       └── router.py            # LLM 인프라 어시스턴트 API
│   └── services/                    # 도메인별 비즈니스 로직
│       ├── deployment/              # 배포 도메인
│       │   └── service.py           # DeploymentService (Terraform+Ansible 통합)
│       ├── terraform_service.py     # Terraform 실행 서비스
│       ├── ansible/                 # Ansible 실행 서비스
│       │   └── __init__.py          # AnsibleService
│       ├── proxmox/                 # Proxmox 조회/모니터링 서비스
│       │   └── __init__.py          # ProxmoxService
│       ├── task/                    # 작업 상태/로그 관리
│       │   └── manager.py           # TaskManager, TaskStatus
│       └── llm/                     # LLM 및 인프라 액션 도메인
│           ├── llm_core.py          # Gemini LLM 연동 핵심 로직
│           ├── service.py           # LLMService 래퍼
│           └── infra_action_service.py  # LLM 액션 → 실제 인프라 서비스 매핑
├── iac/                             # Infrastructure as Code
│   ├── terraform/                   # Terraform 설정 파일 (main.tf 등)
│   └── ansible/                     # Ansible playbook 및 inventory
└── requirements.txt                 # Python 의존성
```

## 동작 흐름 (간단 요약)

1. **프론트엔드 요청** → FastAPI 도메인 라우터(`domains/*/router.py`)가 HTTP 요청 수신
2. **라우터** → 도메인별 서비스(`services/deployment`, `services/proxmox`, `services/llm` 등) 호출
3. **서비스** → Terraform/Ansible/Proxmox API/LLM 을 호출하여 실제 인프라 작업 수행
4. **작업 관리** → `TaskManager` 에 상태와 로그를 실시간 저장
5. **응답(배포/LLM)** → 프론트엔드에 `task_id` 또는 액션/결과 정보 반환
6. **프론트엔드** → `task_id` 기반으로 `/api/status`, `/api/logs` 를 폴링하여 상태/로그 조회

## 다음 문서

- [02_ARCHITECTURE.md](./02_ARCHITECTURE.md) - 백엔드 아키텍처 상세 설명
- [03_API_ENDPOINTS.md](./03_API_ENDPOINTS.md) - 모든 API 엔드포인트 목록
- [04_SERVICES.md](./04_SERVICES.md) - 서비스 레이어/도메인 상세
- [05_DEPLOYMENT_FLOW.md](./05_DEPLOYMENT_FLOW.md) - 백엔드 관점 배포 플로우 상세
- [06_RUNNING.md](./06_RUNNING.md) - 실행 방법 및 환경 변수
- 상위 폴더: `../flows/01_DEPLOYMENT_WEB_TO_VM.md` - **프론트엔드까지 포함한 end-to-end 배포 플로우**
- 상위 폴더: `../flows/02_LLM_INFRA_ASSISTANT_FLOW.md` - **LLM 인프라 어시스턴트 플로우**
- 상위 폴더: `../flows/03_MONITORING_FLOW.md` - **모니터링 플로우**
