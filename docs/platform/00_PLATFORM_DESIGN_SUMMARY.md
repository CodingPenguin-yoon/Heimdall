# Platform Design Summary

이 문서는 현재 합의된 큰 방향만 짧게 정리한다.

## 현재 위치

이 프로젝트는 이미 아래 기반을 갖고 있다.

- Proxmox 템플릿 클론 기반 VM 배포
- Terraform + Ansible 후처리
- Task Board + SSE
- instance lifecycle / resize
- 플랫폼 내부 상태 DB 1차 도입

플랫폼 내부 상태 DB의 첫 단계는 완료됐다.

- task persistence 는 SQLAlchemy + Alembic 기반
- 기본 저장소는 `data/platform_state.db`
- legacy `data/task_history.json` 은 import source

즉 “플랫폼 내부 DB 도입”은 시작 단계가 아니라 이미 닫힌 첫 슬라이스다.

## 목표 정체성

최종 목표는 GitLab 프로젝트를 기준으로 환경을 자동 온보딩하는 개발자 셀프서비스 환경 플랫폼이다.

- GitLab 프로젝트 감지
- 프로젝트 설정 / bootstrap
- `Deploy Staging`
- VM + DB + secret + pipeline 오케스트레이션

## 다음 초점

다음 우선순위는 GitLab 인벤토리다.

1. GitLab instance 설정
2. `gitlab_projects` / audit log 같은 control-plane 모델
3. `Projects API` sync
4. `System Hook`
5. 프로젝트 설정 화면

그 다음에 Bootstrap 과 `Deploy Staging` 으로 간다.

## 핵심 판단

- VM 생성은 template clone only
- Ansible 은 호스트 운영 표준화 역할 유지
- GitLab 은 control plane
- 플랫폼이 DB 자동화와 배포 오케스트레이션을 담당
- 플랫폼 내부 DB는 이미 SQLAlchemy + Alembic 기준으로 시작했다
