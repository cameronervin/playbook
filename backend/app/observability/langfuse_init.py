"""Langfuse initialization for LangGraph tracing.

Provides initialization and CallbackHandler factory for tracing
LangGraph agent executions with Langfuse observability.

Langfuse automatically captures:
- LLM calls (model, prompt, completion, tokens, latency, cost)
- Chain runs (input, output, duration)
- Tool calls (name, input, output)
- Nested trace trees for full execution visibility

Used by the eval harness (``evals/``) to link runs/scores to traces and by the
runtime app/worker processes for LangGraph tracing. Langfuse imports remain
lazy so settings/tests can import this module without constructing a client.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping, Sequence
from typing import Any

import structlog

from app.core.config import Settings, get_settings
from app.core.log_redaction import REDACTION, redact_string

logger = structlog.get_logger(__name__)

_initialized = False
_client: Any | None = None

_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_SIGNED_STORAGE_RE = re.compile(
    r"(?i)(x-amz-signature=|x-amz-security-token=|signature=|s3://|gs://)"
)
_TRACE_CONTENT_KEYS = {
    "answer",
    "completion",
    "completions",
    "content",
    "contents",
    "extracted_text",
    "file_contents",
    "input",
    "inputs",
    "message",
    "messages",
    "model_input",
    "model_inputs",
    "model_output",
    "model_outputs",
    "output",
    "outputs",
    "prompt",
    "prompts",
    "question",
    "raw_text",
    "response",
    "responses",
    "source_text",
    "source_texts",
    "tool_input",
    "tool_inputs",
    "tool_output",
    "tool_outputs",
}
_TRACE_SENSITIVE_KEYS = {
    "athlete_email",
    "athlete_emails",
    "athlete_name",
    "athlete_names",
    "client_ip",
    "email",
    "emails",
    "ip_address",
    "provider_sub",
    "provider_subject",
    "provider_subjects",
    "raw_ip",
    "raw_ip_address",
    "remote_addr",
    "remote_ip",
    "source_uri",
    "source_uris",
    "presigned_url",
    "presigned_urls",
    "signed_url",
    "signed_urls",
    "storage_key",
    "storage_keys",
}
_TRACE_SENSITIVE_KEY_PARTS = (
    "api_key",
    "apikey",
    "authorization",
    "password",
    "private_key",
    "raw_ip",
    "secret",
    "signature",
    "token",
    "provider_subject",
    "provider_sub",
)


def is_langfuse_ready() -> bool:
    """Return True when Langfuse SDK is initialized and ready for callbacks."""
    return _initialized


def init_langfuse(settings: Settings | None = None) -> bool:
    """Initialize Langfuse for eval and runtime tracing.

    Returns True when a client is ready. ``LANGFUSE_ENABLED`` controls client
    initialization; runtime callback attachment is additionally gated by
    ``TRACING_ENABLED`` in ``agent_trace``.
    """
    global _client, _initialized
    app_settings = settings or get_settings()

    if not app_settings.LANGFUSE_ENABLED:
        _reset_langfuse_state()
        logger.info("langfuse_tracing_disabled", langfuse_enabled=False)
        return False

    if not app_settings.LANGFUSE_SECRET_KEY or not app_settings.LANGFUSE_PUBLIC_KEY:
        _reset_langfuse_state()
        logger.warning(
            "langfuse_credentials_missing",
            private_credential_configured=bool(app_settings.LANGFUSE_SECRET_KEY),
            public_key_configured=bool(app_settings.LANGFUSE_PUBLIC_KEY),
        )
        return False

    try:
        from langfuse import Langfuse  # noqa: PLC0415
    except ImportError as exc:
        _reset_langfuse_state()
        logger.warning("langfuse_sdk_unavailable", error=str(exc))
        return False

    os.environ["LANGFUSE_SECRET_KEY"] = app_settings.LANGFUSE_SECRET_KEY
    os.environ["LANGFUSE_PUBLIC_KEY"] = app_settings.LANGFUSE_PUBLIC_KEY
    os.environ["LANGFUSE_BASE_URL"] = app_settings.LANGFUSE_BASE_URL

    try:
        _client = Langfuse(
            public_key=app_settings.LANGFUSE_PUBLIC_KEY,
            secret_key=app_settings.LANGFUSE_SECRET_KEY,
            base_url=app_settings.LANGFUSE_BASE_URL,
            environment=app_settings.ENVIRONMENT,
            mask=mask_langfuse_data,
        )
    except Exception as exc:  # noqa: BLE001
        _reset_langfuse_state()
        logger.warning("langfuse_initialization_failed", error=str(exc))
        return False

    _initialized = True
    logger.info(
        "langfuse_tracing_initialized",
        base_url=app_settings.LANGFUSE_BASE_URL,
        environment=app_settings.ENVIRONMENT,
    )
    return True


def create_langfuse_handler():
    """Create a Langfuse CallbackHandler for LangChain/LangGraph tracing.

    Returns a new CallbackHandler instance that will automatically capture
    all LangChain operations (LLM calls, chains, tools) when passed to
    graph.ainvoke() via config["callbacks"].

    Trace-level metadata (user_id, session_id, tags) should be passed
    via the config["metadata"] dict in ainvoke(), not here.

    Returns:
        CallbackHandler instance, or None if Langfuse is not initialized.
    """
    if not _initialized:
        return None

    try:
        from langfuse.langchain import CallbackHandler  # noqa: PLC0415
    except ImportError as exc:
        logger.warning("langfuse_callback_handler_unavailable", error=str(exc))
        return None

    return CallbackHandler()


def shutdown_langfuse() -> None:
    """Flush pending traces and shut down the Langfuse client.

    Must be called at application shutdown to ensure all traces
    are sent before the process exits.
    """
    global _client
    if not _initialized and _client is None:
        return

    try:
        if _client is not None:
            _client.shutdown()
        else:
            from langfuse import get_client  # noqa: PLC0415

            get_client().shutdown()
        logger.info("langfuse_client_shutdown")
    except Exception as e:  # noqa: BLE001
        logger.warning("langfuse_shutdown_failed", error=str(e))
    finally:
        _reset_langfuse_state()


def mask_langfuse_data(data: Any) -> Any:
    """Recursively redact trace payload data before it leaves the process."""
    if isinstance(data, str):
        return _redact_trace_string(data)
    if isinstance(data, Mapping):
        return {
            key: REDACTION
            if _is_trace_sensitive_key(key)
            else mask_langfuse_data(value)
            for key, value in data.items()
        }
    if isinstance(data, tuple):
        return tuple(mask_langfuse_data(item) for item in data)
    if isinstance(data, Sequence) and not isinstance(data, (bytes, bytearray)):
        return [mask_langfuse_data(item) for item in data]
    return data


def _reset_langfuse_state() -> None:
    global _client, _initialized
    _initialized = False
    _client = None


def _is_trace_sensitive_key(key: Any) -> bool:
    normalized = _normalize_key(key)
    if normalized.endswith(("_id", "_ids")):
        return False
    return (
        normalized in _TRACE_CONTENT_KEYS
        or normalized in _TRACE_SENSITIVE_KEYS
        or any(part in normalized for part in _TRACE_SENSITIVE_KEY_PARTS)
    )


def _normalize_key(key: Any) -> str:
    snake_case = re.sub(r"(?<!^)(?=[A-Z])", "_", str(key))
    return snake_case.lower().replace("-", "_").replace(" ", "_")


def _redact_trace_string(value: str) -> str:
    if _SIGNED_STORAGE_RE.search(value):
        return REDACTION
    return _EMAIL_RE.sub(REDACTION, redact_string(value))
