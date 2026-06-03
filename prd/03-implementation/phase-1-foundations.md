# Phase 1: Playbook Foundations

## Scope boundary for this phase

Phase 1 establishes the product-specific foundation for Playbook. This is not a hardening phase because there is no existing Playbook product to harden. The goal is to replace scaffold placeholders with the first real product foundation while preserving reusable scaffold assets.

This phase does **not** implement full AI answer quality, admin insight generation, or complete KB operations. Those come in later phases.

| Status | Goal | User Stories | Validation | PRD Docs |
|--------|------|-------------|------------|----------|
| ☐ | **Replace scaffold product identity** — remove user-facing `Example` product placeholders and establish neutral Playbook copy without explicit university affiliation claims | US-05, US-28 | Landing/chat route contains Playbook-neutral copy -> no user-facing specific-school affiliation text exists -> scaffold Example UI is removed or hidden from primary routes | prd/01-user-stories/epic-5-safety-governance-and-release-readiness.md |
| ☐ | **Create Playbook data migrations** — add organizations, users, conversations, messages, citations, files, KB documents, insight runs, insights, and audit logs | US-02, US-03, US-06, US-10, US-12, US-18, US-20, US-24 | Alembic upgrade applies cleanly -> tables exist with required indexes/constraints -> downgrade strategy is documented or intentionally omitted per project convention | prd/02-technical-docs/data-model.md |
| ☐ | **Implement OAuth/OIDC auth foundation** — configure Google and Microsoft sign-in with local user creation and session handling | US-01, US-02 | Google login callback creates local user -> Microsoft login callback creates local user -> failed callback returns structured error -> OAuth tokens are not logged or returned | prd/02-technical-docs/api-specification.md, prd/02-technical-docs/security.md |
| ☐ | **Implement athlete profile completion** — let first-time users select athlete role and provide name, email, and sport/team before direct chat entry | US-02 | New signed-in user submits athlete profile -> profile_complete becomes true -> user redirects to chat -> missing sport/team returns validation error | prd/01-user-stories/epic-1-authentication-roles-and-seamless-entry.md |
| ☐ | **Implement role model and guards** — enforce athlete/admin/super_admin route and API access boundaries | US-03, US-04 | Athlete GET `/admin` redirects or returns forbidden -> athlete GET `/api/v1/admin/users` returns 403 -> super_admin PATCH role succeeds -> role change creates audit log | prd/02-technical-docs/security.md |
| ☐ | **Build chat-first athlete shell** — create authenticated chat route with input, history sidebar placeholder, upload button placeholder, and responsive layout | US-05, US-10 | Authenticated athlete GET chat route renders input/sidebar/upload control -> unauthenticated user redirects to login -> layout remains usable at desktop and responsive web widths | prd/01-user-stories/epic-2-athlete-ai-chat-experience.md |
| ☐ | **Build admin shell** — create admin navigation for documents, analytics, users, and audit surfaces with role-gated access | US-03, US-04, US-12, US-18, US-24 | Admin GET documents route renders placeholder surface -> admin GET analytics route renders placeholder surface -> athlete cannot access admin shell -> super_admin sees users/audit navigation | prd/01-user-stories/epic-1-authentication-roles-and-seamless-entry.md |
| ☐ | **Implement audit log service** — write immutable audit events for role changes and foundational admin actions | US-03, US-24 | Role change writes audit event -> audit query returns event for super_admin -> admin cannot mutate audit event through normal API | prd/02-technical-docs/data-model.md, prd/02-technical-docs/security.md |
| ☐ | **Define KB document foundation** — create backend records and service contract for uploaded/processing/ready/failed document status before full ingestion UI | US-12, US-13, US-15, US-16 | Admin creates document metadata record -> default visibility is all athletes -> metadata tags persist -> status enum rejects invalid state | prd/02-technical-docs/data-model.md, prd/02-technical-docs/_kb-service-architecture.md |
| ☐ | **Establish product observability baseline** — add structured logging fields for auth, role changes, chat shell access, and admin actions without PII/secrets | US-24, US-27 | Auth logs omit provider tokens -> admin action logs include request ID and actor ID -> role-change log links to audit ID -> tests or smoke checks verify no token logging | prd/02-technical-docs/security.md, prd/02-technical-docs/agentic-framework.md |

## Definition of Done

- [ ] Playbook product routes replace primary scaffold Example experience.
- [ ] OAuth/OIDC foundation works for Google and Microsoft in configured environments.
- [ ] Athlete signup/profile flow lands directly in chat.
- [ ] Athlete/admin/super-admin role guards are enforced in frontend routes and backend APIs.
- [ ] Playbook database foundation migrations apply cleanly.
- [ ] Audit logging exists for role changes and foundational admin actions.
- [ ] Chat and admin shells are ready for later feature implementation.
- [ ] Full available test suite passes in the configured project environment.
