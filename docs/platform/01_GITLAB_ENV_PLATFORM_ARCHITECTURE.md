# GitLab Environment Platform Architecture

이 문서는 현재 VM 자동화 기반을 GitLab 중심 환경 플랫폼으로 확장할 때의 목표 구조를 정리한다.

## 목표 흐름

1. 개발자가 GitLab 에서 프로젝트 생성
2. 플랫폼이 프로젝트를 감지해 목록에 표시
3. 사용자가 프로젝트/환경 설정
4. 사용자가 `Deploy Staging` 실행
5. 플랫폼이 VM + DB + secret + pipeline 을 오케스트레이션

즉 `프로젝트 생성 = 즉시 배포`가 아니라, 감지 -> 설정 -> 배포 순서다.

## 현재 코드에서 재사용할 자산

- `backend/app/domains/proxmox/service.py`
- `backend/app/domains/deploy/service.py`
- `backend/app/integrations/terraform/__init__.py`
- `backend/app/integrations/ansible/__init__.py`
- `backend/app/shared/tasks.py`
- `backend/app/shared/platform_models.py`
- `frontend/src/components/TaskBoard.jsx`

새 플랫폼은 이 기반 위에 GitLab/환경/DB 계층을 얹는 방향이 맞다.

## 제안 구조

### Backend

- `domains/gitlab`
  - GitLab instance / projects sync / bootstrap
- `domains/environments`
  - environment 생성 / deploy / 상태 조회
- `domains/webhooks`
  - GitLab system hook / project hook / pipeline event
- `shared/platform_models.py`
  - control-plane DB 모델
- 기존 `domains/deploy`, `domains/proxmox`, `integrations/terraform`, `integrations/ansible`
  - VM 배포 엔진으로 재사용

### Frontend

- Projects
- Project Detail
- Environment Detail
- Blueprint / Policy 화면
- 기존 Create Instance / Task Board / Monitoring / LLM Assistant 는 운영 기반으로 유지

## 역할 분리

- GitLab
  - 코드 저장소
  - CI/CD control plane
  - pipeline / deployment 상태의 공식 소스

- 이 플랫폼
  - GitLab 프로젝트 인벤토리
  - 환경 오케스트레이션
  - VM / DB / secret 조정
  - GitLab 변수 / pipeline 자동화

- Proxmox / Terraform / Ansible
  - VM 프로비저닝과 호스트 초기화

## 데이터 경계

### 플랫폼 내부 DB

현재 첫 단계는 이미 있다.

- task persistence
- platform metadata

다음에 추가될 것:

- gitlab instances
- gitlab projects
- environments
- environment resources
- audit logs

### 서비스 프로젝트용 DB

사용자 프로젝트의 `staging` / `prod` DB 는 플랫폼이 별도로 생성한다.

즉 플랫폼 내부 DB 와 서비스 앱용 DB 는 분리해서 본다.
