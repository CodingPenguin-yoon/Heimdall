# Frontend

현재 프론트는 React + Vite 기반 운영 UI다.
Heimdall 에서는 기존 VM 운영 화면 위에 선택형 GitLab Workspace 화면이 추가된 상태다.

## 현재 화면

- Create Instance
- Instance List
- Task Board
- Monitoring
- GitLab Workspace
- LLM Assistant

## 현재 기능

- 템플릿 클론 기반 VM 생성
- DHCP / static IP 입력
- 인스턴스 목록 조회
- 인스턴스 lifecycle: `start`, `shutdown`, `stop`, `reboot`
- 인스턴스 CPU / memory resize
- Task Board + SSE 기반 실시간 상태 확인
- 노드/VM monitoring
- GitLab inventory 조회 / 수동 sync
- GitLab 프로젝트 생성
- GitLab 프로젝트별 설정 저장
- LLM Assistant

현재 GitLab Workspace 는 실제 UI로 동작하지만 선택 사항이다.
프로젝트 inventory 와 준비 상태를 다루며, bootstrap / `Deploy Staging` 실행은 아직 미래 작업이다.
기존 Create Instance, Task Board, Monitoring 같은 low-level VM engine 화면도 그대로 유지된다.

## 실행

루트에서:

```bash
pnpm frontend
```

프론트 디렉터리에서 직접:

```bash
pnpm dev
pnpm build
```

백엔드 기본 주소는 `/api` 프록시를 통해 연결된다.
