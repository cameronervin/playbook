# Conversation File Upload Phased Build

## Purpose

This handoff breaks Phase 2 conversation file upload into small, independently
testable build phases. The target architecture keeps backend product ownership
separate from document-intelligence work:

- Backend owns auth, upload routes, conversation metadata, athlete-visible file
  status, chat orchestration, streaming, and citation persistence.
- KB-service owns parsing, chunking, embeddings, vector storage, summary
  generation, private retrieval, S3 staging, and ingestion retries.

The goal is to let coding agents pick up one phase at a time without having to
complete the whole upload + RAG system in one pass.

## Target Architecture

Public/backend APIs stay separate because they have different auth and product
semantics:

| Public backend endpoint | Backend-derived source type |
|-------------------------|-----------------------------|
| `POST /api/v1/admin/kb/documents` | `admin_upload` |
| `POST /api/v1/conversations/{conversation_id}/files` | `conversation_file` |

KB-service should use unified internal ingest and search capabilities, with
`source_type` provided only by the backend after authorization:

```json
{
  "source_type": "admin_upload",
  "organization_id": "uuid",
  "playbook_document_id": "uuid",
  "source_uri": "presigned-url",
  "filename": "nil-handbook.pdf"
}
```

```json
{
  "source_type": "conversation_file",
  "organization_id": "uuid",
  "conversation_id": "uuid",
  "conversation_file_id": "uuid",
  "source_uri": "presigned-url",
  "filename": "contract.pdf"
}
```

The frontend must never choose `source_type`. Browser callers hit role-scoped
backend endpoints; the backend derives the KB-service metadata from that route
and the authenticated principal.

Backend integration direction: Phase 1 uses a no-op conversation-file ingest
dispatcher as a temporary handoff point while the KB-service private ingest
contract is unfinished. Long-term, both admin document uploads and conversation
file uploads should call one backend KB integration seam, such as a generalized
`BaseKnowledgebaseProvider.ingest_source(KBIngestRequest)`, with the backend
deriving the trusted `source_type`. Public backend routes should remain separate
for auth and product semantics; only the internal KB-service ingest path should
converge. When that provider seam exists, the temporary dispatcher can be
removed unless the backend intentionally keeps it as an async/event abstraction.

## Data Model Direction

### Backend

Backend keeps durable product metadata:

- `kb_documents` for admin-managed shared KB document records.
- `conversation_files` for athlete-visible conversation attachments.
- `message_citations` for final answer citations.

Backend should mirror enough KB-service state for UI and chat orchestration:

- `kb_service_document_id`
- `summary`
- processing/extraction status
- chunk count
- sanitized failure reason

Long-term, backend `conversation_file_chunks` should be deprecated for the RAG
path. KB-service should be the canonical owner of chunk text and vectors for
both `admin_upload` and `conversation_file`.

### KB-Service

KB-service stores parsed/chunked/vectorized document content for both source
types. Retrieval must always filter by trusted metadata:

| Source type | Required retrieval filters |
|-------------|----------------------------|
| `admin_upload` | `organization_id`, `source_type=admin_upload`, visibility policy |
| `conversation_file` | `organization_id`, `source_type=conversation_file`, `conversation_id`, optional `file_ids` |

Conversation files must never appear in shared KB search results or another
conversation's retrieval results.

## Memory and Context Rules

- Do not pass whole large documents into agent prompts.
- Do not send raw extracted text through Redis/Celery broker payloads.
- Use S3-compatible object storage for originals, extracted/staged artifacts,
  and NDJSON staging.
- Use spooled temp files and streaming upload/download paths wherever large file
  content is handled.
- The agent receives retrieved snippets plus compact source summaries, not full
  documents.
- Summaries are orientation metadata, not evidence. Final answers must cite
  retrieved chunks.

## Summary Generation

KB-service should generate canonical source summaries for both `admin_upload`
and `conversation_file`.

Configuration:

| Setting | Default | Purpose |
|---------|---------|---------|
| `LITELLM_SUMMARY_MODEL` | `playbook-fast` | Lightweight summary model alias |
| `KB_SUMMARY_INPUT_MAX_TOKENS` | `3000` | Maximum text tokens sent to summary model |
| `KB_SUMMARY_MAX_OUTPUT_TOKENS` | `160` | Maximum generated summary tokens |

Summary behavior:

- Run after parse/chunk and before terminal ready status.
- Use a light LLM call through `playbook-fast`.
- Build input from filename/title, parser metadata, headings/early text, and
  representative chunks.
- If extracted content is longer than `KB_SUMMARY_INPUT_MAX_TOKENS`, truncate or
  sample deterministically with preference for useful headings, early content,
  and representative chunks.
- Produce a one- to two-sentence summary.
- If the LLM call fails, use a fallback summary from cleaned title plus the
  first meaningful non-boilerplate passage.
- Summary failure should not fail ingestion when parse/chunk/embed succeeded.

LiteLLM docs and virtual keys must be updated so KB-service can call
`playbook-fast` in addition to `playbook-embed` and, when enabled,
`playbook-ocr`.

## [IMPLEMENTED] Phase 0: Scaffolding and Contracts

