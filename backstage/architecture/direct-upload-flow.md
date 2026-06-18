# Direct Upload Flow

This document describes the implemented direct-upload path for admin KB
documents and athlete conversation files. Browser clients do not send file bytes
through FastAPI in the normal upload path; they request a backend-authorized
upload contract, POST the file directly to S3-compatible storage, and then ask
the backend to verify and enqueue ingestion.

## Public Contract

Both upload surfaces use the same lifecycle with separate routes and auth
semantics:

```text
Browser -> Backend intent route -> S3/MinIO presigned POST
Browser -> S3/MinIO multipart form POST
Browser -> Backend upload-complete route
Backend -> storage HEAD verification
Backend -> kb_ingest_outbox row
Backend worker -> KB-service ingest
KB-service -> signed backend webhook
Backend -> mirrored ready/failed status
```

The `upload` contract returned from intent routes contains
`upload_request_id`, `method="POST"`, `url`, required form `fields`, and
`expires_at`. Normal document/conversation responses after intent creation do
not expose storage keys, source URIs, presigned URLs, or signed download URLs.

## Admin Document Flow

```text
Admin browser
  |
  | POST /api/v1/admin/kb/documents
  | JSON: filename, content_type, size_bytes, title/tags/source_date
  v
FastAPI backend
  | authorize admin
  | validate metadata
  | create kb_documents(upload_pending)
  | create upload_requests(pending, source_type=admin_upload)
  v
S3-compatible storage
  ^
  | presigned POST contract
  |
Admin browser
  |
  | multipart form POST to contract.url with contract.fields + file
  v
S3-compatible storage
  |
  | browser upload succeeds
  v
Admin browser
  |
  | POST /api/v1/admin/kb/documents/{document_id}/upload-complete
  | JSON: upload_request_id
  v
FastAPI backend
  | lock scoped upload_requests row
  | storage HEAD verifies key, size, content type
  | mark upload_requests(completed)
  | mark kb_documents(uploaded)
  | enqueue kb_ingest_outbox(admin_upload)
  v
backend-files worker
  | signs short-lived source URL
  | derives trusted source_type=admin_upload
  | calls BaseKnowledgebaseProvider.ingest_source(...)
  v
KB-service
  | parse -> chunk -> summarize -> embed -> vector load
  | POST /api/v1/kb/webhook with signed status
  v
FastAPI backend
  | mirror processing/ready/failed, summary, chunk_count
  v
Admin document UI
```

## Conversation File Flow

```text
Athlete browser
  |
  | POST /api/v1/conversations/{conversation_id}/files
  | JSON: filename, content_type, size_bytes, optional message_id
  v
FastAPI backend
  | authorize athlete owns conversation
  | validate file type/size/message scope
  | create conversation_files(upload_pending)
  | create upload_requests(pending, source_type=conversation_file)
  v
S3-compatible storage
  ^
  | presigned POST contract
  |
Athlete browser
  |
  | multipart form POST to contract.url with contract.fields + file
  v
S3-compatible storage
  |
  | browser upload succeeds
  v
Athlete browser
  |
  | POST /api/v1/conversations/{conversation_id}/files/{file_id}/upload-complete
  | JSON: upload_request_id
  v
FastAPI backend
  | lock scoped upload_requests row
  | storage HEAD verifies key, size, content type
  | mark upload_requests(completed)
  | mark conversation_files(uploaded)
  | enqueue kb_ingest_outbox(conversation_file)
  v
backend-files worker
  | signs short-lived source URL
  | derives trusted source_type=conversation_file
  | sends organization_id, conversation_id, conversation_file_id
  v
KB-service
  | parse -> chunk -> summarize -> embed -> vector load
  | private retrieval scope is conversation_id + optional file_ids
  | default shared search excludes conversation_file sources
  | POST /api/v1/kb/webhook with signed status
  v
FastAPI backend
  | mirror extracting/ready/failed, summary, chunk_count
  v
Athlete chat UI and agent private retrieval
```

## Failure And Retry Paths

```text
Storage POST fails
  -> browser keeps a local failed upload row
  -> backend resource remains upload_pending until expiry
  -> backend-maintenance reconciliation marks it failed after expires_at

Upload-complete before object exists
  -> backend storage HEAD returns missing
  -> backend returns validation error
  -> resource remains upload_pending until successful complete or expiry

Upload-complete metadata mismatch
  -> backend storage HEAD detects size/content-type mismatch
  -> backend returns validation error
  -> resource remains upload_pending until expiry/retry with a new intent

Duplicate upload-complete
  -> backend sees upload_requests(completed)
  -> idempotently enqueues or returns existing outbox/resource state
  -> unique outbox constraints prevent duplicate ingest rows

Expired pending upload
  -> backend-maintenance worker locks expired pending upload_requests
  -> still-pending resources move to failed with a safe reason
  -> known intent objects are deleted only when tied to that expired request

KB-service unavailable during ingest handoff
  -> backend-files worker records retryable outbox failure
  -> next_attempt_at schedules another drain
  -> accepted uploads do not require browser re-upload
```

## Operational Notes

- Local browser uploads require a successful MinIO preflight response for the
  frontend origin and `S3_PUBLIC_ENDPOINT_URL=http://localhost:9000` when the
  backend runs in Docker.
- The backend worker must listen on both `backend-files` and
  `backend-maintenance` for outbox draining and expired intent reconciliation.
- KB-service remains the owner of parsing, chunking, embeddings, summaries,
  vector storage, and private conversation-file retrieval filters.
- Browsers never choose `source_type` or KB-service ingest metadata.
