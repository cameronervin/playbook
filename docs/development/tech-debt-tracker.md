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
| TD-002 | 2026-06-16 | P1 | backend/kb-service | Conversation file summaries return `chunk_count=0` after backend-local chunks were removed; KB-service owns real chunk counts but Phase 5/6 sync is not implemented yet. | Include chunk count in signed KB-service status/search metadata and mirror it onto `conversation_files` for conversation detail responses. | Planned |