Scope:

- Define KB-service `source_type` contract: `admin_upload | conversation_file`.
- Add schema notes for unified KB-service ingest/search and private retrieval
  filters.
- Add config placeholders for summary generation.
- Add test fakes for backend KB dispatch, signed status webhooks, retrieval, and
  summary output.

Suggested files:

- `prd/02-technical-docs/01-playbook/data-model.md`
- `prd/02-technical-docs/01-playbook/integration-spec.md`
- `prd/02-technical-docs/02-kb-service/api-contracts.md`
- `prd/02-technical-docs/02-kb-service/data-model.md`
- KB-service and backend schema/test fixtures as implementation begins.

Acceptance criteria:

- A coding agent can see the intended discriminated metadata contract.
- Tests can fake `admin_upload` and `conversation_file` ingest/search without
  real S3, LiteLLM, or Celery workers.
- No runtime behavior changes are required in this phase.

Do not do yet:

- Do not migrate production tables.
- Do not implement real parser or embedding behavior.
- Do not wire the athlete agent.

## [IMPLEMENTED] Phase 1: Backend Upload Metadata Slice

Scope:

- Add `POST /api/v1/conversations/{conversation_id}/files`.
- Validate current athlete owns the conversation.
- Validate filename, supported content type/extension, and size limits.
- Stream `UploadFile.file` to S3-compatible storage without reading the full
  file into memory.
- Create a `conversation_files` row with `uploaded` status.
- Dispatch a fake/no-op KB-service ingest request with `source_type=conversation_file`.

Implemented behavior:

- `POST /api/v1/conversations/{conversation_id}/files` accepts one multipart
  `UploadFile`, authorizes against the current athlete-owned conversation,
  validates filename, exact extension/content type, non-empty content, and
  `CONVERSATION_FILE_MAX_UPLOAD_MB` (`200` MB default).
- The backend streams `UploadFile.file` through the existing S3-compatible
  storage provider under `conversation-files/originals/...`, persists a safe
  `conversation_files` metadata row with `uploaded` status, and dispatches a
  no-op trusted `KBConversationFileIngestRequest` with
  `source_type="conversation_file"`.
- Responses and conversation detail include only `ConversationFileSummaryResponse`
  fields; storage keys, signed URLs, extracted text references, and raw content
  remain internal.

Acceptance criteria:

- Upload returns a safe `ConversationFileSummaryResponse`.
- Conversation detail shows the uploaded file.
- Response does not expose storage keys, presigned URLs, extracted text refs, or
  raw file content.
- Cross-athlete upload attempts return not found or forbidden according to
  existing conversation route patterns.

Do not do yet:

- Do not parse or chunk the file in backend.
- Do not expose download URLs.
- Do not let clients provide `source_type`.

## Phase 2: KB-Service Private Ingest Contract

Scope:

- Extend KB-service ingest request schemas to accept `source_type`.
- Require `playbook_document_id` for `admin_upload`.
- Require `conversation_id` and `conversation_file_id` for `conversation_file`.
- Persist trusted metadata into KB-service document/vector metadata.
- Ensure `visibility_policy.scope=conversation` for conversation files.
- Replace the Phase 1 no-op dispatcher with the generalized KB provider ingest
  seam once KB-service accepts both source types.

Acceptance criteria:

- KB-service can create distinct ingest records for `admin_upload` and
  `conversation_file`.
- Invalid source-type metadata is rejected before worker dispatch.
- Existing `admin_upload` behavior remains backward compatible or is migrated
  in one clearly documented contract change.

Do not do yet:

- Do not expose conversation-file records through shared KB document admin
  routes.
- Do not make KB-service responsible for end-user authorization.

## Phase 3: Real Parse, Chunk, and Embed

Scope:

- Reuse the existing KB-service parser router for PDF, DOCX, PPTX, and XLSX.
- Reuse token-aware chunking and embedding fan-out.
- Continue staging heavy page/chunk intermediates in S3 NDJSON.
- Store chunk text/vectors with `source_type` metadata.
- Preserve source locators such as page, slide, sheet, row range, or paragraph
  range when available.

Acceptance criteria:

- `admin_upload` and `conversation_file` documents use the same parser/chunker
  quality path.
- Conversation-file chunks are embedded and searchable only with private
  filters.
- Large documents do not travel through broker payloads or memory as a single
  bytes/text blob.

Do not do yet:

- Do not add semantic retrieval logic to the backend database.
- Do not duplicate KB-service parser dependencies in backend workers.

## Phase 4: Lightweight Summary Generation

Scope:

- Add a summary worker step to KB-service ingestion after parse/chunk.
- Use `LITELLM_SUMMARY_MODEL=playbook-fast`.
- Token-cap summary input at `KB_SUMMARY_INPUT_MAX_TOKENS`.
- Cap output at `KB_SUMMARY_MAX_OUTPUT_TOKENS`.
- Store summary as canonical KB-service derived metadata.
- Include summary in terminal status webhook payloads.

Acceptance criteria:

- Summary generation works for both `admin_upload` and `conversation_file`.
- Inputs longer than the cap are truncated or sampled deterministically.
- Summary failures fall back to extractive summary and do not block otherwise
  successful retrieval.
