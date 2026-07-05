# KB Service Extension Points

This guide describes the KB service's RAG infrastructure layer. It keeps provider-specific
behavior behind small extension points so the service compiles and runs with a
minimal dependency set. This document explains those extension points and how
to configure the implemented provider paths.

---

## 1. Parser layer

### The Protocols + explicit extractor catalog

Routing-facing extractors return `ParseOutcome`. Native text-only extractors
can still keep their `parse(file, filename) -> list[str]` compatibility method,
but they expose `parse_outcome_path(...)` for the router.

- `ITextParser` — compatibility protocol for native `parse*` methods.
- `IOutcomeParser` — routing-facing `parse_outcome_path(...) -> ParseOutcome`.
- `IStructuredParser` — legacy compatibility for structured parsers that expose
  `parse_structured*`; new structured extractors should prefer
  `parse_outcome_path(...)`.

`parsers/routing/catalog.py` owns the explicit MIME -> extractor candidate map.
There is no import-time parser registration; `ParserRouter` builds its default
catalog directly. Docling uses one `DoclingParser` configured with a
`DoclingParserSpec`; the catalog binds each supported MIME type to the matching
spec.
Native extractor modules are file-type named (`pdf.py`, `docx.py`, `pptx.py`,
`excel.py`) while native classes stay explicit (`NativePDFParser`,
`NativeDOCXParser`, `NativePPTXParser`, `NativeExcelParser`).

### Adding a new extractor

1. Create `parsers/extractors/<name>.py`.
2. Implement a class with `parse_outcome_path(path, filename) -> ParseOutcome`
   or a native text parser plus a wrapper method.
3. Import any heavy library **lazily inside the method** (so the module compiles
   without it installed).
4. Add an `ExtractorCandidate` for the MIME type in
   `parsers/routing/catalog.py`.

### Unified complexity routing

`parsers/routing/complexity.py::ComplexityAssessor` classifies a document
deterministically (no model calls) using the `settings.*THRESHOLD*` values:

| Category | Parser | Module |
|----------|--------|--------|
| `low`    | native extractor (fast, light) | `extractors/pdf.py`, `docx.py`, `pptx.py`, `excel.py` |
| `medium` | Docling (structured extraction) | `extractors/docling.py` |
| `high`   | OCR provider (scanned / image-dominant) | `providers/ocr.py` / `providers/vlm.py` |

`parsers/routing/router.py::ParserRouter` is the single orchestrator:
resolve MIME -> assess complexity -> build ordered candidates -> return the
first usable `ParseOutcome`.

### What changed vs the source service

- **`unstructured` was dropped.** The low-complexity local PDF path now uses
  `NativePDFParser` (PyMuPDF / `fitz`), which simply returns
  `[page.get_text() for page in doc]`. See `extractors/pdf.py`.
- **The `image/` route was dropped** from `ParserRouter`, along with
  `routing/image.py`. Standalone image OCR is outside the shared KB MVP.
- **PDFRouter and OfficeRouter were removed.** Their complexity-specific
  behavior now lives in `ParserRouter` plus the explicit extractor catalog.
- The native DOCX parser class was renamed `UnstructuredDOCXParser` ->
  `NativeDOCXParser` (it never used `unstructured`; the name was misleading).

---

## 2. OCR provider

`parsers/providers/ocr.py` defines:

- `OCRProvider = Literal["none", "textract", "vlm"]`
- `BaseOCRProvider` (Protocol) — `parse_pdf_high_complexity(...) -> ParseOutcome | None`
  and `parse_image_s3(...) -> ParseOutcome`.
- `NullOCRProvider` — the default (`OCR_PROVIDER="none"`):
  - `parse_pdf_high_complexity` returns `None` → `ParserRouter` falls back to
    native text extraction (`ocr_unavailable`, then `fallback_native`). Scanned PDFs
    degrade gracefully instead of hard-failing.
  - `parse_image_s3` raises `UnsupportedFileTypeError` — standalone image OCR is
    not part of the shared KB parser route.
