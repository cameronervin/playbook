"""Celery application for the KB service ingest pipeline.

Worker queues (split CPU vs I/O for optimal throughput):
  kb-cpu     — parse_task, chunk_task, embed_task dispatcher (CPU-bound)
               Use prefork pool, --concurrency=2
  kb-io      — embed_batch_task, load_vector_task, reconcile_stuck_embeds
               (I/O-bound: gateway HTTP + per-batch DB writes)
               Use threads pool, --concurrency=50 so a single process can hold
               many in-flight gateway calls.
  kb-notify  — notify_status_task (dedicated to avoid head-of-line blocking)

Start workers (recommended layout on a 3 CPU / 2 GB host)::

  # CPU worker: prefork keeps parse/chunk on separate OS processes
  celery -A app.workers.app worker -Q kb-cpu --pool=prefork --concurrency=2 \\
         --loglevel=info -n kb-cpu@%h

  # I/O worker: threads pool — 50 OS threads multiplex gateway calls in one process
  celery -A app.workers.app worker -Q kb-io --pool=threads --concurrency=50 \\
         --loglevel=info -n kb-io@%h

  # Notify worker (small, dedicated)
  celery -A app.workers.app worker -Q kb-notify --pool=solo \\
         --loglevel=info -n kb-notify@%h

Importing this module opens NO broker connection — the Celery app is built from
settings URLs but connects lazily on first dispatch / worker boot. That keeps
``app.workers.tasks`` importable under ``compileall`` and the test shims with no
network running.
"""
from __future__ import annotations

import asyncio
import sys
import threading

if sys.platform == "win32":
    # asyncpg requires the selector loop on Windows.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import structlog
from celery import Celery
from celery.signals import worker_process_init, worker_process_shutdown, worker_ready

from app.core.config import settings
from app.infrastructure.embedders.factory import build_fresh_embed_provider

logger = structlog.get_logger(__name__)

# Public Celery app object. Named ``kb_worker`` and imported by the service
# layer (ingestion/status services) as well as ``tasks.py``.
kb_worker = Celery("kb", broker=settings.CELERY_BROKER_URL)

kb_worker.conf.update(
    # Routing — split CPU-bound vs I/O-bound tasks onto dedicated worker pools.
    # Order matters: more-specific rules first.
    task_default_queue="kb-cpu",
    task_routes={
        # Notifications: dedicated low-latency queue.
        "app.workers.tasks.notify_status_task": {"queue": "kb-notify"},
        # I/O-bound — gateway HTTP, DB writes. Routed to kb-io.
        "app.workers.tasks.embed_batch_task":       {"queue": "kb-io"},
        "app.workers.tasks.load_vector_task":       {"queue": "kb-io"},
        "app.workers.tasks.reconcile_stuck_embeds": {"queue": "kb-io"},
        # CPU-bound — parse (Docling) and chunk (tiktoken). Routed to kb-cpu.
        "app.workers.tasks.parse_task": {"queue": "kb-cpu"},
        "app.workers.tasks.chunk_task": {"queue": "kb-cpu"},
        "app.workers.tasks.embed_task": {"queue": "kb-cpu"},  # dispatcher only — fans out to kb-io
        # Catch-all fallback.
        "app.workers.tasks.*": {"queue": "kb-cpu"},
    },
    # Reliability guardrails
    task_time_limit=1800,                   # 30-min hard kill
    task_soft_time_limit=1500,              # 25-min soft warning
    task_acks_late=True,                    # requeue on worker crash
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,           # fetch one task at a time (fairness)
    broker_transport_options={"visibility_timeout": 7200},
    result_backend_transport_options={"visibility_timeout": 7200},
    # Result backend
    result_backend=settings.CELERY_RESULT_BACKEND,
    result_expires=86400,                   # 1 day
    # Memory management
    worker_max_tasks_per_child=50,
    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
)


import app.workers.tasks  # noqa: F401, E402 — must import to register tasks with kb_worker


# Module-level singletons — populated on worker startup.
# _worker_loop_owner_thread captures the thread that built the loop so we can
# detect when a task is running in a sibling thread (threads/gevent pools) and
# fall back to a fresh loop. asyncio is strict about loop-per-thread.
_worker_loop: asyncio.AbstractEventLoop | None = None
_worker_loop_owner_thread: int | None = None


def get_worker_loop() -> asyncio.AbstractEventLoop:
    """Return the worker's persistent event loop."""
    if _worker_loop is None:
        raise RuntimeError("Worker not initialised — call init_worker_resources first")
    return _worker_loop


