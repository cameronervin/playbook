# KB Service Retrieval Fix Handoff

## Purpose

This note is a coding-agent handoff for making local KB retrieval reliable enough
for the athlete chat agent. It is not a PRD rewrite; use the PRD links below as
the source of product intent and this note as the focused fix list.

Related docs:
- `prd/03-implementation/phase-2-athlete-ai-experience.md`
- `prd/03-implementation/phase-3-knowledge-base-admin.md`
- `prd/02-technical-docs/02-kb-service/retrieval.md`
- `prd/02-technical-docs/02-kb-service/api-contracts.md`

## Issues To Resolve

1. **Visibility filter mismatch**: athlete chat filters on `visibility_scope`,
   while KB ingestion stores `visibility_policy`. Normalize on
   `visibility_policy.scope`.
2. **Resolved — Missing organization scoping**: retrieval now requires trusted
   top-level `organization_id`, stamps fresh ingest/vector metadata with that
   value, and filters vector search by `organization_id` before returning
   chunks. Existing vectors without org metadata are intentionally invisible
   until re-ingested or backfilled.
3. **Unready documents may be searchable**: KB search reads vector rows directly
   without filtering against ready/success document status. Failed,
   in-progress, and deleted documents must be excluded.
4. **Resolved — Citation metadata is incomplete**: KB vector inserts now stamp
   deterministic `chunk_id` values from KB-service document ID + chunk index,
   store Playbook `document_id`, `kb_service_document_id`, `chunk_index`, and
   source metadata in vector metadata, and search returns those fields at the
   top level plus in `metadata`. The backend local provider accepts both
   current `chunks` and future `results` payloads and persists citations with
   Playbook `document_id`, stable `chunk_id`, and full source metadata.
5. **Default KB configuration is manual/fragile**: keep the configuration
   concept, but make the default Playbook configuration automatic and
   idempotent so fresh local ingest/search does not require manual setup.
6. **KB-service API contract drift**: reconcile PRD semantic routes with the
   current scaffold routes, or document the intentional adapter mapping.
7. **No-text extraction is unclear**: documents that produce zero usable chunks
   should fail with a clear no-text reason instead of silently continuing.
8. **Ranking/conflict handling is incomplete**: retrieval/agent orchestration
   does not yet apply `is_official`, `priority`, and `source_date` conflict
   rules.
9. **OCR is stubbed**: future OCR should use a LiteLLM-routed vision model, not
   AWS Textract. Implement the `vlm` provider path and avoid adding Textract
   dependencies.
10. **Env names differ across services**: reconcile KB-service names with
    backend names for LiteLLM and S3/MinIO, or support aliases with documented
    precedence.

Key code areas:
- `backend/app/agents/tools/knowledgebase.py`
- `backend/app/infrastructure/knowledgebase/providers/local_kb.py`
- `kb-service/app/repositories/vector_repo.py`
- `kb-service/app/services/configuration_service.py`
- `kb-service/app/infrastructure/parsers/providers/ocr/ocr.py`

## Required Change Direction

- Keep default KB configuration as an internal singleton. Prefer an idempotent
  `configuration/resolve` path or equivalent service-owned default creation.
- Store and filter retrieval metadata by `organization_id` and
  `visibility_policy.scope`.
- Filter KB search by successful/ready document status before returning chunks.
- Return citation-ready search metadata: Playbook document ID, KB-service
  document ID, chunk ID/index, text, score, source title/date, official flag,
  priority, and visibility policy.
- Implement OCR/VLM through LiteLLM model aliases and LiteLLM credentials. Do
  not implement Textract for this product path.
- Reconcile env naming around:
  - LiteLLM: backend uses `LITELLM_BASE_URL` / `LITELLM_API_KEY`; KB-service
    currently uses `LLM_GATEWAY_BASE_URL` / `LLM_GATEWAY_API_KEY`.
  - Storage: backend uses `S3_*`; KB-service currently uses `AWS_S3_*` and
    `AWS_*`.

## Suggested Acceptance Criteria

- A fresh local KB database can ingest and search without manually creating a
  configuration row.
- Ready documents are searchable by the athlete chat agent.
- Failed, deleted, and in-progress documents are excluded from retrieval.
- A golden NIL/compliance prompt retrieves the expected source and persists a
  citation tied to the retrieved chunk.
- OCR/VLM uses LiteLLM credentials/model aliases rather than provider API keys
  in KB-service runtime config.
- Backend and KB-service env examples use consistent names or explicitly
  document supported aliases and precedence.
