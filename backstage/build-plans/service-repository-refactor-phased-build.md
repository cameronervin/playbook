# Service and Repository Refactor Phased Build

## Purpose

This is a planning artifact, not implemented behavior. It breaks the largest
Playbook service, repository, and feature-shell modules into independently
testable refactor phases so later coding agents can improve maintainability
without changing product behavior.

Primary source documents:

- `backstage/architecture/overview.md`
- `backstage/prd/03-implementation/phase-2-athlete-ai-experience.md`
- `backstage/development/hybrid-search-reranker-phased-build.md`
- `.claude/rules/00-tdd.md`
- `.claude/rules/01-patterns.md`
- `.claude/rules/02-python.md`
- `.claude/rules/06-testing.md`
- `.claude/rules/08-security.md`
- `.claude/rules/11-logging.md`
- `.claude/rules/14-frontend-code-organization.md`

## Current State

The architecture expects thin routes, services for business orchestration,
repositories for database access, and infrastructure modules for external
systems. The current implementation follows that layering, but several files
have grown large enough that unrelated responsibilities now change together.

Original confirmed hotspots, with phase status where completed:

| File | Current size / status | Main responsibilities mixed before refactor |
|------|--------------|-----------------------------------|
| `kb-service/app/repositories/vector_repo.py` | Phase 1 completed; was 991 lines before split | chunk record shaping, metadata normalization, SQL statement construction, row mapping, semantic search, lexical search, hybrid ranking, dedupe, sync worker repository, async API repository |
| `backend/app/services/kb_document_service.py` | 865 lines | admin KB document CRUD, upload validation, direct-upload presign/complete, multipart upload, KB ingest handoff, audit/events, delete/retry, signed webhook processing |
| `backend/app/services/conversation_service.py` | 835 lines | conversation CRUD, message submission, worker dispatch, stream authorization, conversation-file upload, direct-upload completion, ingest metadata, DTO mapping |
| `kb-service/app/services/ingestion_service.py` | 578 lines | ingest metadata normalization, S3 size/hash inspection, dedupe/source identity rules, Celery pipeline dispatch, status response mapping, retry, delete |
| `backend/app/repositories/conversations.py` | 542 lines | four small repositories in one file: conversations, messages, citations, conversation files |
| `backend/app/services/kb_ingest_outbox_service.py` | 526 lines | durable row draining plus admin-upload and conversation-file source handling, retry/failure decisions, resource state updates |
| `frontend/src/components/features/admin/AdminKnowledgeBasePanel.tsx` | 476 lines | collection grid, collection detail view, local upload state, upload row rendering, formatters, icon mapping |

The Phase 2 athlete AI experience is active work. Refactors must preserve the
message submit -> Celery task -> Valkey stream -> assistant persistence path,
conversation-file upload behavior, private retrieval filters, and citation
persistence semantics.

The worktree may contain ongoing unrelated changes, especially around hybrid
search and Phase 2 validation. Future agents must inspect `git status -sb`
before editing and must not revert unrelated user changes.

## Target Architecture

The target is smaller modules with stable facades, not a product rewrite.
Routes, schemas, database tables, public API contracts, worker task names, and
frontend user-visible behavior should remain unchanged unless a later phase
explicitly says otherwise.

```text
FastAPI routes
  -> feature services or compatibility facade services
    -> focused workflow helpers
    -> repositories
      -> SQLAlchemy models

KB-service search
  -> SearchService
    -> AsyncVectorRepository facade
      -> vector SQL builders
      -> row mappers
      -> ranking/dedupe helpers

KB-service workers
  -> VectorRepository facade
    -> shared vector record builders
    -> sync persistence methods
```

## Locked Decisions or Implementation Defaults

