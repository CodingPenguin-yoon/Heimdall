# Heimdall Documentation Index

> 현재 문서 세트는 새 방향성으로 전환 중이다.

Heimdall의 새 기준은 다음이다.

```text
Heimdall = Hermes-controlled Agentic DevOps Execution Plane
```

즉 Heimdall은 자체 AI agent 두뇌가 아니라, Hermes가 호출하는 worker/task/repo/test/build/PR/staging verification 실행 계층이다.

---

## Source of truth

제품 방향과 현재 상태는 repo 문서보다 shared storage를 우선한다.

```text
/mnt/hermes_data/프로젝트/헤임달
/mnt/hermes_data/프로젝트/AI_Homelab_Control_Plane_방향성.md
```

먼저 읽을 문서:

1. `/mnt/hermes_data/프로젝트/헤임달/README.md`
2. `/mnt/hermes_data/프로젝트/헤임달/CURRENT_STATE.md`
3. `/mnt/hermes_data/프로젝트/헤임달/TASKS.md`
4. `/mnt/hermes_data/프로젝트/헤임달/DECISIONS.md`
5. `/mnt/hermes_data/프로젝트/헤임달/01_아키텍처/Hermes_중심_Heimdall_방향성.md`

---

## Active repo docs

현재 repo-local docs에는 과거 staging-first 구현 문서가 남아 있다.
아래 문서는 “현재 구현을 이해하기 위한 역사/전환 자료”로 읽고, 새 기능 설계의 기준으로는 shared storage를 우선한다.

- [architecture/AGENT_WORKER_REGISTRY.md](architecture/AGENT_WORKER_REGISTRY.md)
- [architecture/WORKER_WORKSPACE_CONTRACT.md](architecture/WORKER_WORKSPACE_CONTRACT.md)
- [updates/2026-05-02_COMPLETED_WORK_SUMMARY.md](updates/2026-05-02_COMPLETED_WORK_SUMMARY.md)
- [architecture/STAGING_ARCHITECTURE.md](architecture/STAGING_ARCHITECTURE.md)
- [architecture/STAGING_CONTRACT.md](architecture/STAGING_CONTRACT.md)
- [operations/STAGING_RUNBOOK.md](operations/STAGING_RUNBOOK.md)
- [roadmap/NEXT_WORK.md](roadmap/NEXT_WORK.md)
- [updates/2026-04-27_ENVIRONMENT_CONTRACT_SLICE.md](updates/2026-04-27_ENVIRONMENT_CONTRACT_SLICE.md)

Service docs:

- [../backend/README.md](../backend/README.md)
- [../frontend/README.md](../frontend/README.md)

---

## New scope rule

### Keep / evolve inside Heimdall

- worker registry
- agent task lifecycle
- repo / branch / worktree preparation
- Codex / Claude / OpenCode execution wrapper
- test / build / lint execution
- diff / PR / staging verification report
- task log / artifact storage

### Move out to Gjallar

- Proxmox VM provisioning ownership
- Terraform state ownership for VMs
- VM lifecycle actions
- Proxmox inventory / monitoring / risk dashboard
- backup / snapshot / guest-agent / storage / owner policy checks

---

## Relationship with Gjallar

```text
Gjallar provides infrastructure.
Heimdall executes DevOps and agent work on that infrastructure.
Hermes coordinates both.
```

When Heimdall needs worker capacity, the target flow is:

```text
Hermes → Gjallar provision plan → user approval → Gjallar VM bootstrap → Heimdall worker registration → agent task execution
```

---

## Documentation cleanup TODO

- Rewrite legacy staging docs around the new execution-plane model.
- [x] Define worker registry schema and 1차 `/api/workers` contract.
- [x] Define agent task lifecycle state-transition policy.
- [x] Add worker heartbeat/health probe self-report contract and worker_id hardening.
- [x] Define worker workspace / repo execution contract and dirty-tree guard policy.
- [ ] Define log/artifact report schema/retention beyond the Set 2 path convention.
- [x] Define the Gjallar provision API contract from Heimdall's point of view.
- Keep Codex OAuth/device-auth as a worker-local official auth state; never document raw tokens.

If code and docs disagree, do not blindly trust old repo docs. Check shared storage first.
