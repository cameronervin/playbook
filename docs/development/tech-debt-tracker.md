# Tech Debt Tracker

> Track known shortcuts, deferred work, and code smells so they stay visible and
> get paid down deliberately. Add a row when debt is taken on or identified.

## Priority Scale

| Priority | Meaning |
|----------|---------|
| P0 | Actively causing pain / risk — address now |
| P1 | Should be addressed within the current release |
| P2 | Address opportunistically |
| P3 | Nice to have |

## Status Values

`Identified` · `Planned` · `In Progress` · `Resolved` · `Accepted (won't fix)`

## Items

| ID | Date | Priority | Area | Description | Proposed Fix | Status |
|----|------|----------|------|-------------|--------------|--------|
| TD-001 | YYYY-MM-DD | — | _backend/frontend/agents/infra_ | _What the debt is and why it exists_ | _How to pay it down_ | Identified |
| TD-002 | 2026-06-16 | P1 | backend/kb-service | Conversation file summaries returned `chunk_count=0` after backend-local chunks were removed; KB-service owns real chunk counts and private retrieval metadata. | Phase 5 mirrors chunk count/status/summary onto `conversation_files`; Phase 6 source-scoped search filters private chunks by conversation scope. | Resolved |
| TD-003 | 2026-06-17 | P2 | backend/storage | Phase 9F intentionally handles only short-term cleanup for expired pending direct-upload intents; successful original files and extracted artifacts still need a product retention policy. | Define retention windows, legal/audit requirements, and cleanup ownership for successful admin originals, conversation originals, and extracted artifacts before adding deletion automation. | Identified |
| TD-004 | 2026-06-17 | P1 | backend/evals | The eval runner now uses Langfuse experiments with bounded concurrency, but real Playbook golden datasets/specs are still not built and the scaffold's KB capture remains a locked legacy patch. | Add Playbook NIL/compliance/refusal/admin golden specs and replace legacy KB capture with per-item injected providers/source registries. | Identified |