| Decision | Direction |
|----------|-----------|
| Runtime behavior | Refactor-only. Preserve existing behavior, public DTOs, route paths, task names, env names, and DB schema. |
| Compatibility | Keep import-compatible facades during each phase so callers can migrate incrementally. |
| TDD | For each non-trivial extraction, add or update tests first, then move code, then remove compatibility only after all imports are migrated. |
| Dependencies | No new dependencies. Use existing Python, FastAPI, SQLAlchemy, pytest, TypeScript, TanStack Query, Zustand, and Vitest patterns. |
| API contracts | Do not change request or response shapes in this refactor. |
| Database | Do not add migrations or schema changes. |
| Logging | Preserve structured `structlog` events and do not add raw file text, request bodies, signed URLs, tokens, secrets, or private metadata to logs. |
| Security | Preserve organization, athlete ownership, conversation-file scope, webhook signature checks, and trusted server-side metadata ownership. |
| Docs | Update this plan only when a phase is actually completed and verified. Do not mark planned work as implemented. |

## Ownership and Boundary Rules

- Backend routes remain thin: validate request, call a service, return a DTO.
- Backend services own business orchestration, authorization-scoped workflow
  decisions, audit/event side effects, worker dispatch, and DTO mapping.
- Backend repositories own SQLAlchemy persistence only. They should not make
  product decisions, call storage, call KB-service, or emit audit events.
- KB-service owns ingest pipeline execution, vector persistence/search,
  retrieval ranking, reranking orchestration, and internal source metadata
  normalization.
- Backend owns authenticated public routes, chat context assembly, final answer
  persistence, and final citation persistence.
- Frontend components own rendering and local UI state only. Server data stays
  in TanStack Query; UI state stays in Zustand.
- Frontend callers must never choose trusted `source_type`, organization scope,
  visibility policy, storage keys, KB-service document IDs, or private
  conversation-file filters.

## Phase 0: Baseline and Import Map

Scope:

- Capture current import graph and test coverage before runtime refactors.
- Add this build plan and verify no existing behavior was changed.
- Identify the exact compatibility facades that future phases will preserve.

Suggested files:

- `backstage/development/service-repository-refactor-phased-build.md`
- No runtime files in this phase.

Acceptance criteria:

- This document exists and clearly states the target module boundaries.
- Relative to this planning phase, only this document was added.
- Future agents can see which tests to run for each extraction phase.

Relevant tests:

- Not required for docs-only work.

Do not do yet:

- Do not move imports.
- Do not split runtime files.
- Do not mark later phases as implemented.

## Phase 1: Split KB-Service Vector Repository Internals

Status: Completed on 2026-06-18.

Scope:

- Extract pure vector helpers first while keeping
  `app.repositories.vector_repo` as an import-compatible facade.
- Preserve `VectorRepository`, `AsyncVectorRepository`, and
  `dedupe_ranked_results` import paths until all callers and tests are migrated.
- Separate pure functions from DB-bound repository classes.

Suggested files:

- `kb-service/app/repositories/vector_repo.py`
- `kb-service/app/repositories/vector_records.py`
- `kb-service/app/repositories/vector_queries.py`
- `kb-service/app/repositories/vector_ranking.py`
- `kb-service/app/repositories/vector_mapping.py`
- `kb-service/app/repositories/vector_sync.py`
- `kb-service/app/repositories/vector_async.py`
- `kb-service/tests/test_app/test_repositories/test_vector_repository.py`
- `kb-service/tests/test_services/test_search_service.py`

Acceptance criteria:

- `VectorRepository` and `AsyncVectorRepository` continue to support existing
  search, lexical search, hybrid search, insert, count, and delete behavior.
- Semantic, lexical, and hybrid candidate ordering are unchanged.
- Source-scope filters remain identical across semantic and lexical paths.
- Dedupe order remains `chunk_id`, then exact text fallback.
- Sync worker imports in `kb-service/app/workers/tasks/embedding.py` and
  `kb-service/app/workers/tasks/finalize.py` still work.
- Async service imports in `kb-service/app/services/search_service.py` and
  `kb-service/app/services/ingestion_service.py` still work.

Relevant tests:

- `cd kb-service && uv run pytest tests/test_app/test_repositories/test_vector_repository.py -v`
- `cd kb-service && uv run pytest tests/test_services/test_search_service.py -v`
- `cd kb-service && uv run ruff check app tests`

