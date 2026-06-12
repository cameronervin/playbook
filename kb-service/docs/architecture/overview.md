# KB Service — Architecture Overview

The KB Service is a standalone microservice that ingests documents, parses and
chunks them, embeds the chunks, and stores the vectors in pgvector for
similarity search. It exposes a small authenticated HTTP API and runs a
Celery worker pipeline for the heavy, asynchronous ingest work.

It is fully self-contained: it owns the `kb` Postgres schema and a dedicated
Valkey/Redis broker, and it pushes progress back to the calling application via
a signed status webhook. The host app never blocks on ingestion.

---

## 1. Ingest data flow

The host app uploads a document to S3, then calls `POST /api/kb/ingest/url`
with a presigned URL and a configuration id. The service validates and records
the request, then dispatches a Celery chain. Heavy payloads (page text, chunks,
embeddings) never travel through the broker — they are staged in S3 as NDJSON;
only small summary dicts flow between tasks.

```
                 POST /api/kb/ingest/url
                         │
                         ▼
                 IngestionService
        (HEAD size guard → MD5 dedup → create Document
         + IngestionLog → dispatch Celery chain)
                         │
                         ▼
   ┌──────────────── Celery chain (kb-cpu queue) ─────────────────┐
   │                                                              │
   │   parse_task ──► chunk_task ──► embed_task (fan-out)         │
   │   (S3 → tmp,     (pages NDJSON  (plan index windows,         │
   │    parser route,  → chunker →    reset progress counter)     │
   │    pages NDJSON   chunks NDJSON)                             │
   │    → S3)                                                     │
   └──────────────────────────────┬───────────────────────────────┘
                                   │  group(embed_batch_task.s(...))
                                   ▼
        ┌──────────── embed_batch_task × N (kb-io queue) ──────────┐
        │  read chunk slice [start,end) from S3 NDJSON            │
        │  → embed via LiteLLM (distributed rate limiter)         │
        │  → INSERT batch vectors into kb.langchain_pg_embedding  │
        │  → INCR Redis progress counter                          │
        │  → last batch dispatches load_vector_task               │
        └──────────────────────────────┬───────────────────────────┘
                                        │
                                        ▼
                          load_vector_task (kb-io)
            (verify vec count == staged chunk count;
             reissue missing chunks if short;
             mark SUCCESS, delete S3 staging, notify)
                                        │
                                        ▼
                          notify_status_task (kb-notify)
            (HMAC-SHA256 signed POST → {APP_WEBHOOK_URL}/api/v1/kb/webhook)
```

`notify_status_task` is dispatched at **every** stage transition
(parse/chunk/embed/load_vector + a terminal `pipeline` event), giving the host
app a live progress feed without polling.

### Why no chord?

`embed → load_vector` is deliberately **not** a Celery chord. `chord_unlock`
proved unreliable at high fan-out (50+ batches). Instead each `embed_batch_task`
writes its own vectors directly to pgvector and atomically increments a Redis
progress counter; the last-completing batch dispatches `load_vector_task` as a
plain follow-up. A safety-net `load_vector_task` is also scheduled with a
countdown, and a `reconcile_stuck_embeds` watchdog recovers any document whose
embed started but never finalised.

---

## 2. Search flow

```
POST /api/kb/search ──► SearchService ──► embed query (litellm/direct)
                                       └─► AsyncVectorRepository.search
                                             (cosine distance over pgvector,
                                              score = 1 - distance,
                                              HNSW vector_cosine_ops index)
                                       └─► results: [{document_id, text,
                                                      score, metadata}, ...]
```

Search runs synchronously inside the FastAPI request using the **async**
`AsyncVectorRepository`. The sync `VectorRepository` (same SQL building blocks)
is used by the Celery workers, which run on a threads pool and prefer sync I/O.

---

## 3. Worker queue split

Tasks are routed to dedicated queues so CPU-bound and I/O-bound work never
contend for the same workers:

