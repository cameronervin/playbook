# KB Service Data Model

This document defines the KB service-owned data model for Playbook MVP document
ingestion and retrieval.

## Ownership

The KB service owns the `kb` PostgreSQL schema. Playbook's main backend may
reference KB-service identifiers, but it should not write KB-service tables
directly. All coordination happens through authenticated KB service APIs and
signed status webhooks.

## Durable Content Locations

| Content | Durable Location | Notes |
|---------|------------------|-------|
| Original admin-uploaded binary | Main backend blob storage | Referenced by `kb_documents.storage_key`; KB service reads via signed/presigned URL |
| Original conversation-file binary | Main backend blob storage | Referenced by `conversation_files.storage_key`; KB service reads via signed/presigned URL after backend authorization |
| Parsed text-segment records | Temporary KB staging storage | NDJSON staging used between parse/chunk tasks; includes text plus source locators and is deleted after terminal cleanup |
| Chunk text | `kb.langchain_pg_embedding.document` or equivalent text column | Durable retrieval text returned in search results |
| Embedding vectors | `kb.langchain_pg_embedding.embedding` | `vector(1536)` for the `playbook-embed` LiteLLM alias |
| Chunk metadata | `kb.langchain_pg_embedding.cmetadata` | Includes Playbook document ID, source fields, visibility policy, and chunk locator |
| Ingestion lifecycle | `kb.documents`, `kb.ingestion_logs` | KB service internal source of truth |

## Tables

### `kb.configurations`

Stores parse, chunk, embedding, and vectorstore configuration for a collection.

Required MVP fields:
- `id`
- `name`
- `parser_config`
- `chunk_config`
- `embedding_config`
- `vectorstore_config`
- `collection_name`
- `created_at`
- `updated_at`

MVP uses one default Playbook configuration unless environment-specific tuning is
needed.

### `kb.documents`

One row per KB-service ingestion document.

Current persisted fields:
- `id`
- `configuration_id`
- `name` / filename
- `s3_key`
- `md5` dedupe hash
- `status`
- `metadata`
- `created_at`
- `updated_at`

Phase 2 stores `source_type`, `playbook_document_id`, `conversation_id`,
`conversation_file_id`, `content_type`, `size_bytes`, and related source fields
inside `metadata` JSON rather than first-class columns. `source_uri` and signed
URLs are not persisted. Admin uploads keep the historical raw content MD5 dedupe
value; conversation files use a scoped 32-character dedupe hash so identical
private and shared files remain distinct. The raw content MD5 is retained in
safe metadata for a later column/backfill migration.

`source_type` is `admin_upload` or `conversation_file`. For `admin_upload`, the
metadata `playbook_document_id` maps to main backend `kb_documents.id`, and
search responses must prefer this identifier as the external `document_id`. For
`conversation_file`, metadata `conversation_id` and `conversation_file_id` map
to backend conversation metadata and are required for private retrieval filters.

Allowed statuses:
- `pending`
- `parsing`
- `chunking`
- `embedding`
- `loading`
- `success`
- `failed`
- `deleted`

### `kb.ingestion_logs`

Tracks task IDs, per-stage status, timestamps, and errors for ingestion.

Required MVP stages:
- `parse`
- `chunk`
- `embed`
- `load_vector`
- `pipeline`

Status values:
- `PENDING`
- `STARTED`
- `SUCCESS`
- `FAILURE`
- `REVOKED`

### `kb.langchain_pg_collection`

Collection registry used by the vector store. MVP should use one collection for
Playbook shared department documents unless multi-tenant isolation requires
separate collections later.

### `kb.langchain_pg_embedding`

Stores durable searchable chunks and embeddings.

Required MVP fields:
- `uuid`
- `collection_id`
- `embedding`
- `document`
- `cmetadata`

Required `cmetadata` keys:
- `organization_id`
- `source_type`
- `playbook_document_id`
- `conversation_id`
- `conversation_file_id`
- `kb_document_id`
- `chunk_id`
- `chunk_index`
- `source_title`
- `source_date`
- `is_official` (internal compatibility; normalized true for new MVP ingest)
- `priority` (internal compatibility; normalized 0 for new MVP ingest)
- `visibility_policy`
- `metadata_tags`
- `content_type`
- `source_locator`

For `admin_upload` vectors, `conversation_id` and `conversation_file_id` are
omitted. For `conversation_file` vectors, `playbook_document_id` is omitted and
`visibility_policy.scope` must be `conversation`. Shared KB search must filter
to `source_type="admin_upload"`; private file search must filter to
`source_type="conversation_file"`, `organization_id`, and `conversation_id`.
Phase 3 preserves source locators in `cmetadata.source_locator`, with file-type
specific hints such as page number, slide number, sheet and row range,
paragraph range, or Docling layout block.

The `document` text and `embedding` vector are the durable retrieval payload.
Temporary pages/chunks staged in S3 are implementation artifacts, not the long-term
source for search.

## Deletion and Retry

Retrying an ingestion must remove stale embeddings for the affected
`playbook_document_id` or `kb_document_id` before new chunks become searchable.
Deleting or archiving a document must make existing embeddings ineligible for
search, either by deleting them or marking metadata/status so the search filter
excludes them.