Completed verification on 2026-06-18:

- `cd kb-service && uv run pytest tests/test_app/test_repositories/test_vector_repository.py -v` -> 23 passed
- `cd kb-service && uv run pytest tests/test_services/test_search_service.py -v` -> 15 passed
- `cd kb-service && uv run ruff check app tests` -> passed
- `cd kb-service && uv run python -m compileall app tests` -> passed

Do not do yet:

- Do not change search strategy defaults.
- Do not change reranker behavior.
- Do not move KB-service API schemas.
- Do not remove the compatibility exports from `vector_repo.py` in this phase.

## Phase 2: Extract Backend Direct-Upload Workflow Helpers

Status: Completed on 2026-06-18.

Scope:

- Reduce duplication between admin KB document uploads and conversation-file
  uploads by extracting shared direct-upload primitives.
- Keep route dependencies returning the existing public service classes.
- Preserve direct-upload request status transitions, storage verification,
  outbox enqueue, reconciliation dispatch, and safe validation errors.

Suggested files:

- `backend/app/services/kb_document_service.py`
- `backend/app/services/conversation_service.py`
- `backend/app/services/direct_uploads.py`
- `backend/app/services/upload_validation.py`
- `backend/app/repositories/uploads.py`
- `backend/tests/integration/test_kb_document_routes.py`
- `backend/tests/integration/test_conversation_routes.py`
- `backend/tests/integration/test_upload_request_repositories.py`
- `backend/tests/integration/test_upload_request_reconciliation.py`
- `backend/tests/unit/test_direct_upload_workflows.py`

Acceptance criteria:

- Admin KB document direct uploads still create upload intents, verify storage,
  mark requests complete, enqueue KB ingest, audit the upload, and dispatch the
  outbox worker.
- Conversation-file direct uploads still scope files to the owning athlete
  conversation, verify storage, mark requests complete, enqueue private ingest,
  and dispatch the outbox worker.
- Existing multipart upload behavior remains unchanged.
- Expired upload reconciliation still marks pending resources failed and cleans
  known objects without leaking signed URLs or raw storage metadata.
- New helper code has typed inputs and does not introduce HTTP concerns into
  repositories.

Relevant tests:

- `cd backend && uv run pytest tests/unit/test_direct_upload_workflows.py tests/unit/test_direct_upload_schemas.py -v`
- `cd backend && uv run pytest tests/integration/test_kb_document_routes.py -v`
- `cd backend && uv run pytest tests/integration/test_conversation_routes.py -v`
- `cd backend && uv run pytest tests/integration/test_upload_request_repositories.py -v`
- `cd backend && uv run pytest tests/integration/test_upload_request_reconciliation.py -v`
- `cd backend && uv run ruff check app tests`

Completed verification on 2026-06-18:

- `cd backend && uv run pytest tests/unit/test_direct_upload_workflows.py tests/unit/test_direct_upload_schemas.py tests/integration/test_kb_document_routes.py tests/integration/test_conversation_routes.py tests/integration/test_upload_request_repositories.py tests/integration/test_upload_request_reconciliation.py -v` -> 47 passed
- `cd backend && uv run ruff check app tests` -> passed
- `cd backend && uv run python -m compileall app tests` -> passed

Do not do yet:

- Do not split `ConversationService` public methods into route-visible services
  yet.
- Do not change direct-upload schemas or endpoint paths.
- Do not change storage key formats.

## Phase 3: Split KB Document Services

Scope:

- Separate admin document control-plane behavior from KB webhook processing.
- Preserve dependency aliases used by routes.
- Keep event and audit semantics unchanged.

Suggested files:

- `backend/app/services/kb_document_service.py`
- `backend/app/services/kb_documents/admin_document_service.py`
- `backend/app/services/kb_documents/upload_service.py`
- `backend/app/services/kb_documents/webhook_service.py`
- `backend/app/services/kb_documents/mappers.py`
- `backend/app/services/kb_documents/status_mapping.py`
- `backend/app/api/v1/dependencies.py`
- `backend/tests/integration/test_kb_document_routes.py`
- `backend/tests/integration/test_kb_webhook_routes.py`
- `backend/tests/unit/test_phase1_services.py`

