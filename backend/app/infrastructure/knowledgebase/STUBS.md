# Knowledgebase Infrastructure — Stubs & Extension Guide

Retrieval-augmented knowledge access behind a provider interface. Two modes
ship: `mock` (offline fixtures) and `local` (httpx-backed KB service).

## Pattern

```
BaseKnowledgebaseProvider (ABC)   ← providers/base.py
   ├── MockProvider               ← providers/mock.py     (offline fixtures)
   └── LocalKBProvider            ← providers/local_kb.py (httpx KB service)

KBProviderMode (StrEnum)          ← factory.py
get_kb_provider() @lru_cache      ← factory.py  (singleton, mode-driven)
get_kb_provider_dependency()      ← factory.py  (FastAPI Depends)
is_kb_feature_enabled()           ← factory.py  (KB_ENABLED kill switch)
clear_kb_provider_cache()         ← factory.py  (test reset)

assemble_context()                ← context.py  (token-bounded markdown)
deduplicate_chunks()              ← dedup.py    (content de-dup, keep best score)
```

Selection is driven by `settings.KB_PROVIDER_MODE` (`mock` | `local`) and gated
by `settings.KB_ENABLED`.

## The retrieval contract (Phase A — implemented)

Every provider implements:

- `search(query, max_docs, score_threshold, metadata_filter, configuration_id) -> KnowledgebaseResult`
- `health_check() -> bool`
- `resolve_configuration() -> str` (cached after first success; raises
  `KBConfigError` when the config can't be found → fail-fast at startup)
- `close()` (no-op by default; `LocalKBProvider` closes its httpx client)

`MockProvider.resolve_configuration()` returns a static ID and never touches
the network, so it stays trivially simple.

## Phase B — ingestion / pipeline provisioning (NOT YET IMPLEMENTED)

These were intentionally kept off the base ABC so the Mock/Local providers stay
lean. When an ingestion backend is added, introduce them as **provider-specific**
methods (or a separate `IngestingKnowledgebaseProvider` mix-in), not abstract
methods on `BaseKnowledgebaseProvider`:

- `provision_pipeline(name, collection_name) -> str` — create a new collection/
  pipeline configuration.
- `submit_document_url(configuration_id, presigned_url, filename, metadata, ...) -> str | None`
  — start an async ingestion task; returns a task id.
- `check_task_status(task_id) -> str | None` — poll a single ingestion task.
- `ingest_document_url(...)` — convenience: submit + poll + resolve doc id.
- `delete_document(document_id)` / `delete_pipeline(configuration_id)`.
- `find_document_ids_by_filename(configuration_id, filename) -> list[str]`.

Document ingestion is typically driven from a Celery task (see `app/tasks/`),
calling the individual submit/poll methods with worker-managed retries.

## Adding a real KB backend

1. Subclass `BaseKnowledgebaseProvider` (e.g. `PgVectorProvider`).
2. Implement the four Phase A methods. Map transport/HTTP failures onto the KB
   exceptions in `app/core/exceptions.py` (`KBConnectionError`, `KBTimeoutError`,
   `KBAuthError`, `KBValidationError`, `KBConfigError`) so the error handler and
   retry semantics behave consistently.
3. Add a `KBProviderMode` member and a branch in `factory.get_kb_provider`.
4. Reuse `assemble_context()` and `deduplicate_chunks()` — do not re-implement
   context formatting per provider.
