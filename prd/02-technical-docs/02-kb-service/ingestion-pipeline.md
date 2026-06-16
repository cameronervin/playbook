# KB Service Ingestion Pipeline

This document defines MVP ingestion behavior for admin-uploaded Playbook KB
documents and trusted conversation-scoped files.

## Pipeline Stages

```text
ingest request
  -> validate source URL and metadata
  -> create kb.documents row
  -> parse original file
  -> stage text-segment records
  -> chunk text records
  -> stage chunks
  -> summarize source
  -> embed chunks
  -> write chunk text + vectors
  -> verify vector count
  -> mark success
  -> notify main backend
```

## Stage Requirements

### Validate

- Verify service auth.
- Verify required Playbook metadata is present.
- Verify file size/content type are within configured limits.
- Use signed/presigned source URLs without logging the full URL.
- Return a structured retryable error when the source cannot be fetched.

### Parse

- Support MVP file types: PDF, DOCX, PPTX, XLSX.
- Use Docling/native parsers from the existing scaffold.
- Produce page/sheet/slide/paragraph-aware text records when possible.
- Fail with `NO_TEXT_EXTRACTED` when a file has no usable text.
- Scanned PDF OCR is available only when explicitly enabled through the
  LiteLLM-routed VLM provider; standalone image extraction remains out of MVP.

### Chunk

- Use deterministic token-aware chunking.
- Preserve chunk order with zero-based `chunk_index`.
- Preserve source locators such as page number, slide number, sheet name, row
  range, paragraph range, or Docling layout block.
- Store chunk metadata needed for citations and conflict ranking.

### Summarize

- Build summary input from safe source metadata, parser telemetry, and
  deterministic representative chunks from staged `chunks.ndjson`.
- Use the LiteLLM-routed `playbook-fast` alias from `LITELLM_SUMMARY_MODEL`.
- Cap input with `KB_SUMMARY_INPUT_MAX_TOKENS` and output with
  `KB_SUMMARY_MAX_OUTPUT_TOKENS`.
- Persist the canonical one- to two-sentence summary in `kb.documents.summary`.
- If model generation fails, use an extractive fallback and continue ingestion.
- Do not log raw summary inputs, model prompts, signed URLs, or file contents.

### Embed

- Embed each chunk with the configured embedding provider.
- Default embedding alias is `playbook-embed`; LiteLLM owns the provider model mapping.
- Vector dimension is 1536 and changing it requires migration planning.
- Embedding failures should be retryable where provider errors are transient.

### Load Vector

- Write durable chunk text and vectors to `kb.langchain_pg_embedding`.
- Verify stored vector count matches staged chunk count.
- Delete or overwrite stale vectors for the document before retry/re-ingestion.
- Mark the KB document `success` only after vectors are searchable.

### Cleanup

- Delete temporary page/chunk staging artifacts after successful load.
- Retain enough ingestion logs and error messages for admin troubleshooting.
- Do not retain signed source URLs after they are no longer needed.

## Status Mapping

| KB Service Status | Main Backend `kb_documents.processing_status` |
|-------------------|-----------------------------------------------|
| `pending` | `uploaded` |
| `parsing` | `processing` |
| `chunking` | `processing` |
| `embedding` | `processing` |
| `loading` | `processing` |
| `success` | `ready` |
| `failed` | `failed` |
| `deleted` | `failed` or archived/deleted state if added |

## Retry Behavior

Admin retry in Playbook should call the KB service retry endpoint. Retry must:

1. create a new ingestion attempt or reset the existing attempt,
2. remove stale vectors for the document before new vectors are searchable,
3. preserve the same `playbook_document_id`,
4. emit status events for each stage,
5. end in `success` or `failed` with a clear reason.

## Deletion and Archive

When a Playbook KB document is deleted or archived:

1. main backend records an audit event,
2. main backend calls KB service delete/archive,
3. KB service removes vectors or marks them unsearchable,
4. KB search excludes the document immediately after successful deletion/archive.

## Non-Goals

- Athlete conversation file ingestion into the shared admin KB corpus.
- Provider API actions in external athletic systems.
- Standalone OCR for image-only documents unless separately scoped.
- Cross-organization document sharing.
