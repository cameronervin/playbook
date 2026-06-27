# Phase 9 Conversation File Upload Handoff

## Purpose

This document is an implementation handoff and verification record for Phase 9
of the conversation file upload build. It breaks the work into small action
items and records which pieces have been completed.

Primary source documents:

- `backstage/development/conversation-file-upload-phased-build.md`
- `backstage/prd/03-implementation/phase-2-athlete-ai-experience.md`
- `backstage/prd/02-technical-docs/01-playbook/api-specification.md`
- `backstage/prd/02-technical-docs/01-playbook/data-model.md`
- `backstage/prd/02-technical-docs/01-playbook/integration-spec.md`
- `backstage/prd/02-technical-docs/02-kb-service/api-contracts.md`
- `backstage/prd/02-technical-docs/02-kb-service/ingestion-pipeline.md`
- `backstage/prd/02-technical-docs/02-kb-service/retrieval.md`
- `backstage/prd/02-technical-docs/02-kb-service/operations-security.md`

## Phase 9 Scope

Phase 9 moves admin KB document uploads and athlete conversation-file uploads
to a two-step direct-to-S3-compatible-storage flow:

- Backend creates an upload request after authorization and metadata validation.
- Backend returns a presigned upload contract and the backend document/file ID.
- Browser uploads the binary directly to object storage with progress and
  client-side retry.
- Browser calls a backend complete endpoint after upload.
- Backend verifies the object with `HEAD` before marking it uploaded.

Phase 9 also adds a durable backend outbox for KB-service ingest handoff. The
outbox worker derives trusted `source_type` metadata, calls
`BaseKnowledgebaseProvider.ingest_source(...)`, stores KB-service task/linkage
metadata, and retries transient failures without requiring users to re-upload.

KB-service remains responsible for parsing, chunking, embeddings, vectors,
summaries, retrieval, and private conversation-file isolation.

## Locked Decisions

| Decision | Locked direction |
|----------|------------------|
| Browser storage upload contract | Use presigned POST with `url` plus required `fields`. |
| Public upload route direction | Replace current multipart upload behavior with intent/complete flow. |
| Source metadata ownership | Backend derives `source_type`; browsers never choose it. |
| KB-service boundary | KB-service keeps parse, chunk, embed, vector, summary, and retrieval work. |
| Reliable handoff | Backend outbox owns retryable ingest dispatch after storage verification. |
| Completion verification | Backend must `HEAD` the object before marking a resource uploaded. |

## Target Public API Shape

The exact schema should be finalized during implementation, but later agents
should keep these behavioral contracts stable.

Admin KB document upload:

- `POST /api/v1/admin/kb/documents`
  - Request: JSON metadata for an upload request, including `filename`,
    `content_type`, `size_bytes`, and optional admin metadata such as `title`,
    `metadata_tags`, and `source_date`.
  - Response: safe `KBDocumentResponse`-compatible resource plus an upload
    contract containing `upload_request_id`, `method="POST"`, `url`, `fields`,
    and `expires_at`.
- `POST /api/v1/admin/kb/documents/{document_id}/upload-complete`
  - Request: `{ "upload_request_id": "uuid" }`.
  - Response: safe `KBDocumentResponse`.

Athlete conversation-file upload:

- `POST /api/v1/conversations/{conversation_id}/files`
  - Request: JSON metadata for an upload request, including `filename`,
    `content_type`, `size_bytes`, and optional `message_id` if the product
    chooses to attach uploads to a message at creation time.
  - Response: safe `ConversationFileSummaryResponse` plus an upload contract
    containing `upload_request_id`, `method="POST"`, `url`, `fields`, and
    `expires_at`.
- `POST /api/v1/conversations/{conversation_id}/files/{file_id}/upload-complete`
  - Request: `{ "upload_request_id": "uuid" }`.
  - Response: safe `ConversationFileSummaryResponse`.

Do not expose storage keys, source URLs, presigned URLs, or signed download URLs
from normal conversation detail or admin document responses after the upload
intent has been created.

## [COMPLETED] Phase 9A: Contracts and Migrations

Scope:

- Add request/response schemas for direct upload requests, upload completion,
  and safe upload contract responses.
- Add backend upload lifecycle statuses:
  - Admin KB documents: `upload_pending`, `uploaded`, `processing`, `ready`,
    `failed`.
  - Conversation files: `upload_pending`, `uploaded`, `extracting`, `ready`,
    `failed`.
