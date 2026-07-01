# Playbook Implementation Plan

## Scope-Level Plan

Playbook MVP is a fresh product build on top of an agentic-app scaffold. Keep the
phase order below because it still matches the MVP build path: foundations first,
then the athlete AI loop, KB administration, admin analytics, and release gates.

The phase files are organized for developers by build area rather than broad
product goals. Each row should be concrete enough to drive implementation across
models, schemas, repositories, services, API routes, frontend surfaces,
infrastructure, tests, and docs.

## Current Implementation Snapshot

As of 2026-07-01:

| Area | Status | Notes |
|------|--------|-------|
| Backend Phase 1 foundations | ☑ | Product schema/models/migrations, OAuth/session/profile services, role guards, admin user routes, audit service, conversation history CRUD, KB document control-plane routes, signed KB webhook, request context/CORS/error handling, and provider wiring are implemented and verified. |
| Backend verification | ☑ | Backend tests passed with `76 passed`; `backend/.venv/bin/ruff check app tests` passed; live Alembic upgrade/downgrade/re-upgrade passed on `playbook_test`. |
| Frontend | ☑ | Scaffold UI has been replaced by Playbook `/`, `/login`, `/profile`, `/chat`, and `/admin` route shells with neutral department copy. Frontend Vitest passed with `68 passed`; typecheck and ESLint passed. |
| KB service | ◐ | Ingestion/retrieval implementation exists, including configuration, ingest, status, search, document routes, parser/chunker/embed/vectorstore infrastructure, and workers. It was not locally verified in this shell because no runnable local venv/`uv` path was available. |
| Admin analytics backend | ◐ | Admin analytics summary/query APIs, anonymized snapshot service, dashboard insight run/output APIs, LangGraph dashboard insight agent, admin chat side-panel backend/API/agent/worker stream path, read-only analytics tools, Celery generation tasks, nightly beat scheduling, real admin Insights dashboard wiring, and Phase 4 privacy/audit/runtime Langfuse tracing are implemented and focused tests pass. Remaining work is broader Phase 5 release eval gates and any custom date-range UX. |
| Eval harness | ◐ | Backend eval package, sample dataset/rubrics, and the deterministic `dashboard_insights` golden spec exist; broader MVP golden sets and release gates remain. |

## Phase Overview

| Phase | Focus | Goal |
|-------|-------|------|
| Phase 1 | Playbook Foundations | Replace scaffold placeholders with product foundations: auth, roles, data model, route shell, KB document model, audit/observability baseline |
| Phase 2 | Athlete AI Experience | Build Celery-executed streamed chat over Valkey Streams/pub-sub, citations, conversation history, conversation file upload, safety/refusal behavior |
| Phase 3 | Knowledge Base Admin | Build document upload/status/retry/metadata flows and connect them to the KB service |
| Phase 4 | Admin Analytics and Insights | Build dashboard metrics, polled nightly/manual dashboard insight runs, and streamed admin chat side panel |
| Phase 5 | Evaluation and Release Readiness | Add eval suites, security checks, observability validation, and prototype release gates |

## Developer Phase Matrix