- Generated summaries are short enough to use as source orientation in prompts
  and UI.

Do not do yet:

- Do not treat summaries as answer evidence.
- Do not inject all document summaries into every agent call.

## Phase 5: Status and Summary Sync

Scope:

- Extend signed KB-service webhook payloads to include:
  - `source_type`
  - backend document/file ID
  - `kb_service_document_id`
  - processing status
  - chunk count
  - summary
  - sanitized failure reason
- Backend routes webhook updates to:
  - `kb_documents` for `source_type=admin_upload`
  - `conversation_files` for `source_type=conversation_file`

Acceptance criteria:

- Backend mirrors status and summary for both source types.
- Conversation history can show file status and summary without querying
  KB-service.
- Webhook signature verification still rejects invalid or stale events.

Do not do yet:

- Do not expose private conversation-file metadata through admin KB document
  lists.
- Do not log raw summary input, extracted text, signed URLs, or file contents.

## Phase 6: Private Retrieval

Scope:

- Extend KB-service search to accept `source_types`.
- Support one unified search implementation with strict filters:
  - `admin_upload`: shared org/visibility filters.
  - `conversation_file`: org + conversation + optional file IDs.
- Return citation-ready metadata:
  - `source_type`
  - Playbook document or conversation file ID
  - KB-service document ID
  - chunk ID/index
  - score
  - source title
  - source summary
  - locator metadata

Acceptance criteria:

- Shared KB search never returns `conversation_file` chunks.
- Conversation-file search cannot retrieve another conversation's files.
- Combined searches can return both source types only when backend passes the
  trusted private scope.

Do not do yet:

- Do not let frontend callers send arbitrary KB-service search filters.
- Do not rely on source summaries alone for answer grounding.

## Phase 7: Agent Context and Citations

Scope:

- Add backend provider methods that may call the same KB-service search endpoint:
  - `search_admin_uploads(...)`
  - `search_conversation_files(...)`
- Keep the methods separate in backend code for readability and leakage
  prevention.
- Add an athlete chat graph step that retrieves conversation-file context for
  attached or conversation-scoped ready files.
- Inject retrieved snippets plus compact source summaries into model context.
- Persist citations with `source_type=admin_upload` or
  `source_type=conversation_file`.

Acceptance criteria:

- Agent answers can cite uploaded conversation files.
- Mixed KB/file answers persist correct citation metadata.
- The agent never receives whole large documents by default.
- Unsupported policy/process behavior still refuses when no adequate source
  supports the answer.

Do not do yet:

- Do not let uploaded file context override safety/refusal policy.
- Do not cite a summary as if it were the supporting chunk.

## Phase 8: Hardening and Documentation

Scope:

- Add no-text, failed-ingest, retry, stuck-task, and storage-failure coverage.
- Add logging redaction checks for source URIs, file text, model inputs, and
  secrets.
- Add local smoke coverage for:
  - admin upload ingest/search
  - conversation file ingest/search
  - athlete chat with mixed source citations
- Update PRD/data-model/API/integration docs after implementation.
- Update LiteLLM docs and env examples for `LITELLM_SUMMARY_MODEL`.

Acceptance criteria:

- Backend and KB-service tests pass.
- Lint passes for touched services.
- Docs clearly describe which source types are searchable in which contexts.
- Known limitations are tracked in `docs/development/tech-debt-tracker.md` if
  any shortcuts remain.

Do not do yet:

- Do not add broad frontend upload UI in this backend/RAG build unless a later
  phase explicitly takes it on.

## Test Matrix

| Area | Required scenarios |
|------|--------------------|
| Backend upload | Ownership, validation, S3 streaming, safe response shape |
| Backend webhooks | Status/summary mirroring for both source types |
| KB ingest | Valid/invalid metadata for `admin_upload` and `conversation_file` |
| KB memory path | Spooled temp files and S3 NDJSON staging for large artifacts |
| KB summary | Fast-model call, token truncation, fallback, non-blocking failure |
| KB retrieval | Source-type filters, private conversation scope, no cross-corpus leaks |
| Agent | Snippet injection, mixed citations, no full-document prompt injection |

## Implementation Defaults

| Setting | Default |
|---------|---------|
| `source_type` values | `admin_upload`, `conversation_file` |
| `LITELLM_SUMMARY_MODEL` | `playbook-fast` |
| `KB_SUMMARY_INPUT_MAX_TOKENS` | `3000` |
| `KB_SUMMARY_MAX_OUTPUT_TOKENS` | `160` |
| Conversation-file visibility | `visibility_policy.scope=conversation` |

## Open Follow-Ups

- Decide whether `conversation_file_chunks` remains temporarily for compatibility
  during migration or is removed in the same schema migration that introduces
  KB-service private retrieval.
- Decide retention policy for original conversation files and extracted
  artifacts.
- Decide whether backend mirrors only terminal summaries or all in-progress
  parser quality metadata.
- Decide whether the dispatcher remains as an async/event abstraction or is
  removed once `BaseKnowledgebaseProvider` owns unified ingestion.