- Add an `upload_requests` table for direct-upload lifecycle data.
- Add a `kb_ingest_outbox` table for durable KB-service handoff.
- Add repositories for intent lookup, completion, stale intent queries, outbox
  enqueueing, row locking, retry scheduling, and terminal state updates.

Suggested files:

- `backend/app/models/knowledge_base.py`
- `backend/app/models/conversations.py`
- `backend/app/models/__init__.py`
- `backend/app/repositories/knowledge_base.py`
- `backend/app/repositories/conversations.py`
- `backend/app/schemas/kb_documents.py`
- `backend/app/schemas/conversations.py`
- `backend/alembic/versions/`
- `backend/tests/unit/test_playbook_models_metadata.py`
- `backstage/architecture/db.md`

Acceptance criteria:

- Alembic migration adds both tables with useful indexes for resource lookup,
  expiry cleanup, status polling, and outbox draining.
- Model metadata tests include new tables, indexes, defaults, and status fields.
- Repositories can create, resolve, complete, expire, and list due rows without
  committing outside service boundaries.
- No existing response schema exposes storage keys or source URLs.

Relevant tests:

- Unit model metadata tests.
- Repository integration tests for `upload_requests`.
- Repository integration tests for `kb_ingest_outbox` idempotency and row
  locking.
- Alembic upgrade/downgrade smoke.

Do not do yet:

- Do not wire browser upload UI.
- Do not call KB-service from request handlers.
- Do not mark Phase 9 implemented in PRD/status docs.

## [COMPLETED] Phase 9B: Presigned POST Storage Support

Scope:

- Extend the storage provider interface with a direct-upload method that returns
  a presigned POST contract.
- Add object metadata verification support with `HEAD`.
- Implement S3/MinIO behavior using `boto3.generate_presigned_post(...)`.
- Include policy conditions for fixed key, expected content type, and
  `content-length-range`.
- Return safe object metadata from `HEAD`, such as content length, content type,
  ETag, and checksum fields when available.
- Update MinIO local setup so browser uploads from the frontend origin are
  allowed by bucket CORS.

Implemented behavior:

- `StorageProvider` now exposes direct-upload POST contract creation, object
  metadata lookup, and reusable expected-size/content-type verification.
- `S3StorageProvider` generates constrained presigned POST contracts using
  fixed key, fixed content type, expiry, and `content-length-range` policy
  conditions.
- `S3StorageProvider.get_object_metadata(...)` wraps S3 `HEAD`, returns safe
  length/type/ETag/checksum metadata when available, and treats expected
  missing-object errors as `None`.
- Local Docker MinIO bootstrap creates the bucket and applies frontend-origin
  CORS for direct browser POST upload checks.
- `S3_PUBLIC_ENDPOINT_URL` supports Docker local browser uploads while backend
  signed GET URLs continue to use the internal storage endpoint.

Suggested files:

- `backend/app/infrastructure/storage/provider.py`
- `backend/app/infrastructure/storage/s3_client.py`
- `backend/app/infrastructure/storage/paths.py`
- `backend/app/core/config.py`
- `deploy/compose/local.yml`
- `deploy/envs/.env.local.example`
- `backstage/guides/minio_setup.md`
- `backstage/guides/setup.md`

Acceptance criteria:

- Storage tests prove presigned POST response shape includes `url` and required
  `fields`.
- Generated policy constrains key, content type, expiry, and max upload size.
- Completion verification can distinguish missing objects, wrong size, wrong
  content type, and valid objects.
- Storage errors are sanitized and do not log presigned URLs or credentials.
- Local MinIO accepts frontend-origin direct browser uploads.

Relevant tests:

- Unit tests for storage provider interface fakes.
- S3 provider tests with mocked boto3 calls.
- Local manual MinIO direct-upload smoke.

Do not do yet:

- Do not expose S3 credentials to the frontend.
- Do not rely on checksum verification unless storage exposes trustworthy
  checksum metadata.

## [COMPLETED] Phase 9C: Intent Creation and Completion Services

Scope:

- Refactor admin KB document upload from multipart ingestion to JSON intent
  creation.
- Refactor athlete conversation-file upload from multipart ingestion to JSON
  intent creation.
- Keep route auth semantics separate:
  - Admin routes authorize admin KB document upload.
  - Conversation routes authorize current-athlete ownership.
