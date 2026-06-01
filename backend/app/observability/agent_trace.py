"""Shared LangGraph invoke config for tracing and recursion limits.

Builds the ``config`` dict passed to ``graph.ainvoke(...)`` so every agent run
carries a consistent thread id, phase tag, recursion limit, and (optionally) a
tracing callback handler.

Tracing is intentionally provider-agnostic here: ``TRACING_ENABLED`` toggles it
and ``_build_trace_callbacks()`` is the single place to attach a real tracer
(Langfuse, LangSmith, OpenTelemetry, etc.).
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)


def verify_tracing_configuration() -> dict[str, Any]:
    """Report tracing readiness at startup (logged by the lifespan)."""
    return {"enabled": settings.TRACING_ENABLED, "ready": settings.TRACING_ENABLED}


def _build_trace_callbacks() -> list[Any]:
    """Return tracing callback handlers, or an empty list if disabled.

    Wire a concrete tracer here (e.g. a Langfuse/LangSmith CallbackHandler).
    Left empty in the scaffold so there is no hard tracing dependency.
    """
    if not settings.TRACING_ENABLED:
        return []
    # e.g. return [LangfuseCallbackHandler(...)] once a tracer is configured.
    return []


def build_graph_invoke_config(
    *,
    thread_id: UUID | str,
    phase: str,
    mode: str,
    extra_configurable: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an ainvoke config with tracing and recursion limits.

    Args:
        thread_id: Checkpointer thread id (typically the entity id).
        phase: Logical phase/step name for tracing.
        mode: Execution mode label for tracing.
        extra_configurable: Extra keys merged into ``configurable``.

    Returns:
        A config dict suitable for ``graph.ainvoke(state, config=...)``.
    """
    configurable: dict[str, Any] = {"thread_id": str(thread_id), "phase": phase, "mode": mode}
    if extra_configurable:
        configurable.update(extra_configurable)

    config: dict[str, Any] = {
        "configurable": configurable,
        "recursion_limit": settings.AGENT_GRAPH_RECURSION_LIMIT,
    }

    callbacks = _build_trace_callbacks()
    if callbacks:
        config["callbacks"] = callbacks

    return config
