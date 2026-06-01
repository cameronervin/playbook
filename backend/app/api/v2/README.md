# API v2 — Async Task Pattern

Reserved for endpoints that follow the **async task** pattern: a request returns
a `task_id` immediately and the client polls a task-status endpoint for the
result, instead of blocking on a long-running agent/LLM call.

Typical shape:

```
POST /api/v2/<resource>        → 202 Accepted, { "task_id": "..." }
GET  /api/v2/tasks/{task_id}   → { "status": "pending|running|succeeded|failed", "result": ... }
```

The work is dispatched to a background worker (see `app/tasks/`), which uses
`worker_db_session()` for its own DB session. v1 endpoints remain the blocking
equivalents.

Add routers here and include them in `app/main.py` under the `API_V2_PREFIX`.
