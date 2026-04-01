# 2026-03-28 작업 요약

오늘 반영한 Heimdall MVP 슬라이스는 GitLab 기반 수동 staging 요청 흐름을 한 단계 더 좁히는 데 초점을 맞췄다.

- manual `Deploy Staging` request task 슬라이스를 추가했다
- 같은 프로젝트에 대해 진행 중인 live request 중복 생성을 막았다
- `.heimdall/project.yaml` 최소 검증을 추가했다
- 현재는 실제 VM/DB/Terraform/Ansible 실행 없이 요청 task 기록과 상태 노출까지만 제공한다

현재 제한 사항:

- staging deploy 버튼은 요청 task만 남기며 실제 인프라 실행을 시작하지 않는다
- manifest 검증은 최소 필드만 본다
- compose 파일 존재 여부나 bootstrap MR 생성 가능 여부는 아직 검사하지 않는다

다음 단계:

1. bootstrap 경로에서 `.heimdall/project.yaml` 초안 생성과 MR 제안을 연결한다
2. manifest 검증에 compose 경로와 배포 입력 계약 검사를 추가한다
3. staging deploy request task를 실제 VM/DB 실행 오케스트레이션으로 연결한다
4. Postgres 자동 연결 정보 주입과 실행 이력 저장을 붙인다
