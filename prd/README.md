# Playbook PRD

## MVP Overview

Playbook is an agentic web prototype for college athletic departments. The MVP gives athletes a seamless chat-first experience for NIL, compliance, and internal process questions, grounded in department-specific documents and supported by admin analytics.

The product is athlete-first for MVP and designed to expand later to additional personas and colleges. The first prototype may use athletics-inspired theming, but product copy and code must not imply affiliation with any specific university.

## Scaffold Context

This is the first structured Playbook harness for the repository. The repo started as a reusable FastAPI + LangGraph + Next.js + KB-service scaffold with placeholder `Example` product docs and code.

The previous scaffold PRD was moved to `prd-v1-unstructured/`. The separate `prd_example/` folder was deleted after being used as a format reference.

## Quick Start

The project scaffold is already in place.

1. Open `prd/03-implementation/phase-1-foundations.md`
2. Start building Playbook foundations before feature phases

## What's In Here

- `prd/01-user-stories/_master-user-stories.md` — consolidated Playbook MVP user stories
- `prd/01-user-stories/epic-1-authentication-roles-and-seamless-entry.md`
- `prd/01-user-stories/epic-2-athlete-ai-chat-experience.md`
- `prd/01-user-stories/epic-3-knowledge-base-and-document-operations.md`
- `prd/01-user-stories/epic-4-admin-analytics-and-insights.md`
- `prd/01-user-stories/epic-5-safety-governance-and-release-readiness.md`
- `prd/02-technical-docs/01-playbook/data-model.md`
- `prd/02-technical-docs/01-playbook/api-specification.md`
- `prd/02-technical-docs/01-playbook/agentic-framework.md`
- `prd/02-technical-docs/01-playbook/security.md`
- `prd/02-technical-docs/01-playbook/integration-spec.md`
- `prd/02-technical-docs/01-playbook/eval-framework.md`
- `prd/02-technical-docs/02-kb-service/README.md`
- `prd/02-technical-docs/02-kb-service/architecture.md`
- `prd/02-technical-docs/02-kb-service/data-model.md`
- `prd/02-technical-docs/02-kb-service/api-contracts.md`
- `prd/02-technical-docs/02-kb-service/ingestion-pipeline.md`
- `prd/02-technical-docs/02-kb-service/retrieval.md`
- `prd/02-technical-docs/02-kb-service/operations-security.md`
- `prd/03-implementation/_implementation-plan.md`
- `prd/03-implementation/phase-1-foundations.md`
- `prd/03-implementation/phase-2-athlete-ai-experience.md`
- `prd/03-implementation/phase-3-knowledge-base-admin.md`
- `prd/03-implementation/phase-4-admin-analytics-and-insights.md`
- `prd/03-implementation/phase-5-evaluation-and-release-readiness.md`

## Phase Structure

1. Phase 1: Playbook Foundations
2. Phase 2: Athlete AI Experience
3. Phase 3: Knowledge Base Admin
4. Phase 4: Admin Analytics and Insights
5. Phase 5: Evaluation and Release Readiness

## How Phases Work

Each phase file has a task table with goals, user story references, validation criteria, and linked spec docs. Work through tasks in order, mark status, and log deviations when implementation differs from plan.

At phase boundaries, reconcile specs to match what was actually built before starting the next phase.

## Deviation Log Format

When implementation differs from a task row, log it in `phase-{N}-*.deviations.md` with:

- Planned
- Actual
- Reason
- Impact on later phases

## Status Symbols

- ☐ = Not started
- ◐ = Partial (note what remains in Goal column)
- ☑ = Complete (reviewed, tested, committed)

## MVP Priorities

1. Seamless athlete sign-in and chat-first entry.
2. Accurate, concise, cited answers grounded in department knowledge.
3. Safe refusal behavior for unsupported, emergency, and sensitive topics.
4. Admin document management and query analytics.
5. Dashboard insight generation and admin chat side panel.

## Hardening Targets

- OAuth/OIDC correctness.
- Athlete/admin/super-admin authorization.
- Conversation privacy.
- Admin analytics anonymization.
- KB ingestion reliability.
- Citation integrity.
- Safety/refusal behavior.
- Audit logging.
- Observability without secrets or unnecessary PII.

## Key Decisions

- Google and Microsoft OAuth/OIDC are preferred for MVP.
- No paid third-party auth vendor should be required unless implementation later proves it necessary.
- MVP is a single-tenant prototype, designed for future multi-college expansion.
- Athlete-uploaded files are conversation-scoped and retained in history.
- Admin KB documents are visible to all athletes for MVP.
- KB document chunks and vectors are owned by the KB service; conversation file
  chunks are owned by the main backend and remain conversation-scoped.
- Metadata tags are preferred over a fixed document category taxonomy.
- Admin analytics may show query text but should anonymize athlete identity.
- No explicit university affiliation claims should appear in product copy or code identifiers.

## Hard Deadlines

No hard launch deadline was specified.

## Unresolved Items

- Dev team should confirm the exact OAuth/OIDC implementation path and whether `fastapi-users` OAuth support is sufficient for MVP.
- Dev team should encode deterministic retrieval/ranking rules for freshness, official-source metadata, and priority metadata.
- Product owner is building a separate design guide; visual styling should align once that guide is available.

## V1 Archive

Previous scaffold PRD files are archived at `prd-v1-unstructured/`.
