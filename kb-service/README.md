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
POST /api/kb/ingest/url ─▶ IngestionService ─▶ Celery chain
                                                  parse_task   (docling + native parsers, complexity-routed)
                                                    │  └─ stages page text to S3 (NDJSON)
                                                  chunk_task   (tiktoken recursive splitter)
                                                    │  └─ stages chunks to S3 (NDJSON)
                                                  embed_task   (fan-out dispatcher)
                                                    └─▶ group(embed_batch_task)  (OpenAI / LiteLLM embeddings)
                                                          └─ writes vectors → pgvector (kb.langchain_pg_embedding)
                                                          └─ last batch dispatches load_vector_task (finalize)

POST /api/kb/embed/search ─▶ SearchService ─▶ embed query ─▶ pgvector cosine search ─▶ ranked chunks
```

## Stack

| Concern | Technology |
|---------|-----------|
| API | FastAPI (port 8001), Bearer service-to-service auth |
| Async pipeline | Celery + Valkey (multi-queue: cpu / io / notify) |
| Parsing | Docling (PDF/DOCX/PPTX) + native (python-docx / openpyxl / python-pptx); complexity router |
| OCR | **stub** (`NullOCRProvider`) — plug Textract/VLM back in (see `app/infrastructure/STUBS.md`) |
| Chunking | tiktoken `RecursiveCharacterTextSplitter` (400 tokens / 40 overlap) |
| Embeddings | OpenAI direct or LiteLLM gateway (`EmbedProviderMode`), `text-embedding-3-small`, 1536-dim |
| Vector store | pgvector (`vector(1536)`, HNSW `vector_cosine_ops`) in the `kb` schema |
| Storage | S3 / LocalStack (boto3), streamed to tempfiles |

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
  workers/                 Celery app, tasks, per-thread state, rate limiter
  infrastructure/
    db/session.py          thread-local async engine + NullPool (Celery-thread safe)
    parsers/               contracts + extractors + complexity routing + OCR stub
    chunkers/              token-based recursive splitter
    embedders/             ABC + direct + gateway + factory
    vectorstore/           pgvector cosine search / bulk insert wrappers
    llm/                   embed client builders (lru_cache)
    io/                    S3 streaming tempfile helpers
alembic/                   pgvector extension + kb schema migrations
tests/                     pgvector / celery / splitter shims; repo + worker contract tests
```

## Run locally

```bash
cd kb-service
pip install -r requirements.txt
alembic upgrade head                 # needs Postgres with the pgvector extension
python run_dev.py                    # uvicorn on :8001
# workers (separate terminals):
celery -A app.workers.app worker -Q kb-cpu --pool=prefork --concurrency=2
celery -A app.workers.app worker -Q kb-io  --pool=threads  --concurrency=50
```

See `deploy/compose/base.yml` (+ `--profile worker`) to run the whole stack with Docker.

## Extending

Read `app/infrastructure/STUBS.md` for: adding a parser/extractor, plugging a real
OCR provider (Textract / VLM), and changing the embedding model or vector dimension
(requires a migration — the `vector(N)` column dimension is fixed).
