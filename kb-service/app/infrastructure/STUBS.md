# Infrastructure Stubs & Extension Points

This is the genericized RAG infrastructure layer. It ships with the heavy,
vendor-specific pieces stubbed out so the scaffold compiles and runs with a
minimal dependency set. This document explains the extension points and how to
plug real implementations back in.

---

## 1. Parser layer

### The Protocol + dispatch registry

Every extractor satisfies one of two Protocols in
`parsers/contracts/base.py`:

- `IParser` — `parse(file, filename) -> list[str]` (one string per page/section).
  You get `parse_path(path, filename)` for free, or override it for path-based
  libraries.
- `IStructuredParser` — `parse_structured*` returning a `ParseOutcome` with
  structured `ParseArtifacts` (tables, figures, layout blocks). Docling parsers
  implement this.

Both are `runtime_checkable`, so the router can `isinstance`-check a parser
without importing concrete classes.

`PARSER_DISPATCH: dict[str, type[IParser]]` is the global MIME -> parser-class
table. Each extractor module registers itself at import time:

```python
PARSER_DISPATCH["application/pdf"] = NativePDFParser
```

`parsers/__init__.py::load_parser_registry()` imports every extractor module
exactly once so the table is fully populated before routing. The top-level
`ParserRouter` calls it in its constructor.

### Adding a new extractor

1. Create `parsers/extractors/<name>.py`.
2. Implement a class with `parse(self, file, filename) -> list[str]`.
3. Import any heavy library **lazily inside the method** (so the module compiles
   without it installed).
4. Register it: `PARSER_DISPATCH["<mime>"] = MyParser`.
5. Add the import to `load_parser_registry()` in `parsers/__init__.py`.

### The complexity router

`parsers/routing/complexity.py::ComplexityAssessor` classifies a document
deterministically (no model calls) using the `settings.*THRESHOLD*` values:

| Category | Parser | Module |
|----------|--------|--------|
| `low`    | native extractor (fast, light) | `extractors/pdf_native.py`, `docx.py`, `pptx.py`, `excel.py` |
| `medium` | Docling (structured extraction) | `extractors/docling.py` |
| `high`   | OCR provider (scanned / image-dominant) | `providers/ocr/ocr.py` |

- `parsers/routing/pdf.py::PDFRouter` — high -> OCR, medium -> Docling, low -> native.
- `parsers/routing/office.py::OfficeRouter` — medium -> Docling DOCX/PPTX, low -> native.
- `parsers/routing/router.py::ParserRouter` — top-level MIME dispatch.

### What changed vs the source service

- **`unstructured` was dropped.** The low-complexity local PDF path now uses
  `NativePDFParser` (PyMuPDF / `fitz`), which simply returns
  `[page.get_text() for page in doc]`. See `extractors/pdf_native.py`.
- **The `image/` route was dropped** from `ParserRouter`, along with
  `routing/image.py`. Image OCR depended on the now-stubbed OCR providers.
- The native DOCX parser class was renamed `UnstructuredDOCXParser` ->
  `NativeDOCXParser` (it never used `unstructured`; the name was misleading).

---

## 2. OCR provider (the key stub)

`parsers/providers/ocr/ocr.py` defines:

- `OCRProvider = Literal["none", "textract", "vlm"]`
- `BaseOCRProvider` (Protocol) — `parse_pdf_high_complexity(...) -> ParseOutcome | None`
  and `parse_image_s3(...) -> ParseOutcome`.
- `NullOCRProvider` — the default (`OCR_PROVIDER="none"`):
  - `parse_pdf_high_complexity` returns `None` → the PDF router falls back to
    native text extraction (`ocr_unavailable_fallback_native`). Scanned PDFs
    degrade gracefully instead of hard-failing.
  - `parse_image_s3` raises `UnsupportedFileTypeError` — there is no sensible
    text-only fallback for an image.
- `build_ocr_provider(provider=None)` — factory keyed off `settings.OCR_PROVIDER`.
  Returns `NullOCRProvider()` for `"none"`; raises `NotImplementedError` for
  `"textract"` / `"vlm"`.

### Plugging a real OCR provider back in

The source service shipped two providers that were **dropped for genericity**:

- **Textract** — AWS Textract async document analysis: submit the S3 object,
  poll the job until complete, assemble text from the returned blocks.
- **VLM** — OpenAI Vision: rasterise pages to images and caption/transcribe
  them with a vision-language model.

To restore OCR:

1. Implement a class satisfying `BaseOCRProvider` (set `provider = "textract"`
   or `"vlm"`). Put it under `parsers/providers/ocr/`.
2. Return it from `build_ocr_provider()` for the matching `OCR_PROVIDER` value
   (replace the `NotImplementedError` branch).
3. Set `OCR_PROVIDER=textract` (or `vlm`) in the environment.
4. If you want image parsing back, re-add an `ImageRouter` and an `image/`
   branch in `ParserRouter.route_path` that calls `provider.parse_image_s3(...)`.
5. Add any provider-specific settings (the scaffold config intentionally has no
   `TEXTRACT_*` / `VLM_*` keys — add them to `app/core/config.py`).

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

## 4. pgvector cosine search

`vectorstore/pgvector.py` exposes:

- `cosine_search(pg_engine, collection_id, organization_id, query_vector, max_docs, score_threshold, metadata_filter)` (sync)
- `async_cosine_search(session, ...)` (async, via `AsyncSession`)
- `bulk_insert_embeddings(pg_engine, document_id, collection_id, chunks, embeddings)`

Contract: search uses pgvector's `.cosine_distance()`; relevance is reported as
`score = 1 - distance`, filtered by `score_threshold`. An optional
`metadata_filter` is applied via JSONB containment. `bulk_insert_embeddings`
deletes any existing rows for `document_id` (idempotent re-ingest) then inserts
the new chunk vectors.

The SQL itself lives in the vector repository
(`app.repositories.vector_repo`) and the `VectorEmbedding` model
(`app.models.vector_embedding`), authored separately. These imports resolve when
those files land.

---

## 5. IO / S3

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