| Status | Phase | Primary Build Areas | Completion Signal | Phase File |
|--------|-------|---------------------|-------------------|------------|
| ☑ | Phase 1 Playbook Foundations | Backend schema, auth/session/profile, RBAC, audit, KB document control plane, conversation history, frontend scaffold cleanup, route tests, env/docs | Playbook routes replace scaffold UI; auth/profile/RBAC/admin APIs work; live migrations pass; role/KB/audit route tests pass; docs match implemented endpoints | [phase-1-foundations.md](phase-1-foundations.md) |
| ☑ | Phase 2 Athlete AI Experience | Message APIs, Celery agent execution, Valkey Streams/pub-sub stream endpoint keyed by `task_id`, LangGraph chat graph, KB retrieval, citation persistence, safety policy, conversation file upload, athlete chat UI | Athlete can submit a message, receive streamed grounded response with citations/refusals from a worker task, upload conversation files, and reload conversation history | [phase-2-athlete-ai-experience.md](phase-2-athlete-ai-experience.md) |
| ◐ | Phase 3 Knowledge Base Admin | Admin document UI, metadata upload contract, status/retry UX, KB-service contract reconciliation, ingestion/search e2e verification | Admin can upload, tag, view status, retry, and delete docs; ready docs are searchable; failed docs are excluded; admin actions are audited | [phase-3-knowledge-base-admin.md](phase-3-knowledge-base-admin.md) |
| ◐ | Phase 4 Admin Analytics and Insights | Analytics repositories/services, anonymized APIs, dashboard UI, polled insight jobs, Celery/Valkey-streamed admin chat services/APIs/UI | Admin dashboard returns anonymized metrics/query review; manual/nightly insight runs persist outputs and are polled by `run_id`; admin chat streams answers from authorized analytics data by `task_id`; privacy/audit/observability is closed with audit events, anonymized context, and privacy-safe runtime tracing | [phase-4-admin-analytics-and-insights.md](phase-4-admin-analytics-and-insights.md) |
| ◐ | Phase 5 Evaluation and Release Readiness | Golden datasets, retrieval/citation/refusal/security evals, observability checks, affiliation-copy scan, release command | Release validation command runs golden evals and security/observability/copy checks with documented pass criteria | [phase-5-evaluation-and-release-readiness.md](phase-5-evaluation-and-release-readiness.md) |

## Implemented Backend API Surface

The following routes are implemented under `/api/v1` and should remain aligned
with [backstage/api/endpoints.md](../../api/endpoints.md):

| Area | Implemented Routes |
|------|--------------------|
| Auth/users | `GET /auth/providers`, `GET /auth/{provider}/login`, `GET /auth/{provider}/callback`, `POST /auth/logout`, `GET /users/me`, `PATCH /users/me/profile` |
| Admin users/audit | `GET /admin/users`, `PATCH /admin/users/{user_id}/role`, `GET /admin/audit-logs` |
| Conversations | `GET /conversations`, `POST /conversations`, `GET /conversations/{conversation_id}`, `POST /conversations/{conversation_id}/messages`, `GET /conversations/{conversation_id}/messages/{message_id}/stream`, conversation-file direct-upload routes |
| KB documents | `GET /admin/kb/documents`, `POST /admin/kb/documents`, `GET /admin/kb/documents/{document_id}`, `PATCH /admin/kb/documents/{document_id}/metadata`, `POST /admin/kb/documents/{document_id}/retry`, `DELETE /admin/kb/documents/{document_id}`, `POST /kb/webhook` |
| Admin analytics/insights | `GET /admin/analytics/summary`, `GET /admin/analytics/queries`, `GET /admin/dashboard-insights/current`, `GET /admin/dashboard-insights/outputs`, `GET /admin/dashboard-insights/outputs/{insight_id}`, `GET /admin/dashboard-insights/runs`, `POST /admin/dashboard-insights/runs`, `GET /admin/dashboard-insights/runs/{run_id}`, `GET /admin/chat/sessions`, `POST /admin/chat/sessions`, `GET /admin/chat/sessions/{session_id}`, `POST /admin/chat/sessions/{session_id}/messages`, `GET /admin/chat/sessions/{session_id}/messages/{message_id}/stream` |
| Health | `GET /health` |

Remaining planned API surface: none for Phase 4 MVP; Phase 5 may add release
validation/reporting utilities if needed.

## How Phase Files Work

Each phase file uses a developer-focused task table with:

- **Status** (`☐`, `◐`, `☑`)
- **Build Area** — engineering layer or surface area
- **What To Build** — concrete implementation work
- **Current Implementation** — what exists now, if anything
- **Validation** — assertion chain proving completion
- **Source Specs** — PRD/spec files that define behavior

Use `☑` only when a row is implemented, tested, and documentation-aligned.
Backend-only or unverified work should stay `◐`.

## Deviation Log Format

When implementation differs from a planned task:

- **Planned** — what the task said.
- **Actual** — what was built.
- **Reason** — why.
- **Impact** — effect on later phases.
