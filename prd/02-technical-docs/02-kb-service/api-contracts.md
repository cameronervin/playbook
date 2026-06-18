# KB Service API Contracts

This document defines the service-to-service API contracts between the Playbook
main backend and the KB service.

Base URL is environment-configured, for example `http://kb-service:8001/api/kb`.
All non-health endpoints require service-to-service bearer authentication.

## Endpoint Summary

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/health` | Public liveness/readiness probe |
| POST | `/configuration/resolve` | Resolve or create the default Playbook KB configuration |
| POST | `/ingest/document` | Start ingestion for an admin-uploaded document |
| GET | `/status/documents/{document_id}` | Return KB-service document status |
| POST | `/documents/{document_id}/retry` | Retry ingestion for an existing KB-service document |
| DELETE | `/documents/{document_id}` | Delete/archive a KB-service document and its vectors |
| POST | `/search` | Search ready shared KB chunks and trusted conversation-file chunks when explicitly scoped |

The KB service exposes these semantic endpoints directly. Older scaffold route
names are not part of the supported contract.

## Resolve Default Configuration

```json
POST /api/kb/configuration/resolve
{}
```

The KB service owns one MVP default configuration. The endpoint creates
`Playbook KB Pipeline` with collection `playbook-kb` when missing, returns the
same row on repeated calls, and is safe for fresh local databases. Callers do
not need to provide a name or collection name.

## Start Ingestion

```json
POST /api/kb/ingest/document
{
  "source_type": "admin_upload",
  "organization_id": "uuid",
  "playbook_document_id": "uuid",
  "configuration_id": "uuid",
  "source_uri": "https://signed-url.example/doc.pdf",
  "filename": "nil-handbook.pdf",
  "content_type": "application/pdf",
  "size_bytes": 123456,
  "source_title": "NIL Handbook",
  "source_date": "2026-01-15",
  "visibility_policy": { "scope": "all_athletes" },
  "metadata_tags": {
    "topic": "nil",
    "source_type": "policy"
  },
  "status_webhook_url": "https://app.example/api/v1/kb/webhook"
}
```

`source_type` is backend-derived and currently accepts:

| Source type | Required identifiers | Visibility |
|-------------|----------------------|------------|
| `admin_upload` | `organization_id`, `playbook_document_id` | `visibility_policy.scope="all_athletes"` by default |
| `conversation_file` | `organization_id`, `conversation_id`, `conversation_file_id` | `visibility_policy.scope="conversation"` |

Conversation-file ingestion uses the same endpoint/worker pipeline, but the
backend sends conversation metadata only after validating the athlete owns the
conversation. Browser callers never send `source_type` directly to KB-service.

Response:

```json
{
  "kb_service_document_id": "uuid",
  "source_type": "admin_upload",
  "playbook_document_id": "uuid",
  "conversation_id": null,
  "conversation_file_id": null,
  "task_id": "celery-task-id",
  "status": "pending"
}
```

For `source_type="conversation_file"`, `playbook_document_id` is omitted/null
and `conversation_id` plus `conversation_file_id` identify the private source.
Phase 2 persists this trusted source identity in KB-service JSON metadata rather
than first-class columns; a later migration will backfill columns once private
retrieval and webhook contracts are stable.

Ingestion is idempotent by trusted source identity. Repeated admin-upload
requests with the same `organization_id`, `configuration_id`, and
`playbook_document_id` return the existing KB-service document instead of
creating or dispatching duplicate work. Repeated conversation-file requests with
the same `organization_id`, `configuration_id`, `conversation_id`, and
`conversation_file_id` do the same. Active duplicates return the existing
pipeline `task_id`; terminal duplicates return `task_id: null`. Failed
documents are not implicitly retried through ingest; callers must use the retry
endpoint. If identical content is submitted for a different trusted source
identity, KB-service returns `409` rather than replacing the existing document.

## Status Webhook

The KB service posts signed status events to the main backend. The main backend
uses these events to mirror status, summary, KB-service document linkage, and
safe count metadata into `kb_documents` for `admin_upload` and
`conversation_files` for `conversation_file`. Admin-upload events also append
`kb_document_events`.

```json
POST /api/v1/kb/webhook
{
  "document_id": "kb-service-document-uuid",
  "kb_service_document_id": "uuid",
  "source_type": "admin_upload",
  "playbook_document_id": "uuid",
  "conversation_id": null,
  "conversation_file_id": null,
  "stage": "embed",
  "status": "STARTED",
  "summary": "One- or two-sentence orientation summary on terminal success.",
  "message": null,
  "metadata": {
    "chunk_count": 42,
    "embedding_count": 20
  },
  "timestamp": 1780603200
}
```

For `source_type="conversation_file"`, `conversation_id` and
`conversation_file_id` are populated and `playbook_document_id` is omitted.
Webhook payloads must not include signed URLs, raw extracted text, model inputs,
or file contents.

`summary` is populated on terminal pipeline success once KB-service has
generated or fallen back to a canonical source orientation summary. It is not
answer evidence; final answers must cite retrieved chunks.

Required signature header:
- `X-KB-Signature`

The signature is an HMAC-SHA256 over the raw request body using a shared webhook
secret. When `timestamp` is present in the payload body, the main backend rejects
stale timestamps as well as invalid signatures.

## Search

```json
POST /api/kb/search
{
  "query": "Can I accept this NIL deal?",
  "organization_id": "uuid",
  "visibility_context": {
    "role": "athlete",
    "sport_team": "Basketball"
  },
  "source_types": ["admin_upload"],
  "limit": 10,
  "score_threshold": 0.7
}
```

If omitted, `source_types` defaults to `["admin_upload"]` so existing backend
shared-KB retrieval cannot accidentally include conversation-file chunks.
Frontend/browser callers never choose arbitrary KB-service `source_types`; the
backend derives trusted source scope before calling this service.
Search strategy is also internal server configuration. Callers do not send a
semantic/hybrid/rerank selector in the request body.

Private conversation-file retrieval requires trusted backend scope:

```json
{
  "query": "Does this contract require approval?",
  "organization_id": "uuid",
  "source_types": ["conversation_file"],
  "conversation_id": "uuid",
  "file_ids": ["uuid"],
  "limit": 10,
  "score_threshold": 0.7
}
```

Response:

```json
{
  "results": [
    {
      "document_id": "playbook-kb-document-uuid",
      "kb_service_document_id": "kb-document-uuid",
      "chunk_id": "chunk-uuid",
      "chunk_index": 3,
      "text": "Relevant chunk text...",
      "score": 0.82,
      "metadata": {
        "source_title": "NIL Handbook",
        "source_summary": "Short orientation summary for the source.",
        "source_date": "2026-01-15",
        "source_type": "admin_upload",
        "organization_id": "uuid",
        "source_locator": { "type": "page", "page_number": 3 },
        "visibility_policy": { "scope": "all_athletes" }
      }
    }
  ]
}
```

`score` is always the final retrieval score exposed to service callers. Default
runtime responses use semantic cosine similarity for `score`. When
`KB_SEARCH_STRATEGY=hybrid`, responses use reciprocal-rank-fusion
`hybrid_score` as `score` after semantic and lexical candidate merge. The Phase
2 reranker provider is internal infrastructure and does not add top-level
search response fields or run during Phase 3. Raw semantic, lexical, hybrid,
and future rerank diagnostics live inside `metadata` only. Reserved metadata
keys are
`semantic_score`, `semantic_rank`, `lexical_score`, `lexical_rank`,
`hybrid_score`, `rerank_score`, and `ranking_strategy`.

## Error Contract

```json
{
  "error": {
    "code": "string",
    "message": "string",
    "retryable": false
  }
}
```

Provider tokens, service secrets, signed URLs, and raw document contents must not
appear in error responses.
