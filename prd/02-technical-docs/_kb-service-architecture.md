# KB Service Architecture

This document maps the existing reusable KB service to Playbook MVP needs.

## Existing Service

The scaffold includes `kb-service/`, a standalone FastAPI microservice for document ingestion and retrieval:

```text
POST /api/kb/ingest/url -> parse -> chunk -> embed -> pgvector
POST /api/kb/embed/search -> query embedding -> pgvector cosine search -> ranked chunks
```

Stack:
- FastAPI on port 8001.
- Celery + Valkey workers.
- Docling and native Office/PDF parsers.
- S3/LocalStack staging.
- OpenAI or LiteLLM gateway embeddings.
- PostgreSQL + pgvector.

## Playbook Use

<!-- V2 CHANGE: Use the existing KB service as the retrieval layer for Playbook athlete chat and admin document ingestion. -->

Playbook should use the KB service for:
- admin-uploaded department document parsing,
- chunking and embedding,
- semantic search for athlete questions,
- source metadata return for citations,
- ingestion status tracking.

## Required Adaptations

1. Support admin-uploaded local files, not only URL ingestion.
2. Preserve Playbook metadata tags in vector metadata.
3. Return source title, source date, official flag, priority, and document ID with search results.
4. Exclude failed/unready documents from search.
5. Keep athlete conversation files separate from the shared KB corpus.
6. Surface parse/no-text failures clearly for admin retry.

## Retrieval Metadata Contract

```json
{
  "document_id": "uuid",
  "chunk_id": "uuid",
  "source_title": "NIL Policy Handbook",
  "source_date": "2026-01-15",
  "is_official": true,
  "priority": 10,
  "visibility_policy": { "scope": "all_athletes" },
  "score": 0.82
}
```

## Operational Notes

- Vector dimension is fixed by embedding model and migration.
- Changes to embedding model require migration planning.
- OCR/image handling is not MVP unless added separately.
- Existing service-to-service auth should remain in place.
