# Infrastructure Overview

This package holds the swappable adapters that the rest of the app depends on
through abstract interfaces. Nothing outside `infrastructure/` imports a vendor
SDK (boto3, anthropic, httpx KB client, psycopg) directly.

## Shared pattern

Every adapter family (except storage, which needs explicit cleanup) follows:

```
BaseXxx (ABC)                  — the contract
XxxMode (StrEnum)              — selectable modes
get_xxx() @lru_cache           — mode-driven singleton factory
get_xxx_dependency()           — FastAPI Depends wrapper
clear_*_cache() / cleanup_*()  — test reset / shutdown
```

Concrete providers are imported lazily inside the factory so unused SDKs are
never imported.

## Components

| Component        | Interface / entry            | Modes                | Real backend         |
|------------------|------------------------------|----------------------|----------------------|
| **LLM**          | `llm/` — `BaseLLMProvider`   | `direct`, `gateway`  | Anthropic / LiteLLM  |
| **Knowledgebase**| `knowledgebase/` — `BaseKnowledgebaseProvider` | `mock`, `local` | KB service (httpx)   |
| **Storage**      | `storage/` — `StorageProvider` | (single)           | S3 / LocalStack (boto3) |
| **Database**     | `db/` — engine/session helpers | (single)           | Postgres (SQLAlchemy) |
| **Checkpointer** | `checkpointer.py`            | (single)             | Postgres (LangGraph) |

See each subpackage's `STUBS.md` for the extension guide.

## Lifecycle (owned by `app/main.py` lifespan)

Startup order:

1. Observability (tracing init)
2. LLM provider (`get_llm_provider()`)
3. Knowledgebase provider (`get_kb_provider()` when `is_kb_feature_enabled()`)
4. Storage provider (`get_storage_provider()`)
5. Checkpointer pool + checkpointer (`create_checkpointer_pool` → `create_checkpointer`)
6. Compile LangGraph graph(s) with the checkpointer (agent layer)
7. Build executors (agent layer)

Shutdown happens in reverse order:

- Shutdown observability
- Close checkpointer pool (`cleanup_checkpointer_pool`)
- Close KB provider (`provider.close()`)
- Cleanup storage (`cleanup_storage_provider`)
- Dispose DB engine (`cleanup_db_engine`)

## Checkpointer notes

- Uses `LANGGRAPH_CHECKPOINT_DB_URL` if set, else `DATABASE_URL`.
- SQLAlchemy `+asyncpg` URLs are converted to psycopg DSNs automatically.
- `prune_old_checkpoints()` deletes data older than `CHECKPOINT_RETENTION_DAYS`
  (wire it into a scheduled task as needed).

## Database notes

- `db/session.py` owns the lazy SQLAlchemy async engine and session factory.
- `db/base.py` imports all ORM models so metadata is available for Alembic and
  SQLAlchemy autogeneration.