- Create backend resource rows at `upload_pending`.
- Generate deterministic storage keys using the backend resource ID.
- On completion, verify the upload request, call storage `HEAD`, compare expected
  size/content type, mark the resource `uploaded`, and enqueue exactly one
  outbox row.
- Make repeated completion calls idempotent.

Implemented behavior:

- Admin KB document upload now accepts JSON metadata, creates
  `kb_documents.processing_status="upload_pending"`, returns a safe document
  summary plus a presigned POST contract, and no longer streams browser file
  bytes through FastAPI on the public upload route.
- Athlete conversation-file upload now accepts JSON metadata, validates
  current-athlete conversation ownership, creates
  `conversation_files.extraction_status="upload_pending"`, returns a safe file
  summary plus a presigned POST contract, and no longer dispatches KB ingest
  from the request handler.
- Completion endpoints verify the scoped `upload_requests` row, use storage
  object verification before changing resource status, mark successful uploads
  `uploaded`, and enqueue a single `kb_ingest_outbox` row.
- Duplicate completion calls are idempotent through resource-scoped outbox
  enqueueing.
- Admin storage keys are deterministic by backend document ID:
  `kb/originals/{organization_id}/{document_id}/{filename}`.
- Browser-provided metadata cannot set reserved source/storage/KB-service
  identifiers such as `source_type`, `organization_id`, `source_uri`, or
  `kb_service_document_id`.
- Unlinked direct-upload document retry requests re-queue the outbox instead of
  bypassing reliable handoff with a direct KB-service ingest call.

Suggested files:

- `backend/app/api/v1/kb_documents.py`
- `backend/app/api/v1/conversations.py`
- `backend/app/api/v1/dependencies.py`
- `backend/app/services/kb_document_service.py`
- `backend/app/services/conversation_service.py`
- `backend/app/repositories/knowledge_base.py`
- `backend/app/repositories/conversations.py`
- `backend/tests/integration/test_kb_document_routes.py`
- `backend/tests/integration/test_conversation_routes.py`

Acceptance criteria:

- Large browser-path uploads do not stream file bytes through FastAPI request
  bodies.
- Backend never marks admin documents or conversation files `uploaded` until
  storage `HEAD` verification succeeds.
- Duplicate complete calls do not create duplicate outbox rows.
- Cross-athlete completion attempts cannot reveal or complete another
  conversation's file.
- Completion responses are safe and do not include storage keys or signed URLs.

Relevant tests:

- Admin intent creation and completion route tests.
- Conversation-file intent creation and completion route tests.
- Ownership and role authorization tests.
- Invalid filename, content type, size, expired intent, missing object, and size
  mismatch tests.
- Duplicate completion tests.

Do not do yet:

- Do not parse, chunk, embed, or retrieve in backend.
- Do not let browsers provide `source_type`, `organization_id`, or KB-service
  identifiers.
- Do not expose raw storage internals after intent creation.

## [COMPLETED] Phase 9D: Durable Ingest Outbox Worker

Scope:

- Add a backend worker task to drain due `kb_ingest_outbox` rows.
- Use row locking such as `FOR UPDATE SKIP LOCKED` to avoid duplicate workers
  processing the same row.
- Derive trusted `KBIngestRequest` payloads from backend resource rows:
  - `admin_upload` from `kb_documents`.
  - `conversation_file` from `conversation_files`.
- Generate a short-lived signed source URL for KB-service ingestion.
- Call `BaseKnowledgebaseProvider.ingest_source(...)`.
- Persist `kb_service_document_id`, KB task ID, dispatch attempts, next retry,
  and safe failure metadata.
- Update admin document events for upload verified, ingest queued, dispatched,
  retried, and failed.

Implemented behavior:

- Backend worker routing now includes `backend-files` plus
  `drain_kb_ingest_outbox_task(limit=25)` for verified direct-upload ingest
  handoff.
- The outbox service drains due rows one locked row at a time with
  `FOR UPDATE SKIP LOCKED`, derives trusted admin/conversation-file ingest
  payloads from backend records, and generates signed source URLs only at
  dispatch time.
- Successful dispatch records KB-service document/task linkage, moves admin
  documents to `processing`, moves conversation files to `extracting`, and
  appends safe admin lifecycle events.
- Retryable KB/storage failures schedule backoff using existing KB retry
  settings; terminal failures mark outbox rows and backend resources failed with
  sanitized metadata.
- Upload completion and worker startup kick the drain task without making user
  responses depend on Celery broker availability.

