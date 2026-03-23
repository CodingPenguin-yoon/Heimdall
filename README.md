# GitLab 중심 개발자 셀프서비스 환경 플랫폼

이 저장소의 목표는 GitLab 프로젝트를 기준으로 `VM + DB + secret + pipeline` 을 함께 오케스트레이션하는 control plane 이다.

현재는 그 최종 형태 전 단계다. 이미 동작하는 기반은 Proxmox 템플릿 클론 VM 배포, Terraform/Ansible 연동, Task Board + SSE, 운영 UI, LLM Assistant, 기존 인스턴스 lifecycle/resize, 플랫폼 내부 상태 DB 1차 도입이다.

## 현재 구현된 기반

### 1. VM 배포 엔진

- Proxmox 템플릿 클론 기반 VM 생성
- Terraform 기반 인프라 프로비저닝
- Ansible 기반 후처리
- DHCP 또는 static IP 입력 지원

현재 VM 생성 경로는 `template_id` 기반만 지원한다. ISO 직접 설치 경로는 없다.

### 2. 인스턴스 운영 기능

- 인스턴스 목록 조회
- `start`, `shutdown`, `stop`, `reboot`
- stopped 상태에서 CPU / memory resize
- terminate

즉 지금 저장소는 “VM 하나만 만드는 UI”가 아니라, 운영 액션이 가능한 인프라 관리 기반까지는 갖춘 상태다.

### 3. 작업 추적과 상태 저장

- Task Board
- SSE 기반 실시간 상태 스트림
- 로그 누적 및 아카이브
- 플랫폼 내부 상태 DB 1차 도입

현재 task persistence 는 `data/platform_state.db` 에 저장된다. legacy `data/task_history.json` 은 초기 import source 로만 남아 있다. 내부 저장소는 SQLAlchemy + Alembic 기반이다.

### 4. 운영 화면

- Create Instance
- Instance List
- Task Board
- Monitoring
- LLM Assistant

## 아직 구현되지 않은 것

아래는 아직 roadmap 이다. 현재 구현 완료 기능이 아니다.

- GitLab 프로젝트 인벤토리 / sync / system hook
- 프로젝트 설정 화면
- Bootstrap 자동화
- `Deploy Staging`
- 환경별 DB 자동 생성 및 연결 정보 주입
- GitLab 변수 upsert / pipeline trigger
- `Redeploy`, `Destroy`, `Rotate DB Credentials`

즉 지금 단계는 “플랫폼 완성본”이 아니라, 그 위에 GitLab/환경/DB 계층을 얹기 위한 기반 엔진이다.

## 바로 다음 작업

현재 우선순위는 GitLab 연동 시작이다.

1. GitLab instance 연결 설정 모델
2. `gitlab_projects` / audit log 같은 control-plane 모델 추가
3. `Projects API` 기반 inventory sync
4. `System Hook` 수신
5. 프로젝트 설정 화면
6. 그 다음에 Bootstrap / `Deploy Staging`

GitLab 연동에 필요한 준비용 env 변수(`GITLAB_BASE_URL`, `GITLAB_API_TOKEN` 등)는 `docs/ENV_SETTINGS_EXPLAINED.md` 에 정리해 두었다.

핵심은 `GitLab 프로젝트 생성 = 즉시 배포`가 아니라:

1. GitLab 프로젝트 생성
2. 플랫폼이 프로젝트를 감지
3. 사용자가 프로젝트/환경 설정
4. 준비된 뒤에만 `Deploy Staging`

즉 큰 틀은 자동 오케스트레이션이지만, 배포 전에는 프로젝트와 환경 설정 단계가 먼저 필요하다.

## 문서 안내

운영 기준 문서는 아래를 먼저 보면 된다.

- `docs/README.md`
- `docs/LOCAL_RUN_GUIDE.md`
- `docs/ENV_SETTINGS_EXPLAINED.md`
- `docs/TEMPLATE_PREPARATION.md`
- `docs/ANSIBLE_AUTOMATION.md`
- `docs/VM_CREATION_METHODS.md`

장기 설계와 로드맵은 아래 문서를 본다.

- `docs/platform/00_PLATFORM_DESIGN_SUMMARY.md`
- `docs/platform/01_GITLAB_ENV_PLATFORM_ARCHITECTURE.md`
- `docs/platform/02_IMPLEMENTATION_ROADMAP.md`
- `docs/platform/03_PROJECT_MANIFEST_SPEC.md`
