"""Worker-level shared state — initialised on worker startup.

Thread-pool safety:
    Celery's ``--pool=threads`` runs many tasks concurrently in one process.

    The pg_engine is a SYNC SQLAlchemy engine and is safe to share across
    threads (psycopg2/SQLAlchemy connection pool is thread-safe).

    The embed_client wraps a SYNC ``openai.OpenAI`` client (sync, not async, to
    avoid the per-task event-loop teardown race in openai-python#1254 — see
    ``embedders/base.py``). The sync client's underlying httpx.Client connection
    pool is thread-safe, so technically one instance could be shared. We still
    build one per thread to preserve isolation (one bad TLS state in a pool only
    affects that thread) and to keep the contract identical regardless of the
    sync/async choice — the rest of the codebase need not care.

    parser_router and text_splitter are sync, sharable.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any


@dataclass
class _WorkerState:
    pg_engine: Any = field(default=None)        # sync SQLAlchemy Engine — thread-safe
    parser_router: Any = field(default=None)    # sync, thread-safe
    text_splitter: Any = field(default=None)    # sync, thread-safe

    # Thread-local embed clients: each worker thread gets its own sync OpenAI
    # client (and therefore its own httpx connection pool). See module docstring
    # for why per-thread instead of process-wide.
    _embed_clients: threading.local = field(default_factory=threading.local)
    # Factory used to build a fresh embed_client per thread. Set during init.
    _embed_client_factory: Any = field(default=None)

    @property
    def embed_client(self):
        """Return the current thread's embed_client, lazily creating it."""
        client = getattr(self._embed_clients, "client", None)
        if client is None:
            if self._embed_client_factory is None:
                # init never ran — fall back to building from scratch.
                from app.infrastructure.embedders.factory import (
                    build_fresh_embed_provider,
                )

                self._embed_client_factory = build_fresh_embed_provider
            client = self._embed_client_factory()
            self._embed_clients.client = client
        return client


# Module-level singleton — mutated by init_worker_resources in workers/app.py
worker_state = _WorkerState()