| Queue        | Tasks                                                    | Pool / concurrency        | Why |
|--------------|----------------------------------------------------------|---------------------------|-----|
| `kb-cpu`     | `parse_task`, `chunk_task`, `embed_task` (dispatcher)    | prefork, ~2                | Docling + tiktoken are CPU-bound |
| `kb-io`      | `embed_batch_task`, `load_vector_task`, `reconcile_stuck_embeds` | threads, ~50      | LiteLLM HTTP + per-batch DB writes are I/O-bound |
| `kb-notify`  | `notify_status_task`                                     | solo                       | dedicated low-latency, avoids head-of-line blocking |

Reliability config applies to all queues: `task_acks_late`,
`task_reject_on_worker_lost`, `worker_prefetch_multiplier=1`, and 25/30-min
soft/hard time limits.

---

## 4. Storage: the `kb` Postgres schema + pgvector

All tables live in the dedicated `kb` schema (so the service can share a
Postgres instance with the host app without colliding). Alembic manages them
with `version_table_schema="kb"` and the async→sync URL rewrite in `env.py`.

| Table | Purpose |
|-------|---------|
| `kb.configurations`           | Parse/chunk/embed/vectorstore config + collection name |
| `kb.documents`                | One row per ingested document (status, md5 dedup, s3_key) |
| `kb.ingestion_logs`           | Per-stage task ids + statuses; KB's internal source of truth |
| `kb.langchain_pg_collection`  | LangChain-pgvector collection registry |
| `kb.langchain_pg_embedding`   | The vectors: `embedding vector(1536)` + `cmetadata` JSONB |

The `embedding` column is cast to `vector(1536)` and indexed with an **HNSW**
index using `vector_cosine_ops` (`m = 16, ef_construction = 64`). The migration
degrades gracefully when pgvector is unavailable (local dev): the column stays
`TEXT` and the pgvector-specific steps are skipped, so the migration still runs.

---

## 5. S3 NDJSON staging

To keep the Redis broker small and bounded regardless of document size, the
pipeline stages intermediate artifacts in S3 as newline-delimited JSON:

| Stage      | Staging key                              | Written by   | Read by |
|------------|------------------------------------------|--------------|---------|
| pages      | `kb/staging/{doc_id}/pages.ndjson`       | `parse_task` | `chunk_task` |
| chunks     | `kb/staging/{doc_id}/chunks.ndjson`      | `chunk_task` | `embed_batch_task`, `load_vector_task` |

Writes use a `SpooledTemporaryFile` + `boto3 upload_fileobj` (RAM until a spill
threshold, then disk). Each `embed_batch_task` reads only its own
`[chunk_start, chunk_end)` window. Staging is deleted after a successful
`load_vector` pass.

---

## 6. Thread-local engines + NullPool (the asyncio-in-threads problem)

Celery's threads pool runs many tasks concurrently in one process. asyncio is
strict about each thread owning its own event loop, and pooled asyncpg
connections are bound to the loop active at creation. A shared module-level
engine therefore breaks the moment a sibling thread reuses a connection from a
different loop ("Future attached to a different loop").

The service solves this with **thread-local async engines + NullPool**:

* Each thread caches its own `create_async_engine(..., poolclass=NullPool)`.
* NullPool opens a fresh connection per session and closes it on exit — no pool
  state survives across loops.
* The worker bootstrap (`init_worker_resources`) builds a **persistent** event
  loop per process and a `run_async()` helper that reuses it for same-thread
  tasks but falls back to `asyncio.run()` for sibling threads (threads/gevent
  pools) and for tests/scripts with no worker context.
* For the bulk vector INSERT in the load path, a separate **sync** SQLAlchemy
  engine (psycopg2) is used — no event loop needed at all.
* On worker shutdown, `reset_db_engine()` disposes the calling thread's cached
  engine so no asyncpg connection lingers on the dying loop.

The embedding client follows the same per-thread isolation: the worker registers
a `build_fresh_embed_provider` factory and each thread lazily builds its own
sync `OpenAI` client (and httpx pool) on first use.