Acceptance criteria:

- Existing imports of `KBDocumentService`, `KBDocumentUpload`, and
  `KBDocumentWebhookService` remain valid through a compatibility module.
- Admin list/get/upload/update/retry/delete route behavior is unchanged.
- Webhook signature verification, timestamp verification, source-type routing,
  status mapping, failure-reason redaction, summary mirroring, and chunk-count
  mirroring remain unchanged.
- Conversation-file webhooks still update only the matching conversation file
  and do not expose private file summaries through athlete-facing responses.

Relevant tests:

- `cd backend && uv run pytest tests/integration/test_kb_document_routes.py tests/integration/test_kb_webhook_routes.py -v`
- `cd backend && uv run pytest tests/unit/test_phase1_services.py -v`
- `cd backend && uv run ruff check app tests`

Do not do yet:

- Do not change KB webhook payload schemas.
- Do not change webhook auth settings.
- Do not remove compatibility imports until route dependencies and tests are
  updated.

## Phase 4: Split Conversation Services

Scope:

- Split athlete conversation orchestration by workflow: conversation history,
  message submission/stream authorization, and conversation-file lifecycle.
- Keep route dependency names stable while internals move behind focused
  services.
- Preserve Phase 2 worker and streaming contracts.

Suggested files:

- `backend/app/services/conversation_service.py`
- `backend/app/services/conversations/history_service.py`
- `backend/app/services/conversations/message_service.py`
- `backend/app/services/conversations/file_service.py`
- `backend/app/services/conversations/mappers.py`
- `backend/app/services/conversations/validation.py`
- `backend/app/api/v1/dependencies.py`
- `backend/app/api/v1/conversations.py`
- `backend/tests/integration/test_conversation_routes.py`
- `backend/tests/integration/test_athlete_chat_executor.py`

Acceptance criteria:

- Conversation list/create/detail responses are unchanged.
- Message submit still persists the user message, creates a streaming assistant
  placeholder, binds `task_id`, dispatches `RUN_ATHLETE_CHAT`, and returns the
  same stream metadata.
- Stream validation still checks athlete ownership, assistant role, conversation
  membership, and exact `task_id` binding.
- Conversation-file upload and direct-upload completion still preserve private
  conversation scope and KB ingest outbox behavior.
- DTO mappers remain explicit and do not return ORM models from services.

Relevant tests:

- `cd backend && uv run pytest tests/integration/test_conversation_routes.py -v`
- `cd backend && uv run pytest tests/integration/test_athlete_chat_executor.py -v`
- `cd backend && uv run pytest tests/integration/test_kb_ingest_outbox_worker.py -v`
- `cd backend && uv run ruff check app tests`

Do not do yet:

- Do not change follow-up message or streaming frontend behavior.
- Do not change worker payload fields.
- Do not change conversation-file visibility policy or trusted metadata.

## Phase 5: Split KB-Service Ingestion Service

Scope:

- Extract ingest metadata, source identity, S3 object inspection, pipeline
  dispatch, and status response helpers while preserving `IngestionService` as
  the route-facing facade.
- Keep heavy imports lazy where they currently avoid import-time coupling.

Suggested files:

- `kb-service/app/services/ingestion_service.py`
- `kb-service/app/services/ingestion/metadata.py`
- `kb-service/app/services/ingestion/source_identity.py`
- `kb-service/app/services/ingestion/s3_inspector.py`
- `kb-service/app/services/ingestion/pipeline_dispatcher.py`
- `kb-service/app/services/ingestion/status_mapper.py`
- `kb-service/tests/test_services/`
- `kb-service/tests/test_app/`

Acceptance criteria:

- `start_ingest()` still resolves configuration, validates trusted metadata,
  checks object size before hashing, dedupes by source identity/content, creates
  document/log rows, dispatches the Celery chain, and returns the same response.
- Admin uploads and conversation-file ingest requests keep distinct dedupe and
  trusted source identity rules.