Suggested files:

- `backend/app/workers/tasks.py`
- `backend/app/workers/queues.py`
- `backend/app/workers/app.py`
- `backend/app/services/kb_document_service.py`
- `backend/app/services/conversation_service.py`
- `backend/app/infrastructure/knowledgebase/providers/base.py`
- `backend/app/repositories/knowledge_base.py`
- `backend/app/repositories/conversations.py`
- `backend/tests/integration/test_kb_ingest_outbox_worker.py`

Acceptance criteria:

- Accepted uploads survive backend restarts and KB-service downtime.
- Transient KB-service failures retry with backoff and do not require
  re-upload.
- Terminal dispatch failures mark resources failed with sanitized reasons.
- Worker records KB-service linkage when dispatch succeeds.
- Duplicate worker attempts are safe.

Relevant tests:

- Outbox worker success tests for admin documents and conversation files.
- Retry scheduling tests for transient provider failures.
- Terminal failure tests with sanitized metadata.
- Duplicate worker attempt/idempotency tests.
- Redaction tests for signed source URLs.
- Worker queue/task scaffold tests.

Do not do yet:

- Do not move KB-service document intelligence into backend workers.
- Do not log signed source URLs or raw file content.

## [COMPLETED] Phase 9E: KB-Service Ingest Idempotency

Scope:

- Ensure repeated KB ingest calls for the same trusted source identity do not
  create duplicate KB-service documents.
- Preserve current private retrieval guarantees for conversation files.
- For admin uploads, use `playbook_document_id` as the idempotent source
  identity.
- For conversation files, use `conversation_file_id` plus trusted conversation
  metadata as the idempotent source identity.
- Return the existing in-progress or completed KB-service document response
  when a duplicate ingest call is received.

Suggested files:

- `kb-service/app/services/ingestion_service.py`
- `kb-service/app/repositories/document_repo.py`
- `kb-service/app/schemas/ingest.py`
- `kb-service/tests/test_services/test_ingestion_service.py`
- `kb-service/tests/test_contracts/test_source_type_contracts.py`

Acceptance criteria:

- Duplicate admin ingest calls for the same `playbook_document_id` are
  idempotent.
- Duplicate conversation-file ingest calls for the same `conversation_file_id`
  are idempotent.
- Existing shared-KB and private-conversation retrieval filters still prevent
  cross-source leaks.
- Existing retry/delete behavior remains compatible.

Implementation notes:

- KB-service now checks JSONB metadata for trusted source identity before
  storage `HEAD`, MD5 download, or Celery dispatch.
- Active duplicates return the existing pipeline task ID; terminal duplicates
  return the existing KB-service document with `task_id=null`.
- Content-MD5 dedupe remains as a legacy guard, but same-content submissions
  for a different trusted source identity return `409` instead of replacing an
  existing document.

Relevant tests:

- KB-service ingest idempotency tests for `admin_upload`.
- KB-service ingest idempotency tests for `conversation_file`.
- Private retrieval isolation regression tests.

Do not do yet:

- Do not add first-class KB-service source identity columns unless this phase
  explicitly includes the migration and JSON backfill.
- Do not relax current metadata validation.

## [COMPLETED] Phase 9F: Reconciliation and Cleanup

Scope:

- Add maintenance logic for expired pending upload requests.
- Mark expired resources failed with a safe user-facing reason.
- Clean up orphaned objects only when they belong to expired known intents.
- Add observability for stuck upload-pending resources and outbox backlog.
- Decide only short-term cleanup needed for Phase 9; keep long-term retention
  policy as a follow-up unless product requirements settle it.

Implemented behavior:

- Backend maintenance now includes `reconcile_upload_requests_task` on the
  `backend-maintenance` queue.
- Upload intent creation schedules reconciliation for the returned contract
  expiration time without making the HTTP response depend on broker
  availability.
- Backend worker startup also kicks reconciliation, and each reconciliation
  pass self-schedules for the next pending expiration when one exists.
- Expired pending admin upload requests move still-`upload_pending` documents to
  `failed`, append a safe `document.upload_expired` lifecycle event, and delete
  the known intent object when storage confirms it exists.
- Expired pending conversation-file upload requests move still-`upload_pending`
  files to `failed` with safe athlete-visible error metadata and delete the
  known intent object when storage confirms it exists.
