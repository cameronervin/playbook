# Phase 4: Admin Analytics and Insights

## Scope boundary for this phase

Phase 4 builds the admin analytics dashboard and insight agents for recent athlete queries. It does not create document-edit automation or exported reports.

| Status | Goal | User Stories | Validation | PRD Docs |
|--------|------|-------------|------------|----------|
| ☐ | **Build analytics data pipeline** — label and aggregate query volume, topics, unanswered questions, and risk categories | US-18, US-23 | Stored messages have topic/risk labels -> GET summary returns volume/topics/unanswered/risk counts -> seeded query set produces expected aggregates | prd/02-technical-docs/01-playbook/data-model.md, prd/02-technical-docs/01-playbook/agentic-framework.md |
| ☐ | **Build anonymized query review** — show query text without athlete names | US-19, US-23 | GET query list returns text and anonymous user key -> response omits athlete name/email -> filters by date/risk/topic work | prd/02-technical-docs/01-playbook/security.md |
| ☐ | **Implement nightly dashboard insight generation** — scheduled agent run creates dashboard insight output | US-20 | Nightly job starts dashboard insight run -> completed run stores curated dashboard cards/summary/topic/risk output -> failed run stores error and appears in admin UI | prd/02-technical-docs/01-playbook/agentic-framework.md, prd/02-technical-docs/01-playbook/integration-spec.md |
| ☐ | **Implement manual dashboard insight generation** — admin can run the dashboard insights agent for a selected time window | US-21 | POST dashboard insight run with time window returns run_id -> status endpoint transitions pending/processing/completed -> output persists for later view | prd/02-technical-docs/01-playbook/api-specification.md |
| ☐ | **Implement admin chat side panel** — admin asks natural-language questions about analytics data | US-22 | Side panel opens from dashboard -> POST admin chat message returns analytics-grounded answer -> question/answer persists to admin chat session -> unsupported question declines -> closing panel preserves dashboard state | prd/01-user-stories/epic-4-admin-analytics-and-insights.md, prd/02-technical-docs/01-playbook/data-model.md, prd/02-technical-docs/01-playbook/api-specification.md, prd/02-technical-docs/01-playbook/agentic-framework.md |

## Definition of Done

- [ ] Admin dashboard shows query volume, topics, unanswered questions, and NIL/compliance/recruiting risk.
- [ ] Athlete identity is anonymized in analytics views.
- [ ] Nightly and manual dashboard insight runs work.
- [ ] Admin chat side panel answers analytics questions from authorized data and persists admin session history.
- [ ] No export/report feature is included in MVP.