- Task status and document status responses keep the same stage names and field
  values.
- Retry still deletes prior vectors, resets document status, ensures an
  ingestion log, and dispatches the pipeline.
- Delete still removes embeddings, deletes the document row, and best-effort
  deletes S3 object data off the event loop.

Relevant tests:

- `cd kb-service && uv run pytest tests/test_services -v`
- `cd kb-service && uv run pytest tests/test_app -v`
- `cd kb-service && uv run ruff check app tests`

Do not do yet:

- Do not change ingestion API contracts.
- Do not change Celery task names or pipeline order.
- Do not change MD5/dedupe behavior.

## Phase 6: Split Backend Repository Files Mechanically

Scope:

- Split files that already contain multiple focused repository classes.
- Keep package-level exports stable while callers migrate imports.
- Avoid business logic changes.

Suggested files:

- `backend/app/repositories/conversations.py`
- `backend/app/repositories/conversations/__init__.py`
- `backend/app/repositories/conversations/conversation_repo.py`
- `backend/app/repositories/conversations/message_repo.py`
- `backend/app/repositories/conversations/citation_repo.py`
- `backend/app/repositories/conversations/file_repo.py`
- `backend/app/repositories/uploads.py`
- `backend/app/repositories/uploads/__init__.py`
- `backend/app/repositories/uploads/upload_request_repo.py`
- `backend/app/repositories/uploads/kb_ingest_outbox_repo.py`
- `backend/tests/integration/test_conversation_repositories.py`
- `backend/tests/integration/test_upload_request_repositories.py`
- `backend/tests/integration/test_kb_ingest_outbox_repositories.py`

Acceptance criteria:

- Existing repository imports keep working through compatibility exports.
- Repository tests pass without SQL or behavior changes.
- No service behavior changes are bundled into this mechanical phase.
- Type hints and SQLAlchemy 2.0 `select()` usage are preserved.

Relevant tests:

- `cd backend && uv run pytest tests/integration/test_conversation_repositories.py -v`
- `cd backend && uv run pytest tests/integration/test_upload_request_repositories.py tests/integration/test_kb_ingest_outbox_repositories.py -v`
- `cd backend && uv run ruff check app tests`

Do not do yet:

- Do not combine this with service refactors.
- Do not change table models or migrations.
- Do not remove compatibility exports until all imports are migrated.

## Phase 7: Extract Outbox Source Handlers

Scope:

- Keep `KbIngestOutboxService` responsible for row locking, retry accounting,
  transaction boundaries, and drain summary.
- Move admin-upload and conversation-file resource handling into focused
  source handlers.

Suggested files:

- `backend/app/services/kb_ingest_outbox_service.py`
- `backend/app/services/kb_ingest_outbox/admin_upload_handler.py`
- `backend/app/services/kb_ingest_outbox/conversation_file_handler.py`
- `backend/app/services/kb_ingest_outbox/failure_policy.py`
- `backend/tests/integration/test_kb_ingest_outbox_worker.py`

Acceptance criteria:

- Durable outbox drain behavior is unchanged for admin uploads and conversation
  files.
- Retryable and terminal KB/storage errors preserve existing retry/failure
  outcomes.
- Resource mismatch and missing-resource cases do not count as provider dispatch
  attempts unless current behavior already does so.
- Failure metadata remains sanitized and bounded.

Relevant tests:

- `cd backend && uv run pytest tests/integration/test_kb_ingest_outbox_worker.py -v`
- `cd backend && uv run ruff check app tests`

Do not do yet:

- Do not change outbox database schema.
- Do not change retry settings or backoff policy.
- Do not change worker task scheduling.

## Phase 8: Optional Frontend Feature-Shell Cleanup

Scope:

- Split large frontend feature shells only after backend behavior is stable.
- Keep UI behavior, copy, API hooks, and route structure unchanged.

Suggested files:

