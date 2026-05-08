# Verification

## 최근 확인된 검증

`c310361` 관련:

- `pnpm --dir frontend test:devops` -> 5 tests OK
- `pnpm --dir frontend build` -> PASS
- backend smoke/contract -> 12 tests OK

`65d6f82` 관련:

- backend DevOps tests + smoke fixtures -> 16 tests OK
- frontend DevOps tests -> 5 tests OK
- frontend build -> PASS
- static scan -> 0 issues
- independent review -> PASS

## 현재 문서에서 전제하는 검증 범위

active 문서는 다음 구현 상태를 기준으로 서술한다.

- `/api/devops/*` typed backend skeleton 존재
- frontend `/devops` read-only dashboard 존재
- `HEIMDALL_DEVOPS_SMOKE_FIXTURES` opt-in fixture 존재
- VM lifecycle route가 `/api/devops`에 없음
- secret-safe validation이 schema/test에 반영됨

## 2026-05-08 repo-local 문서 검증

이번 docs 정리 후 다음을 확인했다.

- `docs/**/*.md` 파일 수: 20개
- root `README.md`까지 포함한 Markdown 검증 대상: 21개
- 상대 Markdown 링크: 깨진 링크 0개
- secret 위험 패턴: 0개
- trailing whitespace: 0개
- `git diff --check -- README.md docs`: PASS
- active 문서에서 `worker-first`, `staging-first`, `backend GET-only` 같은 표현은 현재 지침이 아니라 “아님/주의/역사적 흔적”을 설명하는 문맥으로만 남김

## 문서 검증 시 체크할 것

- active docs가 worker-first나 staging-first를 current guidance로 말하지 않는지
- frontend read-only와 backend POST skeleton을 혼동하지 않는지
- secret 예시가 raw credential을 포함하지 않는지
- Gjallar/Heimdall 경계를 VM ownership 기준으로 분리했는지
