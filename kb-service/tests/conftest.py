"""Shared pytest fixtures and import shims for KB service tests.

These module-level shims let the unit tests import application modules without
the heavy native dependencies (pgvector C extension, langchain splitters) or a
running broker / database. The Celery shim here is the single canonical source
of truth — individual test files must NOT define their own Celery shims (shim
code only runs if celery is not yet in sys.modules, which is non-deterministic
based on pytest collection order).

conftest runs before any test module is imported, so installing the shims here
guarantees all tests see the same fakes.
"""
from __future__ import annotations

import os
import sys
import types
from types import SimpleNamespace

# ── required env vars (de-branded, safe test defaults) ─────────────────────────
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://kb:kb@localhost:5432/kb")
os.environ.setdefault("KB_WEBHOOK_SECRET", "test-webhook-secret")
os.environ.setdefault("KB_API_SECRET", "test-api-secret")
os.environ.setdefault("LLM_PROVIDER_MODE", "litellm")
os.environ.setdefault("LITELLM_BASE_URL", "http://litellm:4000")
os.environ.setdefault("LITELLM_API_KEY", "test-key")

# ── pgvector shim ──────────────────────────────────────────────────────────────
# pgvector is a C extension not available outside the container. Stub it so unit
# tests importing app.models.* can collect without a running Postgres + extension.
if "pgvector" not in sys.modules:
    from sqlalchemy import types as _sa_types

    from sqlalchemy import func as _sa_func

    class _VECTOR(_sa_types.UserDefinedType):
        """Minimal SQLAlchemy VECTOR stub for unit tests.

        Subclasses UserDefinedType (not TypeDecorator) so we can attach a
        Comparator exposing ``cosine_distance`` — the operator the real pgvector
        VECTOR provides and that ``_build_search_statement`` relies on.
        """

        cache_ok = True

        def __init__(self, dim: int | None = None) -> None:
            self.dim = dim

        def get_col_spec(self, **kw) -> str:
            return "VECTOR" if self.dim is None else f"VECTOR({self.dim})"

        class comparator_factory(_sa_types.UserDefinedType.Comparator):
            def cosine_distance(self, other):
                # Stand-in distance expression; only needs to be a valid SQL
                # expression for statement-building tests.
                return _sa_func.cosine_distance(self.expr, other)

    _pgvector = types.ModuleType("pgvector")
    _pgvector_sqlalchemy = types.ModuleType("pgvector.sqlalchemy")
    _pgvector_sqlalchemy.VECTOR = _VECTOR
    sys.modules["pgvector"] = _pgvector
    sys.modules["pgvector.sqlalchemy"] = _pgvector_sqlalchemy

# ── Celery shim ────────────────────────────────────────────────────────────────
# Installed before any test module is collected so all files see the same shim.
if "celery" not in sys.modules:
    _celery = types.ModuleType("celery")
    _celery_exc = types.ModuleType("celery.exceptions")
    _celery_sig = types.ModuleType("celery.signals")
    _celery_res = types.ModuleType("celery.result")
    _celery_schedules = types.ModuleType("celery.schedules")

    class _SoftTimeLimitExceeded(Exception):
        pass

    class _MaxRetriesExceededError(Exception):
        pass

    class _Signal:
        def connect(self, fn):
            return fn

    class _FakeTask:
        """Stand-in for a bound Celery task — preserves .s()/.delay()/.apply_async()."""

        def __init__(self, fn, name=None):
            self._fn = fn
            self.name = name or fn.__name__
            self.max_retries = 3
            self.request = SimpleNamespace(id="test-task-id", retries=0)
            self.__name__ = fn.__name__
            self.__doc__ = fn.__doc__

        def __call__(self, *args, **kwargs):
            return self._fn(self, *args, **kwargs)

        def run(self, *args, **kwargs):
            return self._fn(self, *args, **kwargs)

        def s(self, *args, **kwargs):
            return self

        def delay(self, *args, **kwargs):
            return SimpleNamespace(id="fake-task-id")

        def apply_async(self, *args, **kwargs):
            return SimpleNamespace(id="fake-task-id")

        def retry(self, exc=None, **kwargs):
            if exc:
                raise exc
            raise RuntimeError("retry called")

    class _AsyncResult:
        def __init__(self, task_id, app=None):
            self.id = task_id
            self.state = "PENDING"

    class _FakeCelery:
        def __init__(self, *args, **kwargs):
            self.conf = SimpleNamespace(update=lambda **kw: None)

        def task(self, *args, **kwargs):
            def decorator(fn):
                return _FakeTask(fn, kwargs.get("name"))

            return decorator

    _celery.Celery = _FakeCelery
    _celery.group = lambda items: list(items)
    _celery.chord = lambda sigs: (lambda cb: SimpleNamespace(id="fake-chord-id"))
    _celery.current_app = SimpleNamespace(backend=SimpleNamespace(client=None))
    _celery_exc.SoftTimeLimitExceeded = _SoftTimeLimitExceeded
    _celery_exc.MaxRetriesExceededError = _MaxRetriesExceededError
    _celery_sig.worker_process_init = _Signal()
    _celery_sig.worker_process_shutdown = _Signal()
    _celery_sig.worker_ready = _Signal()
    _celery_res.AsyncResult = _AsyncResult

    sys.modules["celery"] = _celery
    sys.modules["celery.exceptions"] = _celery_exc
    sys.modules["celery.signals"] = _celery_sig
    sys.modules["celery.result"] = _celery_res
    sys.modules["celery.schedules"] = _celery_schedules

# ── langchain_text_splitters shim ──────────────────────────────────────────────
if "langchain_text_splitters" not in sys.modules:
    try:
        import langchain_text_splitters  # noqa: F401
    except ModuleNotFoundError:
        _splitters = types.ModuleType("langchain_text_splitters")

        class _FakeSplitDocument:
            def __init__(self, page_content: str, metadata: dict) -> None:
                self.page_content = page_content
                self.metadata = metadata

        class _FakeRecursiveCharacterTextSplitter:
            def __init__(
                self,
                *,
                chunk_size: int = 512,
                chunk_overlap: int = 0,
                add_start_index: bool = False,
                **kwargs,
            ) -> None:
                self.chunk_size = chunk_size
                self.chunk_overlap = chunk_overlap
                self.add_start_index = add_start_index

            @classmethod
            def from_tiktoken_encoder(cls, **kwargs):
                return cls(**kwargs)

            def create_documents(self, texts, metadatas=None):
                docs = []
                step = max(self.chunk_size - self.chunk_overlap, 1)
                for idx, text in enumerate(texts):
                    base_meta = dict((metadatas or [{}])[idx] if metadatas else {})
                    start = 0
                    while start < len(text):
                        end = min(start + self.chunk_size, len(text))
                        piece = text[start:end]
                        if piece.strip():
                            meta = dict(base_meta)
                            if self.add_start_index:
                                meta["start_index"] = start
                            docs.append(_FakeSplitDocument(page_content=piece, metadata=meta))
                        if end >= len(text):
                            break
                        start += step
                return docs

        _splitters.RecursiveCharacterTextSplitter = _FakeRecursiveCharacterTextSplitter
        sys.modules["langchain_text_splitters"] = _splitters
