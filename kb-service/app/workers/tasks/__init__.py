"""KB pipeline Celery task package.

The public task names intentionally remain ``app.workers.tasks.<task>`` even
though the implementations live in focused submodules. Celery routing, status
lookups, and ``IngestionService`` imports depend on those stable names.
"""
from __future__ import annotations

from app.workers.tasks.embedding import embed_batch_task, embed_task
from app.workers.tasks.finalize import load_vector_task
from app.workers.tasks.ingest import chunk_task, parse_task
from app.workers.tasks.notify import notify_status_task
from app.workers.tasks.summary import summarize_task
from app.workers.tasks.watchdog import reconcile_stuck_embeds

__all__ = [
    "chunk_task",
    "embed_batch_task",
    "embed_task",
    "load_vector_task",
    "notify_status_task",
    "parse_task",
    "reconcile_stuck_embeds",
    "summarize_task",
]