- `frontend/src/components/features/admin/AdminKnowledgeBasePanel.tsx`
- `frontend/src/components/features/admin/AdminKBCollectionGrid.tsx`
- `frontend/src/components/features/admin/AdminKBCollectionDetail.tsx`
- `frontend/src/components/features/admin/AdminKBLocalUploadRow.tsx`
- `frontend/src/components/features/admin/kbFormatting.ts`
- `frontend/src/components/features/chat/ChatShell.tsx`
- `frontend/src/components/features/chat/useChatFileUploads.ts`
- `frontend/src/components/features/chat/conversationGrouping.ts`
- `frontend/src/components/features/chat/ChatShell.test.tsx`

Acceptance criteria:

- Admin KB panel still shows collection grid/detail views, upload progress,
  upload errors, retry actions, document rows, metadata drawer, and permission
  states unchanged.
- Chat shell still redirects by auth/profile state, groups conversations,
  supports local file attachment/upload, creates conversations, shows sources,
  and opens settings unchanged.
- Server state remains in TanStack Query hooks and UI state remains in Zustand.
- Feature component files should stay under 400 lines after splitting.

Relevant tests:

- `cd frontend && npm test -- AdminKnowledgeBasePanel ChatShell`
- `cd frontend && npm run lint`
- `cd frontend && npm run typecheck`

Do not do yet:

- Do not redesign UI.
- Do not add new frontend state libraries.
- Do not change API endpoint modules or DTO types.

## Cross-Phase Test Matrix

| Area | Required scenarios |
|------|--------------------|
| Import compatibility | Old import paths continue to work until explicitly removed in a later cleanup. |
| API contracts | Existing FastAPI route paths, request schemas, response schemas, and status codes remain unchanged. |
| Authorization | Athlete ownership, organization scope, admin role checks, and private conversation-file scope remain enforced. |
| KB retrieval | Semantic, lexical, hybrid, dedupe, source filters, and reranker fallback behavior remain unchanged. |
| Worker behavior | Celery task names, payload fields, Valkey stream events, retry/idempotency behavior, and terminal statuses remain unchanged. |
| Upload lifecycle | Presign, verify, complete, expire, cleanup, enqueue, retry, and failure states remain unchanged for admin and conversation uploads. |
| Webhooks | Signature verification, timestamp handling, source-type routing, status mapping, redaction, and mirror updates remain unchanged. |
| Failure handling | Retryable failures, terminal failures, sanitized messages, and bounded metadata remain unchanged. |
| Security/logging | No secrets, tokens, raw request bodies, raw document text, signed URLs, or large model inputs in logs. |
| Frontend state | Server state stays in TanStack Query; UI state stays in Zustand; components do not fetch directly. |
| Docs | Mark phases implemented only after code and tests prove completion. |

## Implementation Notes

- Start every coding phase with `git status -sb` and targeted `rg` import
  searches.
- For extraction phases, prefer this order:
  1. Add focused tests or lock existing behavior with targeted tests.
  2. Add new module with moved code.
  3. Re-export old names from the original module.
  4. Update internal imports.
  5. Run targeted tests.
  6. Run lint/type checks for the touched package.
- Keep compatibility modules small and remove them only in a separate cleanup
  after all imports have migrated.
- Use Context7 before library-specific coding changes involving SQLAlchemy,
  pgvector, PostgreSQL full-text search, FastAPI dependency behavior, Celery,
  TanStack Query, or Zustand.
- When a phase reveals real tech debt that is not resolved in that phase, add a
  concise entry to `backstage/development/tech-debt-tracker.md`.

## Explicit Non-Goals

- No unrelated refactors.
- No new dependencies.
- No schema migrations.
- No public API changes.
- No auth model changes.
- No storage key format changes.
- No search relevance changes.
- No frontend redesign.
- No removal of tests to make refactors pass.

## Open Follow-Ups

- Decide after Phase 6 whether compatibility exports should remain for external
  import stability or be removed in a final cleanup.
- Decide after Phase 8 whether frontend test files should be split further; the
  current largest frontend files are tests, not production components.
- Revisit this plan after the hybrid search/reranker work settles, because
  ongoing search changes may alter the safest order for Phase 1.