- `VLMOCRProvider` — opt-in (`OCR_PROVIDER="vlm"`):
  - rasterises high-complexity PDF pages with PyMuPDF,
  - sends page PNG data URLs to a LiteLLM OpenAI-compatible chat completion
    endpoint using `LITELLM_VLM_MODEL`,
  - returns a normal `ParseOutcome` with page text and OCR telemetry,
  - returns `None` when all OCR page outputs are blank/no-text sentinels so the
    router can keep its existing fallback behavior.
- `build_ocr_provider(provider=None)` — factory keyed off `settings.OCR_PROVIDER`.
  Returns `NullOCRProvider()` for `"none"` and `VLMOCRProvider()` for `"vlm"`.
  `textract` intentionally remains unsupported for Playbook.

### Enabling scanned PDF OCR

Set:

```env
OCR_PROVIDER=vlm
LITELLM_BASE_URL=http://litellm:4000
LITELLM_API_KEY=...
LITELLM_VLM_MODEL=playbook-ocr
```

Optional tuning:

```env
VLM_OCR_DPI=150
VLM_OCR_DETAIL=high
VLM_OCR_MAX_PAGES=50
VLM_OCR_REQUEST_TIMEOUT_SECONDS=120.0
```

LiteLLM owns the actual provider/model mapping behind the `playbook-ocr` alias.
The KB service must not store provider-specific vision API keys.

### Adding another OCR provider

1. Implement a class satisfying `BaseOCRProvider` (set `provider = "textract"`
   or another supported literal). Put it under `parsers/providers/`.
2. Return it from `build_ocr_provider()` for the matching `OCR_PROVIDER` value
   (replace the `NotImplementedError` branch only if the provider is a product-approved path).
3. Set the matching `OCR_PROVIDER` in the environment.
4. If you want image parsing back, re-add an `ImageRouter` and an `image/`
   branch in `ParserRouter.route_path` that calls `provider.parse_image_s3(...)`.
5. Add any provider-specific settings to `app/core/config.py` and document the
   credential boundary. Textract is intentionally not implemented for Playbook.

---

## 3. Embedders

`embedders/` provides:

- `base.py` — `EmbedProviderMode(StrEnum)` (LITELLM/DIRECT), `BaseEmbedProvider`
  (ABC with the shared sync `embed()` loop + dimension check), and the error
  hierarchy (`EmbedProviderError` / `EmbedRateLimitError` / `EmbedTransientError`
  + `normalize_embed_exception`).
- `direct.py` / `litellm.py` — concrete providers (model from
  `DIRECT_EMBED_MODEL` / `LITELLM_EMBED_MODEL`).
