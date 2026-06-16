# KB Service Architecture

This document maps the standalone KB service to Playbook MVP ingestion and
retrieval needs. The KB service owns parsing, chunking, embedding, vector
storage, status events, and semantic search for admin-uploaded department
documents.

Related KB-service PRD docs:
- [data-model.md](data-model.md)
- [api-contracts.md](api-contracts.md)
- [ingestion-pipeline.md](ingestion-pipeline.md)
- [retrieval.md](retrieval.md)
- [operations-security.md](operations-security.md)

## Service Boundary

Playbook main backend owns:
- user authentication and authorization,
- admin document records in `kb_documents`,
- original admin-uploaded file storage,
- audit events,
- chat orchestration and final answer generation.

KB service owns:
- ingestion jobs for admin-uploaded documents and trusted conversation files,
- parser/chunker/embedder execution,
- durable searchable chunk text and embeddings,
- ingestion lifecycle status,
- semantic search over ready shared KB documents and private conversation-file
  chunks when the backend supplies trusted private scope.

Athlete-uploaded conversation files are outside the shared admin KB corpus, but
they use the same KB-service parser/chunker/embedder/vector pipeline with
`source_type="conversation_file"` metadata. The main backend owns browser
authorization, original-file metadata, and athlete-visible status; KB-service
owns parsed chunks, vectors, and private retrieval filters.

## Implemented Contract

```text
POST /api/kb/configuration/resolve
  -> resolve or create the default Playbook KB configuration

POST /api/kb/ingest/document
  -> parse -> chunk -> embed -> pgvector

POST /api/kb/search
  -> query embedding -> pgvector cosine search -> ranked chunks
```

Stack:
- FastAPI on port 8001.
- Celery + Valkey workers.
- Docling and native Office/PDF parsers.
- S3-compatible staging.
- LiteLLM embeddings by default, with direct provider mode only for local or break-glass use.
- PostgreSQL + pgvector.

<!-- V2 CHANGE: Use the existing KB service as the retrieval layer for Playbook athlete chat and admin document ingestion. -->

## MVP Target Flow

```text
Admin upload
  -> main backend stores original file
  -> main backend creates kb_documents row
  -> main backend calls KB ingest with file URL + Playbook metadata
  -> KB service records kb.documents row
  -> Celery parses/chunks/embeds
  -> KB service stores chunk text + vectors in pgvector
  -> KB service posts signed status events back to main backend
  -> main backend marks kb_documents ready/failed
  -> chat retrieval calls KB search for ready chunks
```

## Required Adaptations

1. Support admin-uploaded local files by accepting a signed/presigned file URL and Playbook document metadata.
2. Preserve Playbook metadata tags in durable vector metadata.
3. Return source title, source date, visibility policy, document ID, and chunk ID with search results.
4. Exclude failed, deleted, archived, or unready documents from search.
5. Keep athlete conversation files separate from the shared KB corpus.
6. Surface parse/no-text/embed/load failures clearly for admin retry.
7. Send signed status events to the main backend for progress and terminal state updates.
8. Support idempotent retry/re-ingestion for a document without leaving stale vectors searchable.
9. Support deletion/archive so removed documents no longer appear in retrieval.

## Retrieval Metadata Contract

```json
{
  "document_id": "uuid",
  "chunk_id": "uuid",
  "source_title": "NIL Policy Handbook",
  "source_date": "2026-01-15",
  "visibility_policy": { "scope": "all_athletes" },
  "score": 0.82
}
```

The retrieval `document_id` is the Playbook `kb_documents.id` when supplied in
metadata. The KB service also keeps its own internal document ID; Playbook stores
that value in `kb_documents.kb_service_document_id` for status/debug linkage.

## Operational Notes

- Vector dimension is fixed by embedding model and migration.
- Changes to embedding model require migration planning.
- OCR/image handling is not MVP unless added separately.
- Existing service-to-service auth should remain in place.
- Heavy intermediate artifacts may be staged in S3-compatible storage, but durable search
  content lives in the KB service database.
- Staging artifacts should be deleted after successful load or terminal failure
  cleanup.