- Reconciliation uses row locking with `FOR UPDATE SKIP LOCKED`, is idempotent
  across duplicate task runs, skips resources already transitioned out of the
  pending state, and reports safe counters for object cleanup, stuck
  upload-pending resources, and due outbox backlog.
- Long-term retention for successful originals and extracted artifacts remains
  deferred in `backstage/development/tech-debt-tracker.md`.

Suggested files:

- `backend/app/workers/tasks.py`
- `backend/app/repositories/knowledge_base.py`
- `backend/app/repositories/conversations.py`
- `backend/app/services/kb_document_service.py`
- `backend/app/services/conversation_service.py`
- `backend/tests/integration/test_upload_request_reconciliation.py`
- `backstage/development/tech-debt-tracker.md`

Acceptance criteria:

- Expired upload requests transition resources out of `upload_pending`.
- Orphan cleanup deletes only keys tied to known expired intents.
- Safe failure reasons do not include storage keys, signed URLs, or secrets.
- Maintenance task is retryable and safe to run repeatedly.

Relevant tests:

- Expired intent reconciliation tests.
- Orphan object cleanup tests.
- Idempotent maintenance task tests.
- Logging redaction tests.

Do not do yet:

- Do not delete successful original files.
- Do not decide long-term retention for original conversation files and
  extracted artifacts unless product requirements explicitly settle it.

## [COMPLETED] Phase 9G: Frontend Direct Upload Flow

Scope:

- Update typed API adapters and hooks for JSON intent creation and completion.
- Replace admin KB multipart upload usage with direct upload flow.
- Enable athlete chat attachment upload through the composer.
- Upload to presigned POST with browser progress tracking.
- Call backend completion after storage upload succeeds.
- Invalidate TanStack Query caches for KB documents, conversation list, and
  conversation detail after completion.
- Render statuses for upload pending, uploading progress, uploaded/queued,
  extracting/processing, ready, and failed.

Suggested files:

- `frontend/src/lib/api/endpoints/kbDocuments.ts`
- `frontend/src/lib/api/endpoints/conversations.ts`
- `frontend/src/hooks/useKBDocuments.ts`
- `frontend/src/hooks/useConversations.ts`
- `frontend/src/components/features/admin/AdminKnowledgeBasePanel.tsx`
- `frontend/src/components/features/chat/ChatComposer.tsx`
- `frontend/src/components/features/chat/ChatShell.tsx`
- `frontend/src/types/kb.ts`
- `frontend/src/types/conversations.ts`

Acceptance criteria:

- Admin KB uploads no longer send file bytes to FastAPI in the normal browser
  path.
- Athlete conversation-file uploads show progress and final backend status.
- Failed storage upload or failed completion is recoverable by starting a new
  intent.
- UI never renders raw storage keys, presigned URLs, or signed source URLs.
- Existing chat and admin layout remains responsive and accessible.

Relevant tests:

- Frontend API adapter tests for intent, storage POST helper, and completion.
- Component tests for upload progress, error, retry, completion success, and
  status rendering.
- Accessibility checks for upload controls.

Do not do yet:

- Do not add file download/export.
- Do not expose internal KB summaries to athletes.

Implemented behavior:

- Frontend API adapters and hooks use JSON intent creation, browser direct
  storage POST, completion calls, and TanStack Query invalidation for admin KB
  documents and conversation files.
- Admin and chat UI surfaces render local upload progress, recoverable upload
  failure, completion status, and backend/KB processing states without exposing
  storage keys, presigned URLs, source URIs, or internal summaries.

## [COMPLETED] Phase 9H: Documentation and Verification

Scope:

- Update docs after implementation agents complete the runtime work.
- Create concise upload flow architecture markdown document located in backstage/architecture with ASCII diagrams
- Do not update API/spec docs before implementation as though Phase 9 is live.
- Add smoke instructions for local MinIO, backend worker, KB-service, and
  frontend upload validation.

Suggested files:

- `backstage/development/conversation-file-upload-phased-build.md`
- `backstage/api/endpoints.md`
- `backstage/architecture/db.md`
- `backstage/guides/setup.md`
- `backstage/guides/minio_setup.md`
- `backstage/prd/03-implementation/phase-2-athlete-ai-experience.md`
- `backstage/prd/02-technical-docs/01-playbook/api-specification.md`
- `backstage/prd/02-technical-docs/01-playbook/data-model.md`
- `backstage/prd/02-technical-docs/01-playbook/integration-spec.md`
- `backstage/prd/02-technical-docs/02-kb-service/api-contracts.md`
- `backstage/prd/02-technical-docs/02-kb-service/ingestion-pipeline.md`

