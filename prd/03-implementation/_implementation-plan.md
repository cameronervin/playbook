# Playbook Implementation Plan

## Scope-Level Plan

Playbook MVP is a fresh product build on top of an agentic-app scaffold. Phase 1 establishes the Playbook-specific foundation first, then later phases build the athlete AI experience, admin operations, insight agents, and release gates.

## Phase Overview

| Phase | Focus | Goal |
|-------|-------|------|
| Phase 1 | Playbook Foundations | Replace scaffold placeholders with product foundations: auth, roles, data model, chat shell, KB document model, audit/observability baseline |
| Phase 2 | Athlete AI Experience | Build streamed chat, citations, conversation history, conversation file upload, safety/refusal behavior |
| Phase 3 | Knowledge Base Admin | Build document upload/status/retry/metadata flows and connect them to the KB service |
| Phase 4 | Admin Analytics and Insights | Build dashboard metrics, nightly/manual dashboard insight runs, and admin chat side panel |
| Phase 5 | Evaluation and Release Readiness | Add eval suites, security checks, observability validation, and prototype release gates |

## Phase Task Mapping

| Status | Goal | User Stories | Validation | PRD Docs |
|--------|------|-------------|------------|----------|
| ☐ | **Phase 1 Playbook Foundations** — establish product auth, roles, data model, route shell, audit log, and scaffold cleanup | US-01, US-02, US-03, US-04, US-05, US-12, US-24, US-28 | OAuth config loads -> user/profile/role tables migrate -> athlete route renders chat shell -> admin route rejects athlete -> audit log writes role-change event | prd/03-implementation/phase-1-foundations.md |
| ☐ | **Phase 2 Athlete AI Experience** — implement streamed grounded chat, citations, history, conversation files, and safety refusal behavior | US-06, US-07, US-08, US-09, US-10, US-11, US-17, US-25 | POST message persists user turn -> stream endpoint emits assistant chunks -> final message has citations -> unsupported prompt declines -> history reloads messages/files | prd/01-user-stories/epic-2-athlete-ai-chat-experience.md, prd/02-technical-docs/01-playbook/agentic-framework.md |
| ☐ | **Phase 3 Knowledge Base Admin** — implement admin KB upload/status/retry/metadata and retrieval metadata contract | US-12, US-13, US-14, US-15, US-16, US-17, US-24 | Admin upload creates uploaded doc -> processing reaches ready/failed -> failed doc retry restarts ingestion -> metadata affects retrieval ranking -> audit entries are written | prd/01-user-stories/epic-3-knowledge-base-and-document-operations.md, prd/02-technical-docs/02-kb-service/README.md |
| ☐ | **Phase 4 Admin Analytics and Insights** — implement dashboard metrics, anonymized query review, scheduled/manual dashboard insight generation, and admin chat side panel | US-18, US-19, US-20, US-21, US-22, US-23 | Analytics summary returns volume/topics/risk counts -> query list omits names -> nightly dashboard insight run completes -> manual dashboard insight run completes -> admin chat answer references analytics data | prd/01-user-stories/epic-4-admin-analytics-and-insights.md, prd/02-technical-docs/01-playbook/agentic-framework.md |
| ☐ | **Phase 5 Evaluation and Release Readiness** — implement golden evals, security checks, observability validation, and final prototype gates | US-04, US-11, US-24, US-25, US-26, US-27, US-28 | Eval golden set passes -> athlete cannot access admin APIs -> emergency prompts refuse -> audit log checks pass -> logs omit tokens/secrets -> affiliation-copy check passes | prd/01-user-stories/epic-5-safety-governance-and-release-readiness.md, prd/02-technical-docs/01-playbook/eval-framework.md, prd/02-technical-docs/01-playbook/security.md |

## How Phases Work

Each phase file uses a task table with:

- **Status** (`☐`, `◐`, `☑`)
- **Goal** — what the task delivers
- **User Stories** — mapped story IDs
- **Validation** — assertion chain proving completion
- **PRD Docs** — source specification files

Work tasks in order, update statuses, and log deviations when implementation differs from the planned behavior.

## Deviation Log Format

When implementation differs from a planned task:

- **Planned** — what the task said.
- **Actual** — what was built.
- **Reason** — why.
- **Impact** — effect on later phases.