- `factory.py` — the StrEnum + `@lru_cache` pattern:
  - `get_embed_provider(mode)` — process-wide cached singleton. Safe for sync
    callers (the API path).
  - `build_fresh_embed_provider(mode)` — **non-cached**. Worker threads MUST use
    this: the underlying httpx client binds to the creating thread's event loop,
    so a shared cached client across threads triggers "Event loop is closed"
    races (openai-python#1254). Each worker thread builds its own client.
  - `clear_all_caches()`.

### Changing the embedding model / dimension

The embedding dimension is wired in **three** places that must stay in sync:

1. `settings.KB_EMBED_DIMENSIONS` — validated against every returned vector in
   `BaseEmbedProvider.embed()`.
2. `settings.DIRECT_EMBED_MODEL` / `settings.LITELLM_EMBED_MODEL` — the model
   that actually produces vectors of that dimension.
3. The `vector(N)` column in the database migration for the embeddings table —
   `N` must equal `KB_EMBED_DIMENSIONS`.

Changing the model or dimension requires re-ingesting existing documents.

---

## 4. Rerankers

`rerankers/` provides the Phase 2 reranker provider surface:

- `base.py` — `BaseRerankProvider`, `RerankCandidate`, `RerankedCandidate`, and
  the `RerankProviderError` / `RerankTransientError` hierarchy.
- `litellm.py` — sync HTTPX-backed LiteLLM `/rerank` provider. It sends
  `model`, `query`, ordered `documents`, and optional bounded `top_n`, then maps
  returned `results[*].index` and `results[*].relevance_score` back to the
  original chunk identities.
- `factory.py` — cached process-wide provider construction using
  `LITELLM_RERANK_MODEL`, `KB_RERANK_TIMEOUT_SECONDS`, and
  `KB_RERANK_FAIL_OPEN`.

The provider logs only request metadata such as model alias, counts, status,
failure class, and elapsed time. It must not log raw query text, chunk text,
returned document text, source URIs, or secrets.

When `KB_RERANK_FAIL_OPEN=true`, retryable LiteLLM failures return candidates in
input order with `rerank_score=None`. Fail-closed mode raises instead. Malformed
or non-retryable responses always raise.

`SearchService` calls the reranker only when `KB_SEARCH_STRATEGY=hybrid` and
`KB_RERANK_ENABLED=true`. It passes the bounded hybrid candidate list, applies
the request `limit` after reranking, and keeps semantic, lexical, hybrid, and
rerank diagnostics inside result metadata.

---

## 5. Search repository: semantic and hybrid candidates

`vectorstore/pgvector.py` exposes:

- `cosine_search(pg_engine, collection_id, organization_id, query_vector, max_docs, score_threshold, metadata_filter)` (sync)
- `async_cosine_search(session, ...)` (async, via `AsyncSession`)
- `bulk_insert_embeddings(pg_engine, document_id, collection_id, chunks, embeddings)`

Contract: search uses pgvector's `.cosine_distance()`; relevance is reported as
`score = 1 - distance`, filtered by `score_threshold`. An optional
`metadata_filter` is applied via JSONB containment. `bulk_insert_embeddings`
deletes any existing rows for `document_id` (idempotent re-ingest) then inserts
the new chunk vectors.

Search repository internals are split by responsibility:

- `app.repositories.vector_repo.records` builds deterministic chunk/vector insert records.
- `app.repositories.vector_repo.queries` builds shared semantic and lexical SQLAlchemy statements.
- `app.repositories.vector_repo.mapping` maps raw DB rows into the KB search result shape.
- `app.repositories.vector_repo.ranking` owns dedupe, reciprocal-rank fusion, and ranking diagnostics.
- `app.repositories.vector_repo.sync_repo` exposes the sync `VectorRepository` used by workers.
- `app.repositories.vector_repo.async_repo` exposes the async `AsyncVectorRepository` used by API services.

`app.repositories.vector_repo` is the package facade for existing service,
worker, test, and compatibility-wrapper imports.

The repository also owns Phase 3 lexical and hybrid candidate generation:

- lexical search uses `websearch_to_tsquery('english', query)` against the
  generated `VectorEmbedding.search_vector` column,
- lexical relevance uses `ts_rank_cd`,
- semantic and lexical statements share the same collection, successful
  document status, organization, visibility, source-type, conversation, and
  file-scope filters,
- hybrid search dedupes candidates by `chunk_id`, then exact text fallback, and
  ranks them with reciprocal-rank fusion.

Runtime selection is internal config only:

```env
KB_SEARCH_STRATEGY=semantic  # semantic | hybrid
KB_HYBRID_CANDIDATE_LIMIT=50
KB_RRF_K=60
```

Do not expose search strategy, arbitrary metadata filters, or source type
selection to browser callers. The backend must continue deriving trusted
retrieval scope before calling KB-service.

---

## 6. IO / S3

- `io/s3_client.py` — `build_s3_client()` (process-wide cached boto3 client,
  honours `S3_ENDPOINT_URL` / region / keys / profile) and
  `invalidate_s3_client()` (clears the cache so the next call rebuilds, e.g.
  after credential expiry).
- `io/s3_tempfile.py` — `stream_s3_object_to_tempfile` (async) and
  `stream_s3_object_to_tempfile_sync` (sync) context managers that stream an S3
  object to a temp file chunk by chunk (bounded RAM), retrying once on expired
  credentials. The temp file is deleted on context exit.

---

## Compile-time note

All heavy third-party imports (docling, fitz, openai, openpyxl, docx, pptx,
langchain_text_splitters, boto3) are **lazy** — imported inside functions/methods
or under `TYPE_CHECKING`. This lets `python -m compileall` succeed without those
packages installed. Keep this invariant when adding code.