def run_async(coro):
    """Run a coroutine — pool-aware.

    Behavior by Celery pool:
      * prefork / solo (single thread per process) → reuse the persistent worker
        loop set up by ``init_worker_resources``. Keeps asyncpg/HTTP pools warm
        across task invocations.
      * threads / gevent (many concurrent tasks share one process) → the shared
        worker loop can't be re-entered, so each task spins up its own loop via
        ``asyncio.run``. Slight per-task overhead but lets I/O workers multiplex
        50+ in-flight gateway calls.
      * tests / scripts (no worker init at all) → ``asyncio.run`` fallback.
    """
    global _worker_loop, _worker_loop_owner_thread

    if _worker_loop is None:
        # No worker context (tests, ad-hoc scripts).
        return asyncio.run(coro)

    # Cross-thread access (threads / gevent pools): each pool worker thread
    # must have its own event loop. Reusing the main-thread loop produces
    # "attached to a different loop" errors deep inside asyncpg / aiohttp.
    if threading.get_ident() != _worker_loop_owner_thread:
        return asyncio.run(coro)

    # Same thread that built the loop, and the loop is idle → reuse it.
    if _worker_loop.is_running() or _worker_loop.is_closed():
        return asyncio.run(coro)

    try:
        return _worker_loop.run_until_complete(coro)
    except RuntimeError as exc:
        if "already running" in str(exc) or "different thread" in str(exc):
            return asyncio.run(coro)
        raise


@worker_process_init.connect
@worker_ready.connect
def init_worker_resources(**kwargs) -> None:
    """Initialise per-process singletons once at worker startup.

    Subscribed to TWO signals because Celery fires them at different times
    for different pool types:
      * ``worker_process_init`` — fires per-child for the ``prefork`` pool.
      * ``worker_ready`` — fires once when the worker is ready, for ALL pool
        types including ``threads``, ``gevent``, and ``solo`` (used on Windows).
    Either signal triggers idempotent init — guarded below so double-fire is safe.

    Creates a persistent SelectorEventLoop (required on Windows for asyncpg)
    and stores it for reuse by all SAME-THREAD task executions. Also initialises
    the embedding client factory, the parser router, the sync DB engine for the
    load_vector stage, and the (expensive-to-build) text splitter.
    """
    from app.workers.state import worker_state as _ws

    # Idempotent: if already initialised on this process, skip. Both signals
    # can fire on the same process; also ``worker_ready`` fires once per startup.
    if _ws._embed_client_factory is not None and _ws.parser_router is not None:
        return

    global _worker_loop, _worker_loop_owner_thread

    from sqlalchemy import create_engine
    from sqlalchemy.engine.url import make_url

    from app.infrastructure.chunkers.token_based import _build_text_splitter
    from app.infrastructure.parsers.routing.router import ParserRouter
    from app.workers.state import worker_state

    # Persistent loop — all SAME-THREAD tasks reuse this so asyncpg pools stay
    # valid. Tasks executed on sibling threads (threads/gevent pools) fall back
    # to ``asyncio.run()`` (see run_async).
    _worker_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_worker_loop)
    _worker_loop_owner_thread = threading.get_ident()

    # Sync engine for load_vector (bulk INSERT via psycopg2, no asyncpg needed).
    # make_url + set() handles any driver suffix safely (e.g. postgresql+asyncpg).
    sync_url = make_url(settings.DATABASE_URL).set(drivername="postgresql")
    worker_state.pg_engine = create_engine(
        sync_url, pool_size=settings.KB_VECTORSTORE_POOL_SIZE, pool_pre_ping=True
    )

    # Embedding client — register the per-thread factory rather than eagerly
    # building one (an OpenAI httpx pool would bind to the main thread's state
    # and break for sibling worker threads). worker_state.embed_client lazily
    # builds + caches one client per thread on first access.
    worker_state._embed_client_factory = build_fresh_embed_provider
    worker_state.parser_router = ParserRouter()
    # Text splitter — tiktoken init is expensive; build once per worker process.
    worker_state.text_splitter = _build_text_splitter()

    logger.info("kb_worker_initialised", thread_id=_worker_loop_owner_thread)


@worker_process_shutdown.connect
def teardown_worker_resources(**kwargs) -> None:
    """Dispose thread-local async DB engines on worker shutdown.

    The async session module caches one NullPool engine per thread. On a clean
    worker shutdown we reset the calling thread's cached engine so no asyncpg
    connection lingers bound to the about-to-die event loop.
    """
    try:
        from app.infrastructure.db.session import reset_db_engine

        reset_db_engine()
    except Exception as exc:
        logger.warning("kb_worker_teardown_failed", error=str(exc))
