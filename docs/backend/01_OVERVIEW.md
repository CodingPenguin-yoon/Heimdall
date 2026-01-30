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

## 전체 구조

```
backend/
├── app/
│   ├── main.py              # FastAPI 앱 진입점
│   ├── routes/              # API 엔드포인트 정의
│   │   ├── deploy.py        # 배포 API
│   │   ├── status.py        # 상태 조회 API
│   │   ├── logs.py          # 로그 조회 API
│   │   └── proxmox.py        # Proxmox 조회 API
│   └── services/            # 비즈니스 로직
│       ├── deployment_service.py   # 배포 통합 관리
│       ├── terraform_service.py     # Terraform 실행
│       ├── ansible_service.py      # Ansible 실행
│       ├── proxmox_service.py      # Proxmox API 연동
│       └── task_manager.py          # 작업 상태 관리
├── iac/                     # Infrastructure as Code
│   ├── terraform/           # Terraform 설정 파일
│   └── ansible/             # Ansible playbook
└── requirements.txt         # Python 의존성
```

## 동작 흐름 (간단 요약)

1. **프론트엔드 요청** → FastAPI 라우터가 받음
2. **라우터** → 해당 서비스 호출
3. **서비스** → Terraform/Ansible/Proxmox API 실행
4. **결과** → TaskManager에 상태와 로그 저장
5. **응답** → 프론트엔드에 task_id 반환
6. **프론트엔드** → task_id로 상태와 로그 조회

## 다음 문서

- [02_ARCHITECTURE.md](./02_ARCHITECTURE.md) - 아키텍처 상세 설명
- [03_API_ENDPOINTS.md](./03_API_ENDPOINTS.md) - API 엔드포인트 목록
- [04_SERVICES.md](./04_SERVICES.md) - 서비스 레이어 설명
- [05_DEPLOYMENT_FLOW.md](./05_DEPLOYMENT_FLOW.md) - 배포 플로우 상세
- [06_RUNNING.md](./06_RUNNING.md) - 실행 방법
