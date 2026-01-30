# 백엔드 문서

이 디렉토리에는 백엔드의 동작 원리와 사용 방법에 대한 상세한 문서가 포함되어 있습니다.

## 문서 목록

### 📖 [01_OVERVIEW.md](./01_OVERVIEW.md)
백엔드의 전체 개요와 주요 역할을 설명합니다.
- 백엔드란 무엇인가?
- 주요 역할
- 기술 스택
- 전체 구조
- 동작 흐름 요약

### 🏗️ [02_ARCHITECTURE.md](./02_ARCHITECTURE.md)
백엔드의 아키텍처 구조를 상세히 설명합니다.
- 계층형 아키텍처 개요
- 라우터 레이어
- 서비스 레이어
- 외부 시스템
- 데이터 흐름
- 아키텍처 원칙

### 🔌 [03_API_ENDPOINTS.md](./03_API_ENDPOINTS.md)
모든 API 엔드포인트를 상세히 설명합니다.
- 배포 API (`POST /api/deploy`)
- 상태 조회 API (`GET /api/status/{task_id}`)
- 로그 조회 API (`GET /api/logs/{task_id}`)
- Proxmox 조회 API (서버, 템플릿, VM, 스토리지, 네트워크 등)
- 모니터링 API
- 헬스체크 엔드포인트

### ⚙️ [04_SERVICES.md](./04_SERVICES.md)
서비스 레이어의 각 서비스를 상세히 설명합니다.
- DeploymentService (배포 통합 관리)
- TerraformService (Terraform 실행)
- AnsibleService (Ansible 실행)
- ProxmoxService (Proxmox API 연동)
- TaskManager (작업 상태 관리)

### 🔄 [05_DEPLOYMENT_FLOW.md](./05_DEPLOYMENT_FLOW.md)
배포 프로세스의 전체 플로우를 단계별로 설명합니다.
- 배포 요청 수신
- 배포 작업 시작
- Terraform 단계 (Init, Plan, Apply)
- IP 주소 추출
- Ansible 단계 (Inventory 생성, Playbook 실행)
- 상태 조회 플로우
- 에러 처리

### 🚀 [06_RUNNING.md](./06_RUNNING.md)
백엔드를 실행하는 방법을 설명합니다.
- 사전 요구사항
- 실행 방법 (run.sh 스크립트, 수동 실행)
- 서버 확인
- 문제 해결
- 개발 모드
- 프로덕션 배포

## 빠른 시작

1. **개요 파악**: [01_OVERVIEW.md](./01_OVERVIEW.md)부터 읽어보세요
2. **아키텍처 이해**: [02_ARCHITECTURE.md](./02_ARCHITECTURE.md)로 구조를 파악하세요
3. **API 확인**: [03_API_ENDPOINTS.md](./03_API_ENDPOINTS.md)에서 사용 가능한 API를 확인하세요
4. **서비스 이해**: [04_SERVICES.md](./04_SERVICES.md)로 각 서비스의 역할을 이해하세요
5. **플로우 파악**: [05_DEPLOYMENT_FLOW.md](./05_DEPLOYMENT_FLOW.md)로 배포 과정을 이해하세요
6. **실행하기**: [06_RUNNING.md](./06_RUNNING.md)로 실제로 실행해보세요

## 주요 개념

### 조회 vs 제어 분리
- **조회(Read)**: Proxmox API 직접 호출 (빠르고 실시간)
- **제어(Create/Update/Delete)**: Terraform 사용 (IaC의 이점, 안전성, 추적 가능성)

### 비동기 처리
- 배포 작업은 `BackgroundTasks`를 사용하여 비동기로 실행
- 즉시 `task_id`를 반환하고, 프론트엔드는 폴링으로 상태 조회

### 상태 관리
- 작업 상태는 `TaskManager`에서 메모리 기반으로 관리
- Thread-safe 구조로 동시 요청 안전하게 처리

## 기술 스택

- **FastAPI**: Python 기반의 현대적인 웹 프레임워크
- **Uvicorn**: ASGI 서버
- **Pydantic**: 데이터 검증 및 직렬화
- **Python-dotenv**: 환경 변수 관리
- **Requests**: HTTP 클라이언트
- **PyYAML**: YAML 파일 처리

## 관련 문서

- [프론트엔드 문서](../frontend/README.md)
- [환경 변수 설명](../ENV_SETTINGS_EXPLAINED.md)
- [Ansible 자동화](../ANSIBLE_AUTOMATION.md)
- [VM 생성 방법](../VM_CREATION_METHODS.md)
