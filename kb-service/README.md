# KB Service — RAG ingestion & retrieval

A standalone microservice that turns uploaded documents into searchable vector
embeddings and serves similarity search over them. It is the **server** half of
the scaffold's knowledgebase feature; the main `backend/` calls it over HTTP via
`backend/app/infrastructure/knowledgebase/providers/local_kb.py` (`LocalKBProvider`).

> This is **pattern-faithful scaffolding**, not a running product. The example
> flow parses and type-checks; real tuning, auth secrets, and an S3 bucket are
> left to the integrator. Heavy deps (docling, celery, openai) are imported
> lazily so the code compiles without them installed.

---

## Pipeline

```
POST /api/kb/configuration/resolve ─▶ automatic idempotent default config

POST /api/kb/ingest/document ───────▶ IngestionService ─▶ Celery chain
                                                          parse_task   (docling + native parsers, complexity-routed)
                                                            │  └─ stages page text to S3 (NDJSON)
                                                          chunk_task   (tiktoken recursive splitter)
                                                            │  └─ stages chunks to S3 (NDJSON)
                                                          embed_task   (fan-out dispatcher)
                                                            └─▶ group(embed_batch_task)  (OpenAI / LiteLLM embeddings)
                                                                  └─ writes vectors → pgvector (kb.langchain_pg_embedding)
                                                                  └─ last batch dispatches load_vector_task (finalize)

POST /api/kb/search ────────────────▶ SearchService ─▶ embed query ─▶ pgvector cosine search ─▶ ranked results
```

`/configuration/resolve` owns the singleton Playbook defaults
(`Playbook KB Pipeline` + `playbook-kb`) and is safe to call on a fresh local
database. Search resolves that default internally before vector lookup, so a
new database returns zero results instead of requiring manual configuration
seeding.

## Stack

| Concern | Technology |
|---------|-----------|
| API | FastAPI (port 8001), Bearer service-to-service auth |
| Async pipeline | Celery + Valkey (multi-queue: cpu / io / notify) |
| Parsing | Docling (PDF/DOCX/PPTX) + native (python-docx / openpyxl / python-pptx); complexity router |
| OCR | Opt-in scanned PDF OCR via LiteLLM VLM alias (`OCR_PROVIDER=vlm`); default is `NullOCRProvider` |
| Chunking | tiktoken `RecursiveCharacterTextSplitter` (400 tokens / 40 overlap) |
| Embeddings | OpenAI direct or LiteLLM mode (`EmbedProviderMode`), 1536-dim |
| Vector store | pgvector (`vector(1536)`, HNSW `vector_cosine_ops`) in the `kb` schema |
| Storage | S3-compatible storage / MinIO locally (boto3), streamed to tempfiles |

## Layout

```
app/
  main.py                  FastAPI + lifespan (build embed provider, dispose engines)
  core/config.py           Pydantic Settings (grouped by concern)
  models/                  SQLAlchemy models incl. pgvector VectorEmbedding
  schemas/                 Pydantic DTOs (configuration / ingest / search / status)
  repositories/            CRUD + vector similarity search
  services/                ingestion / search / configuration orchestration
  api/                     routers + deps (service_auth, services)
  workers/                 Celery app, task package, per-thread state, rate limiter
    tasks/                 parse/chunk/embed/finalize/notify/watchdog modules
  infrastructure/
    db/session.py          thread-local async engine + NullPool (Celery-thread safe)
    parsers/               contracts + extractors + complexity routing + opt-in VLM OCR
    chunkers/              token-based recursive splitter
    embedders/             ABC + direct + litellm + factory
    vectorstore/           pgvector cosine search / bulk insert wrappers
    llm/                   embed client builders (lru_cache)
    io/                    S3 streaming tempfile helpers
alembic/                   pgvector extension + kb schema migrations
tests/                     pgvector / celery / splitter shims; repo + worker contract tests
```

## Run locally

```bash
cd kb-service
uv sync
uv run alembic upgrade head          # needs Postgres with the pgvector extension
uv run uvicorn app.main:app --host 0.0.0.0 --port 8001
# workers (separate terminals):
uv run celery -A app.workers.app worker -Q kb-cpu --pool=prefork --concurrency=2
uv run celery -A app.workers.app worker -Q kb-io  --pool=threads  --concurrency=50
```

See `deploy/compose/base.yml` (+ `--profile worker`) to run the whole stack with Docker.

## Smoke test

Once the API, Postgres, Valkey, S3/MinIO, LiteLLM, and KB workers are running:

```bash
cd kb-service
uv run python scripts/smoke_kb_service.py
```

The script creates a tiny DOCX, uploads it to the configured bucket, ingests it,
waits for the worker pipeline, runs retrieval, and deletes the test artifact by
default. Use `--keep` to preserve the uploaded object and KB document while
debugging.

## Extending

Read `../docs/guides/kb_service_extension_points.md` for: adding a
parser/extractor, enabling the LiteLLM-routed VLM OCR path, and changing the
embedding model or vector dimension (requires a migration — the `vector(N)`
column dimension is fixed).
