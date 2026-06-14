# AGENTS.md

## Heimdall operating mode
- The main session is the coordinator and may edit code directly.
- Use subagents only for large, risky, or unclear tasks.
- Prefer concise summaries over raw logs and long command dumps.
- Keep the main thread focused on requirements, decisions, validation, and final output.

## When to delegate
Delegate when the task involves:
- broad architecture changes
- database schema or migrations
- security-sensitive behavior
- deployment/runtime behavior
- unfamiliar framework/API assumptions
- large review surface

## Delegation pattern
- explorer: use when scope is unclear.
- reviewer: use before or after risky changes.
- docs_researcher: use only when external docs or framework behavior may have changed.
- worker: use for large implementation slices when parallel review is useful.

## When to skip multi-agent
- single-file edits
- targeted bug fixes
- already-known file targets
- tests/docs-only changes
- mechanical refactors

## Definition of done
- Scope is clear
- Change is minimal and targeted
- Relevant validation ran
- Remaining risk is explicitly stated

## Avoid
- mandatory delegation for every non-trivial task
- serial waiting when the coordinator can safely proceed
- broad scans when targeted reads are enough
- speculative refactors
- style-only review comments
- silent changes to behavior or contracts
