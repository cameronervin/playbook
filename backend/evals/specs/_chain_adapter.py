"""Shared chain-level adapter for eval specs.

Builds a ``GraphRun`` by invoking one agent chain with a dataset item's input.
Chains are ``create_agent`` graphs that take ``{"messages": [...], **state}`` and
return state with a ``structured_response`` (Pydantic) or final ``messages``.

This is the generic example adapter: it maps ``input.question`` (or ``query``) to
a ``HumanMessage`` and passes any other ``input`` keys straight into the chain
state. A real product replaces ``_extra_state`` with its own input hydration (the
source harness hydrated stored workflow artifacts into Pydantic models here).

KB capture: KB tools call ``get_kb_provider()`` lazily at invoke time, so for the
RAG specs we temporarily wrap that provider with a recorder and collect the
retrieved chunk texts. They are shaped as ``events=[{"retriever": {"documents":
[...]}}]`` so ``RagasJudge`` can read ``retrieved_contexts`` unchanged. Runs are
sequential within a run, so the scoped patch is safe.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from contextlib import contextmanager
from typing import Any

import structlog
from langchain_core.messages import HumanMessage

from evals.core.types import GraphRun

logger = structlog.get_logger(__name__)


def _item_input(item: Any) -> Any:
    """Read ``input`` from a Langfuse dataset item OR a plain dict."""
    if isinstance(item, dict):
        return item.get("input")
    return getattr(item, "input", None)


class _RecordingKBProvider:
    """Delegating wrapper that records the text of every retrieved chunk."""

    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self.captured: list[str] = []

    async def search(self, *args: Any, **kwargs: Any) -> Any:
        result = await self._inner.search(*args, **kwargs)
        for chunk in getattr(result, "sources", None) or []:
            text = getattr(chunk, "text", None)
            if text:
                self.captured.append(text)
        return result

    def __getattr__(self, name: str) -> Any:  # forward everything else
        return getattr(self._inner, name)


@contextmanager
def _record_kb():
    """Patch the KB tool's ``get_kb_provider`` to a recorder for one invocation.

    Generic + best-effort: if the KB tool module / provider is not present, the
    patch is a no-op and the run proceeds with no captured contexts.
    """
    try:
        import app.agents.tools.example_kb_tool as kb_tool
        from app.infrastructure.knowledgebase import get_kb_provider
    except Exception:  # noqa: BLE001 — KB layer optional; capture nothing
        yield None
        return

    recorder = _RecordingKBProvider(get_kb_provider())
    original = kb_tool.get_kb_provider
    kb_tool.get_kb_provider = lambda *a, **k: recorder  # type: ignore[assignment]
    try:
        yield recorder
    finally:
        kb_tool.get_kb_provider = original  # type: ignore[assignment]


def _question(item_input: Any) -> str:
    if isinstance(item_input, dict):
        return str(item_input.get("question") or item_input.get("query") or item_input)
    return str(item_input)


def _extra_state(item_input: Any) -> dict[str, Any]:
    """Pass through non-question input fields into the chain state.

    Oversized fields are stored in Langfuse as ``{"$blob_ref": path}`` (see
    ``evals.core.sync``); resolve them back to full content first so the agent
    receives the same input it would in production. A product replaces this with
    its own input hydration (e.g. validating stored artifacts into Pydantic models).
    """
    if not isinstance(item_input, dict):
        return {}
    from pathlib import Path

    from evals.core.sync import resolve_blob_refs

    blob_base = Path(__file__).resolve().parents[1] / "datasets"
    resolved = resolve_blob_refs(item_input, base_dir=blob_base)
    if not isinstance(resolved, dict):
        return {}
    return {k: v for k, v in resolved.items() if k not in ("question", "query")}


def _extract_output(result: Any) -> Any:
    if isinstance(result, dict):
        structured = result.get("structured_response")
        if structured is not None:
            return structured.model_dump() if hasattr(structured, "model_dump") else structured
        messages = result.get("messages")
        if messages:
            last = messages[-1]
            return getattr(last, "content", str(last))
    return result


def _invoke_config() -> dict[str, Any]:
    """Minimal ainvoke config: a fresh thread + a Langfuse handler when available."""
    config: dict[str, Any] = {"configurable": {"thread_id": str(uuid.uuid4())}}
    try:
        from app.observability.langfuse_init import create_langfuse_handler

        handler = create_langfuse_handler()
    except Exception:  # noqa: BLE001 — tracing optional
        handler = None
    if handler is not None:
        config["callbacks"] = [handler]
    return config


def make_chain_adapter(
    get_chains: Callable[[], dict[str, Any]],
    chain_key: str,
    *,
    capture_kb: bool = False,
) -> Callable[..., Any]:
    """Build an async adapter ``adapter(item) -> GraphRun`` for one chain."""

    async def adapter(item: Any) -> GraphRun:
        item_input = _item_input(item)
        state: dict[str, Any] = {"messages": [HumanMessage(content=_question(item_input))]}
        state.update(_extra_state(item_input))
        config = _invoke_config()
        chain = get_chains()[chain_key]

        events: list[dict] = []
        if capture_kb:
            with _record_kb() as recorder:
                result = await chain.ainvoke(state, config=config)
            if recorder is not None and recorder.captured:
                events.append({"retriever": {"documents": recorder.captured}})
        else:
            result = await chain.ainvoke(state, config=config)

        return GraphRun(input=item_input, output=_extract_output(result), events=events, trace_id=None)

    return adapter