Acceptance criteria:

- Docs clearly distinguish implemented behavior from planned behavior.
- Endpoint docs match actual route behavior after implementation.
- Setup docs include any new MinIO CORS or worker schedule requirements.
- Phase 2 status reflects Phase 9 only after tests/smoke pass.

Implemented behavior:

- Added `backstage/architecture/direct-upload-flow.md` with ASCII diagrams for admin
  document upload, conversation-file upload, and failure/retry paths.
- Updated API, database, setup, MinIO, PRD, and phase status docs to describe
  the implemented direct-upload intent/complete runtime instead of historical
  multipart upload behavior.
- Documented local prerequisites for MinIO preflight, backend workers on
  `backend-files` and `backend-maintenance`, KB-service API/workers, frontend,
  and private KB-service smoke coverage.

Verification recorded on 2026-06-17:

- Backend targeted unit checks passed:
  `27 passed in 0.41s`.
- Backend targeted integration checks passed:
  `43 passed, 4 warnings in 58.97s`.
- KB-service targeted checks passed:
  `42 passed in 1.57s`.
- Frontend targeted checks passed:
  typecheck, lint, and `49` focused Vitest tests.
- MinIO bucket bootstrap and browser preflight were verified locally; preflight
  from `http://localhost:3000` returned `204` with POST allowed.
- `kb-service/scripts/smoke_kb_service.py --include-conversation-file` passed
  after applying KB migrations and restarting stale local KB workers. It
  confirmed shared admin-style ingest/search, private conversation-file
  ingest/search, and default shared-search isolation.
- Backend route tests cover direct-upload intent creation, storage `HEAD`
  verification, duplicate completion idempotency, and outbox row creation for
  both admin documents and conversation files.
- Browser admin/chat UI smoke and the Phase 2 live grounded citation smoke were
  not promoted to complete here; Phase 2 keeps citation validation marked
  remaining until seeded local retrieval data proves an athlete answer cites a
  ready conversation file.

Relevant tests and checks:

- Backend unit/integration tests for touched services.
- KB-service contract and ingestion tests.
- Frontend typecheck, lint, and component tests.
- Local smoke:
  - admin document direct upload -> completion -> outbox dispatch -> ready
  - conversation-file direct upload -> completion -> private ingest -> ready
  - athlete chat answer can cite ready conversation file

Do not do yet:

- Do not mark Phase 9 as implemented until runtime code, docs, and smoke checks
  are complete.
- Do not add broad claims that upload reliability is complete without outbox
  retry and duplicate-completion coverage.

## Cross-Phase Test Matrix

| Area | Required scenarios |
|------|--------------------|
| Contracts | Request/response validation, safe response shape, status enum coverage |
| Storage | Presigned POST shape, policy constraints, `HEAD` verification, sanitized failures |
| Intent creation | Admin auth, athlete ownership, filename/type/size validation, safe resource creation |
| Completion | Object missing, size mismatch, content-type mismatch, duplicate completion, expired intent |
| Outbox | Restart-safe queued rows, retryable KB handoff, idempotent dispatch, terminal failure metadata |
| KB-service | Duplicate source identity, valid/invalid `admin_upload`, valid/invalid `conversation_file` |
| Reconciliation | Expired pending intents, orphan cleanup, idempotent maintenance |
| Frontend | Progress, retry, completion, status display, cache invalidation |
| Security | No browser-supplied `source_type`, no storage secrets in responses/logs, no private source leaks |

## Implementation Notes

- Prefer shared helper code for common intent/completion behavior while keeping
  public admin and athlete routes separate for auth and product semantics.
- Preserve the existing backend-to-KB provider seam:
  `BaseKnowledgebaseProvider.ingest_source(KBIngestRequest)`.
- Use structured logging and existing redaction utilities for any object-storage
  and KB-service errors.
- Keep source URLs short-lived and generated only when the outbox worker is
  ready to dispatch.
- Treat summaries as internal orientation metadata; final answers must still
  cite retrieved chunks.

## Explicit Non-Goals

- No backend parsing, chunking, embedding, vector storage, or retrieval.
- No browser-provided `source_type` or KB-service metadata.
- No raw storage keys, signed URLs, source URLs, extracted text references, or
  raw file content in normal public responses.
- No file download/export feature.
- No long-term retention policy decision unless separately requested.
