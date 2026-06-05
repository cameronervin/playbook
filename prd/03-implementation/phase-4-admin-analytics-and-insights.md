# Phase 4: Admin Analytics and Insights

## Scope Boundary For This Phase

Phase 4 builds the admin analytics dashboard and insight agents for recent
athlete queries. It does not create document-edit automation, report exports,
or integrations that act in external athletic systems.

| Status | Build Area | What To Build | Current Implementation | Validation | Source Specs |
|--------|------------|---------------|------------------------|------------|--------------|
| ◐ | Analytics and admin chat data model | Use existing conversation/message metadata plus dashboard insight and admin chat tables as the durable foundation. | ORM models and migrations exist for `dashboard_insight_runs`, `dashboard_insights`, `admin_chat_sessions`, and `admin_chat_messages`. Analytics query repositories/services are not implemented. | Migration includes analytics/admin chat tables -> repositories can create/list/update runs, outputs, sessions, and messages -> seeded data can be queried by organization/window. | `prd/02-technical-docs/01-playbook/data-model.md` |
| ☐ | Analytics repositories/services | Aggregate query volume, topics, unanswered/declined questions, and NIL/compliance/recruiting risk from conversation messages. | Conversation messages can store `topic_labels`, `risk_labels`, and `safety_outcome`; no analytics service exists. | Seeded messages produce expected volume/topic/risk/unanswered counts -> filters by date/topic/risk work -> services never expose athlete owner identity by default. | `prd/02-technical-docs/01-playbook/agentic-framework.md`, `prd/02-technical-docs/01-playbook/security.md` |
| ☐ | Analytics APIs | Implement admin-only summary and anonymized query review endpoints. | No `/api/v1/admin/analytics/*` routes exist. | `GET /admin/analytics/summary` returns volume/topics/unanswered/risk counts -> `GET /admin/analytics/queries` returns query text with anonymous user key -> athlete name/email omitted. | `prd/02-technical-docs/01-playbook/api-specification.md`, `prd/01-user-stories/epic-4-admin-analytics-and-insights.md` |
| ☐ | Admin dashboard frontend | Build dashboard views for summary cards, topic/risk breakdowns, unanswered query review, filters, and insight status. | Frontend has no admin routes or dashboard UI. | Admin dashboard loads summary -> query list anonymizes owners -> filters update data -> empty/loading/error states render cleanly -> athlete cannot access admin pages. | `prd/01-user-stories/epic-4-admin-analytics-and-insights.md`, `.claude/rules/13-frontend-design-standards.md` |
| ☐ | Dashboard insight generation | Implement manual and scheduled insight runs that summarize recent chat/analytics data into durable dashboard outputs. | Models exist for runs and outputs; no service, worker, scheduler, or APIs exist. | Nightly job creates run -> manual POST returns `run_id` -> run status transitions pending/processing/completed/failed -> completed output persists cards, summary, topic/risk output, and attention areas. | `prd/02-technical-docs/01-playbook/agentic-framework.md`, `prd/02-technical-docs/01-playbook/integration-spec.md` |
| ☐ | Admin chat side panel | Add admin chat sessions/messages over authorized analytics and dashboard insight data. | Admin chat ORM models exist; no repositories, services, APIs, agent, or frontend panel exists. | Admin creates/loads own session -> sends analytics question -> answer references authorized analytics/insight records -> unsupported questions decline -> session history persists. | `prd/02-technical-docs/01-playbook/api-specification.md`, `prd/02-technical-docs/01-playbook/agentic-framework.md` |
| ☐ | Privacy, audit, and observability | Enforce anonymization, admin authorization, audit manual insight triggers, and trace analytics/insight/admin-chat events without unnecessary PII. | Role dependencies and audit service exist from Phase 1; analytics-specific privacy/audit/log checks do not. | Athlete identity omitted from analytics -> manual insight run writes audit event -> admin chat logs include request/run/session IDs without athlete owner identity -> route guards return 403 for athletes. | `prd/02-technical-docs/01-playbook/security.md`, `prd/02-technical-docs/01-playbook/agentic-framework.md` |
| ☐ | Tests and docs | Add backend service/API tests, frontend dashboard tests, insight job tests, admin chat tests, and docs updates. | No Phase 4 tests exist beyond model/migration coverage. | Analytics service tests pass -> route tests cover auth/anonymization -> frontend tests pass -> insight/admin-chat eval smoke cases exist -> API docs list implemented routes. | `prd/02-technical-docs/01-playbook/eval-framework.md`, `docs/api/endpoints.md` |

## Definition of Done

- [ ] Admin dashboard shows query volume, topics, unanswered questions, and NIL/compliance/recruiting risk.
- [ ] Athlete identity is anonymized in analytics views.
- [ ] Nightly and manual dashboard insight runs work.
- [ ] Admin chat side panel answers analytics questions from authorized data and persists admin session history.
- [ ] Manual insight triggers and privileged analytics actions are audited.
- [ ] No export/report feature is included in MVP.
