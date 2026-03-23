# Frontend

현재 프론트는 React + Vite 기반 운영 UI다.

## 현재 화면

- Create Instance
- Instance List
- Task Board
- Monitoring
- LLM Assistant

## 현재 기능

- 템플릿 클론 기반 VM 생성
- DHCP / static IP 입력
- 인스턴스 목록 조회
- 인스턴스 lifecycle: `start`, `shutdown`, `stop`, `reboot`
- 인스턴스 CPU / memory resize
- Task Board + SSE 기반 실시간 상태 확인
- 노드/VM monitoring
- LLM Assistant

현재 UI는 템플릿 클론 기반 생성과 현재 운영 기능만 다룬다.

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
