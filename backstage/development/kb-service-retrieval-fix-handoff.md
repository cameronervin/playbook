# KB Service Retrieval Fix Handoff

## Purpose

This note is a coding-agent handoff for making local KB retrieval reliable enough
for the athlete chat agent. It is not a PRD rewrite; use the PRD links below as
the source of product intent and this note as the focused fix list.

Related docs:
- `backstage/prd/03-implementation/phase-2-athlete-ai-experience.md`
- `backstage/prd/03-implementation/phase-3-knowledge-base-admin.md`
- `backstage/prd/02-technical-docs/02-kb-service/retrieval.md`
- `backstage/prd/02-technical-docs/02-kb-service/api-contracts.md`

## Issues To Resolve

1. **Resolved — Visibility filter mismatch**: athlete chat filters on `visibility_scope`,
   while KB ingestion stores `visibility_policy`. Normalize on
   `visibility_policy.scope`.
2. **Resolved — Missing organization scoping**: retrieval now requires trusted
   top-level `organization_id`, stamps fresh ingest/vector metadata with that
   value, and filters vector search by `organization_id` before returning
   chunks. Existing vectors without org metadata are intentionally invisible
   until re-ingested or backfilled.
3. **Resolved — Unready documents may be searchable**: KB search reads vector rows directly
   without filtering against ready/success document status. Failed,
   in-progress, and deleted documents must be excluded.
4. **Resolved — Citation metadata is incomplete**: KB vector inserts now stamp
   deterministic `chunk_id` values from KB-service document ID + chunk index,
   store Playbook `document_id`, `kb_service_document_id`, `chunk_index`, and
   source metadata in vector metadata, and search returns those fields at the
   top level plus in `metadata`. The backend local provider accepts both
   current `chunks` and future `results` payloads and persists citations with
   Playbook `document_id`, stable `chunk_id`, and full source metadata.
5. **Resolved — Default KB configuration is automatic/idempotent**: KB-service
   `/configuration/resolve` now owns the singleton Playbook defaults, recovers
   from concurrent first-call creates, and search resolves the default before
   vector lookup so fresh local ingest/search does not require manual setup.
6. **Resolved — KB-service API contract drift**: reconciled with a hard cutover to PRD
   semantic routes only. Backend `LocalKBProvider` now calls canonical
   `/configuration/resolve`, `/ingest/document`, `/search`,
   `/status/documents/{document_id}`, `/documents/{document_id}/retry`, and
   `/documents/{document_id}` routes; old scaffold routes are absent from
   OpenAPI and return 404.
7. **Resolved — No-text extraction is unclear**: documents that produce zero
   usable parser text or zero usable chunks now fail with a clear
   `NO_TEXT_EXTRACTED` reason instead of silently continuing.
8. **Resolved — MVP retrieval order is KB-service owned**:
   admin-uploaded shared KB documents are official by definition, priority is
   not a user-facing MVP ranking control, and backend retrieval preserves
   KB-service order after temporary order-preserving defensive dedupe.
9. **Resolved — OCR/VLM provider is opt-in**: high-complexity scanned PDFs can
   use `OCR_PROVIDER=vlm`, which routes page images through a LiteLLM vision
   model alias. `OCR_PROVIDER=none` remains the default, and Textract remains
   unsupported with no added dependencies.
10. **Resolved — Env names differ across services**: reconcile KB-service names with
    backend names for LiteLLM and S3/MinIO, or support aliases with documented
    precedence.

Key code areas:
- `backend/app/agents/tools/knowledgebase.py`
- `backend/app/infrastructure/knowledgebase/providers/local_kb.py`
- `kb-service/app/repositories/vector_repo.py`
- `kb-service/app/services/configuration_service.py`
- `kb-service/app/infrastructure/parsers/providers/ocr.py`

## Required Change Direction

- Keep default KB configuration as an internal singleton. Prefer an idempotent
  `configuration/resolve` path or equivalent service-owned default creation.
- Store and filter retrieval metadata by `organization_id` and
  `visibility_policy.scope`.
- Filter KB search by successful/ready document status before returning chunks.
- Return citation-ready search metadata: Playbook document ID, KB-service
  document ID, chunk ID/index, text, score, source title/date, and visibility
  policy.
- Implement OCR/VLM through LiteLLM model aliases and LiteLLM credentials. Do
  not implement Textract for this product path.
- Keep env naming canonical across backend and KB-service:
  - LiteLLM: `LITELLM_BASE_URL` / `LITELLM_API_KEY`.
  - Storage: `S3_*`.

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
