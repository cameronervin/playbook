# Phase 3: Knowledge Base Admin

## Scope boundary for this phase

Phase 3 turns the scaffold KB service into an admin-manageable Playbook knowledgebase for athlete answers.

| Status | Goal | User Stories | Validation | PRD Docs |
|--------|------|-------------|------------|----------|
| ☐ | **Build admin document upload UI/API** — upload supported department docs and create KB records | US-12, US-24 | Admin POST document succeeds -> document record status is uploaded -> audit event records upload -> athlete cannot upload shared KB doc | prd/02-technical-docs/01-playbook/api-specification.md |
| ☐ | **Connect ingestion status lifecycle** — show uploaded/processing/ready/failed states from backend and KB service | US-13 | Upload starts processing -> status transitions to processing -> ready doc is searchable -> failed doc shows reason | prd/02-technical-docs/02-kb-service/api-contracts.md, prd/02-technical-docs/02-kb-service/ingestion-pipeline.md |
| ☐ | **Implement retry and re-upload** — let admins recover failed parsing/indexing | US-14, US-24 | Failed doc retry restarts ingestion -> no-text failure remains failed with reason -> re-upload creates audit event -> failed docs are excluded from retrieval | prd/01-user-stories/epic-3-knowledge-base-and-document-operations.md, prd/02-technical-docs/02-kb-service/ingestion-pipeline.md |
| ☐ | **Implement metadata tags and ranking fields** — manage official/priority/source/freshness metadata and pass through retrieval | US-15, US-17, US-24 | PATCH metadata persists tags -> search result returns source_date/is_official/priority -> official/priority metadata can affect ranking -> audit event records metadata update | prd/02-technical-docs/01-playbook/data-model.md, prd/02-technical-docs/02-kb-service/data-model.md, prd/02-technical-docs/02-kb-service/retrieval.md |
| ☐ | **Preserve extensible visibility model** — enforce all-athlete visibility now with future team/sport hooks | US-16 | Ready doc visible to all athlete retrieval -> visibility_policy defaults to all_athletes -> invalid visibility policy is rejected -> model supports future audience data | prd/02-technical-docs/01-playbook/data-model.md, prd/02-technical-docs/01-playbook/security.md |

## Definition of Done

- [ ] Admins can upload, view, tag, retry, and manage KB documents.
- [ ] Ready documents are searchable by the athlete chat agent.
- [ ] Failed documents do not influence answers.
- [ ] Metadata needed for citations and conflict handling is returned by retrieval.
- [ ] Document admin actions are audited.
