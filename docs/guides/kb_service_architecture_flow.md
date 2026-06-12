# KB Service Architecture Flow

This guide is a concise map of how `kb-service` routes requests, parses
documents, stores vectors, and serves retrieval.

## Service Boundary

```text
+-------------------+        HTTP         +----------------------+
| Playbook backend  | ------------------> | kb-service FastAPI   |
|                   |                     | /api/kb/*            |
| - auth/users      |                     | - ingest status      |
| - admin records   |                     | - parse/chunk/embed  |
| - chat answers    |                     | - pgvector search    |
+-------------------+                     +----------+-----------+
                                                     |
                          +--------------------------+-------------------+
                          |                          |                   |
                          v                          v                   v
                    +-----------+              +------------+      +-------------+
                    | Postgres  |              | S3/MinIO   |      | Celery      |
                    | pgvector  |              | staging    |      | Valkey      |
                    +-----------+              +------------+      +-------------+
```

The backend calls `kb-service` through
`backend/app/infrastructure/knowledgebase/providers/local_kb.py`.
The KB service owns the searchable corpus for admin-uploaded KB documents only.
Athlete conversation files stay in the main backend.

## API Routing

```text
app/main.py
  -> include_router(api_router, prefix="/api/kb")

app/api/router.py
  -> /health                  no service auth
  -> /configuration/*         bearer service auth
  -> /ingest/*                bearer service auth
  -> /status/*                bearer service auth
  -> /search                  bearer service auth
  -> /documents/*             bearer service auth
```

Key routes:

```text
POST /api/kb/configuration/resolve
  -> ConfigurationService.resolve()

POST /api/kb/ingest/document
  -> IngestionService.start_ingest()

POST /api/kb/search
  -> SearchService.search()
```

## Ingestion Flow

```text
POST /api/kb/ingest/document
  |
  v
IngestionService.start_ingest()
  -> resolve configuration
  -> validate trusted metadata
  -> extract S3 key
  -> HEAD object for size guard
  -> stream object to compute MD5
  -> create kb.documents row
  -> create kb.ingestion_logs row
  -> dispatch Celery chain
```

The dispatched chain is defined in
`kb-service/app/services/ingestion_service.py`:

```python
pipeline = parse_task.s(...) | chunk_task.s(...) | embed_task.s(...)
result = pipeline.apply_async()
```

Worker flow:

```text
parse_task
  -> stream original S3 object to tempfile
  -> ParserRouter.route_path()
  -> stage page text to S3 as pages.ndjson

chunk_task
  -> stream pages.ndjson
  -> iter_chunks_from_pages()
  -> stage chunks to S3 as chunks.ndjson

embed_task
  -> delete stale vectors for document
  -> plan chunk windows
  -> group(embed_batch_task...)
  -> schedule fallback load_vector_task

embed_batch_task
  -> load one chunk slice from S3
  -> embed text with worker_state.embed_client
  -> VectorRepository.insert_batch_embeddings()
  -> increment Redis progress counter
  -> last batch dispatches load_vector_task

load_vector_task
  -> count staged chunks
  -> count persisted vectors
  -> reissue missing chunk batches if needed
  -> mark document success
  -> delete S3 staging
```

## Parser Routing

`parse_task()` calls `ParserRouter.route_path()`:

```python
outcome = await router.route_path(
    path=tmp_path,
    filename=filename,
    s3_bucket=settings.S3_BUCKET_NAME,
    s3_key=s3_key,
)
```

`ParseOutcome` is the parser contract:

```python
@dataclass(frozen=True)
class ParseOutcome:
    text_segments: list[str]
    artifacts: ParseArtifacts
    selected_parser: str
    route: str
    reason_codes: list[str]
    quality_signals: dict[str, Any]
    warnings: list[str]
```

Parser decision tree:

```text
ParserRouter.route_path()
  |
  +-- PDF
  |     -> PDFRouter.route_path()
  |     -> ComplexityAssessor.assess()
  |          low    -> NativePDFParser
  |          medium -> DoclingPDFParser if enabled, fallback native
  |          high   -> OCR provider if available, fallback native
  |
  +-- DOCX/PPTX with docling routing enabled
  |     -> OfficeRouter.route_path()
  |     -> ComplexityAssessor.assess()
  |          low    -> native parser
  |          medium -> Docling parser, fallback native
  |
  +-- XLS/XLSX or simple file
        -> parser from PARSER_DISPATCH
```

Registry loading:

```text
ParserRouter.__init__()
  -> load_parser_registry()
       -> import docx, excel, pdf_native, pptx extractors
       -> each module registers PARSER_DISPATCH[mime] = ParserClass
```

Native extractors:

```text
NativePDFParser       -> PyMuPDF, one text segment per non-empty page
NativeDOCXParser      -> python-docx, joined non-empty paragraphs
PptxParser            -> python-pptx, one text block per slide
ExcelParser           -> openpyxl, one text block per worksheet
Docling*Parser        -> structured text plus tables, figures, layout blocks
```

## Retrieval Flow

Backend chat retrieval enters through `LocalKBProvider.search()`:

```text
LocalKBProvider.search()
  -> POST /api/kb/search
```

KB service search:

```text
SearchService.search()
  -> ConfigurationService.resolve()
  -> build visibility metadata filter
  -> embed query
  -> AsyncVectorRepository.search()
  -> map rows into SearchResult
```

The pgvector query filters before ranking:

```text
collection_id matches resolved config
AND kb.documents.status = 'success'
AND vector metadata contains organization_id
AND vector metadata contains visibility_policy
AND cosine score >= threshold
ORDER BY cosine distance ASC
LIMIT request.limit
```

Current ranking is vector-similarity first from KB-service, then the backend
keeps semantic relevance bands and prefers newer `source_date` within
near-similar matches. Admin-uploaded shared KB documents are official by
definition for MVP, and priority is not used as a ranking control.
