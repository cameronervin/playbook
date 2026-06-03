# Phase 4: Admin Analytics and Insights

## Scope boundary for this phase

Phase 4 builds the admin analytics dashboard and insight agents for recent athlete queries. It does not create document-edit automation or exported reports.

| Status | Goal | User Stories | Validation | PRD Docs |
|--------|------|-------------|------------|----------|
| ☐ | **Build analytics data pipeline** — label and aggregate query volume, topics, unanswered questions, and risk categories | US-18, US-23 | Stored messages have topic/risk labels -> GET summary returns volume/topics/unanswered/risk counts -> seeded query set produces expected aggregates | prd/02-technical-docs/data-model.md, prd/02-technical-docs/agentic-framework.md |
| ☐ | **Build anonymized query review** — show query text without athlete names | US-19, US-23 | GET query list returns text and anonymous user key -> response omits athlete name/email -> filters by date/risk/topic work | prd/02-technical-docs/security.md |
| ☐ | **Implement nightly insight generation** — scheduled job creates insight summaries | US-20 | Nightly job starts insight run -> completed run stores summary/topic/risk output -> failed run stores error and appears in admin UI | prd/02-technical-docs/agentic-framework.md, prd/02-technical-docs/integration-spec.md |
| ☐ | **Implement manual insight generation** — admin can run insights for a selected time window | US-21 | POST insight run with time window returns run_id -> status endpoint transitions pending/processing/completed -> output persists for later view | prd/02-technical-docs/api-specification.md |
| ☐ | **Implement TTYD side panel** — admin asks natural-language questions about analytics data | US-22 | Side panel opens from dashboard -> POST ask returns analytics-grounded answer -> unsupported question declines -> closing panel preserves dashboard state | prd/01-user-stories/epic-4-admin-analytics-and-insights.md |

## Definition of Done

- [ ] Admin dashboard shows query volume, topics, unanswered questions, and NIL/compliance/recruiting risk.
- [ ] Athlete identity is anonymized in analytics views.
- [ ] Nightly and manual insight runs work.
- [ ] Talk-to-your-data side panel answers analytics questions from authorized data.
- [ ] No export/report feature is included in MVP.
