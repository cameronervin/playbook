"""Shared LangGraph invoke config for tracing and recursion limits.

Builds the ``config`` dict passed to ``graph.ainvoke(...)`` so every agent run
carries a consistent thread id, phase tag, recursion limit, and (optionally) a
tracing callback handler.

Tracing is intentionally provider-agnostic here: ``TRACING_ENABLED`` toggles it
and ``_build_trace_callbacks()`` is the single place to attach a real tracer
(Langfuse, LangSmith, OpenTelemetry, etc.).
"""
from __future__ import annotations

import re
from typing import Any
from uuid import UUID

import structlog

from app.core.config import Settings, get_settings
from app.observability.langfuse_init import create_langfuse_handler, is_langfuse_ready

logger = structlog.get_logger(__name__)

_SAFE_TRACE_METADATA_KEYS = {
    "assistant_message_id",
    "conversation_id",
    "message_id",
    "organization_id",
    "run_id",
    "session_id",
    "task_id",
    "user_message_id",
}
_THREAD_ID_METADATA_KEY_BY_MODE = {
    "admin_chat": "session_id",
    "athlete_chat": "conversation_id",
    "conversation_title": "conversation_id",
    "dashboard_insights": "run_id",
}
_SAFE_TRACE_VALUE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}$")


def verify_tracing_configuration(settings: Settings) -> dict[str, Any]:
    """Report tracing readiness at startup (logged by the lifespan)."""
    provider = "langfuse" if settings.LANGFUSE_ENABLED else None
    return {
        "enabled": settings.TRACING_ENABLED,
        "provider": provider,
        "ready": bool(
            settings.TRACING_ENABLED
            and settings.LANGFUSE_ENABLED
            and is_langfuse_ready()
        ),
    }


def _build_trace_callbacks(settings: Settings) -> list[Any]:
    """Return tracing callback handlers, or an empty list if disabled.

    Runtime trace callbacks require both the feature flag and a ready Langfuse
    client. A fresh handler is created for each graph invocation.
    """
    if (
        not settings.TRACING_ENABLED
        or not settings.LANGFUSE_ENABLED
        or not is_langfuse_ready()
    ):
        return []

    handler = create_langfuse_handler()
    return [handler] if handler is not None else []


def build_graph_invoke_config(
    *,
    thread_id: UUID | str,
    phase: str,
    mode: str,
    settings: Settings | None = None,
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
    app_settings = settings or get_settings()
    configurable: dict[str, Any] = {"thread_id": str(thread_id), "phase": phase, "mode": mode}
    if extra_configurable:
        configurable.update(extra_configurable)

    config: dict[str, Any] = {
        "configurable": configurable,
        "recursion_limit": app_settings.AGENT_GRAPH_RECURSION_LIMIT,
    }

    callbacks = _build_trace_callbacks(app_settings)
    if callbacks:
        config["callbacks"] = callbacks
        config["metadata"] = _build_safe_trace_metadata(
            settings=app_settings,
            thread_id=thread_id,
            phase=phase,
            mode=mode,
            configurable=configurable,
        )
        config["tags"] = [
            "playbook",
            f"env:{app_settings.ENVIRONMENT}",
            f"mode:{mode}",
            f"phase:{phase}",
        ]

    return config


def _build_safe_trace_metadata(
    *,
    settings: Settings,
    thread_id: UUID | str,
    phase: str,
    mode: str,
    configurable: dict[str, Any],
) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for key, value in (
        ("environment", settings.ENVIRONMENT),
        ("mode", mode),
        ("phase", phase),
    ):
        safe_value = _safe_metadata_value(value)
        if safe_value is not None:
            metadata[key] = safe_value

    thread_metadata_key = _THREAD_ID_METADATA_KEY_BY_MODE.get(mode)
    if thread_metadata_key is not None:
        safe_thread_id = _safe_metadata_value(thread_id)
        if safe_thread_id is not None:
            metadata[thread_metadata_key] = safe_thread_id

    for key in _SAFE_TRACE_METADATA_KEYS:
        if key not in configurable:
            continue
        safe_value = _safe_metadata_value(configurable[key])
        if safe_value is not None:
            metadata[key] = safe_value

    return metadata


def _safe_metadata_value(value: Any) -> str | None:
    if isinstance(value, UUID):
        value = str(value)
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if _SAFE_TRACE_VALUE_RE.fullmatch(stripped):
        return stripped
    return None
