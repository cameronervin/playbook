"""Langfuse initialization for LangGraph tracing.

Provides initialization and CallbackHandler factory for tracing
LangGraph agent executions with Langfuse observability.

Langfuse automatically captures:
- LLM calls (model, prompt, completion, tokens, latency, cost)
- Chain runs (input, output, duration)
- Tool calls (name, input, output)
- Nested trace trees for full execution visibility

Used by the eval harness (``evals/``) to link runs/scores to traces, and
available to the app for runtime tracing. All Langfuse imports are lazy so the
module loads without the SDK installed (it ships in the ``evals`` extra).
"""

import os

import structlog

from app.core.config import Settings, get_settings

logger = structlog.get_logger(__name__)

_initialized = False


def is_langfuse_ready() -> bool:
    """Return True when Langfuse SDK is initialized and ready for callbacks."""
    return _initialized


def init_langfuse(settings: Settings | None = None) -> None:
    """Initialize Langfuse by setting environment variables for the SDK.

    The Langfuse Python SDK (v3+) uses a singleton pattern and reads
    credentials from environment variables automatically. This function
    sets the env vars from our application settings and validates
    the connection.

    Must be called once at application startup before any CallbackHandler
    is created.
    """
    global _initialized
    app_settings = settings or get_settings()

    if not app_settings.LANGFUSE_ENABLED:
        logger.info("Langfuse tracing is disabled", langfuse_enabled=False)
        return

    if not app_settings.LANGFUSE_SECRET_KEY or not app_settings.LANGFUSE_PUBLIC_KEY:
        logger.warning(
            "Langfuse enabled but credentials missing",
            has_secret_key=bool(app_settings.LANGFUSE_SECRET_KEY),
            has_public_key=bool(app_settings.LANGFUSE_PUBLIC_KEY),
        )
        return

    os.environ["LANGFUSE_SECRET_KEY"] = app_settings.LANGFUSE_SECRET_KEY
    os.environ["LANGFUSE_PUBLIC_KEY"] = app_settings.LANGFUSE_PUBLIC_KEY
    os.environ["LANGFUSE_HOST"] = app_settings.LANGFUSE_HOST

    _initialized = True
    logger.info("Langfuse tracing initialized", host=app_settings.LANGFUSE_HOST)


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

    from langfuse.langchain import CallbackHandler  # noqa: PLC0415

    return CallbackHandler()


def shutdown_langfuse() -> None:
    """Flush pending traces and shut down the Langfuse client.

    Must be called at application shutdown to ensure all traces
    are sent before the process exits.
    """
    if not _initialized:
        return

    try:
        from langfuse import get_client  # noqa: PLC0415

        get_client().shutdown()
        logger.info("Langfuse client shut down successfully")
    except Exception as e:  # noqa: BLE001
        logger.warning("Error shutting down Langfuse", error=str(e))
