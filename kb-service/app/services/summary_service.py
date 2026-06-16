"""Canonical source summary generation for KB ingestion."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Protocol

import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)

_MAX_SUMMARY_CHARS = 900
_DEFAULT_FALLBACK = "No usable source text was available for summary generation."


class SummaryAgent(Protocol):
    async def ainvoke(self, payload: dict[str, Any]) -> Any:
        """Invoke the summary agent."""


@dataclass(frozen=True, slots=True)
class SummarySource:
    """Source material used to build a compact summary prompt."""

    filename: str
    source_title: str | None
    metadata: dict[str, Any]
    parse_result: dict[str, Any] | None
    chunks: list[dict[str, Any]]


async def summarize_source(
    source: SummarySource,
    *,
    agent: SummaryAgent | None = None,
    max_input_tokens: int | None = None,
) -> str:
    """Generate a canonical source summary, falling back extractively on failure."""
    try:
        agent = agent or _create_default_agent()
        max_tokens = max_input_tokens or settings.KB_SUMMARY_INPUT_MAX_TOKENS
        prompt = build_summary_input(source, max_tokens=max_tokens)
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": prompt}]}
        )
        structured = _structured_summary(result)
        return normalize_summary(structured)
    except Exception as exc:  # noqa: BLE001 - summary failure is non-blocking.
        logger.warning(
            "kb_summary_agent_failed_using_fallback",
            error_type=type(exc).__name__,
            source_type=source.metadata.get("source_type"),
        )
        return fallback_summary(source)


def build_summary_input(source: SummarySource, *, max_tokens: int) -> str:
    """Build a deterministic, token-capped summary input."""
    parse_result = source.parse_result or {}
    lines = [
        "## Source Metadata",
        f"Title: {_clean_text(source.source_title or source.filename)}",
        f"Filename: {_clean_text(source.filename)}",
        f"Source type: {_clean_text(source.metadata.get('source_type', 'unknown'))}",
        f"Parser: {_clean_text(parse_result.get('selected_parser', 'unknown'))}",
        f"Route: {_clean_text(parse_result.get('route', 'unknown'))}",
        "",
        "## Representative Text",
    ]
    for index, chunk in enumerate(source.chunks, start=1):
        text = _chunk_text(chunk)
        if not text:
            continue
        lines.append(f"[Chunk {index}] {text}")
    return _truncate_to_tokens("\n".join(lines), max_tokens=max_tokens)


def fallback_summary(source: SummarySource) -> str:
    """Return a short extractive fallback summary from safe title + first passage."""
    title = _clean_title(source.source_title or source.filename)
    passage = _first_meaningful_passage(source.chunks)
    if not passage:
        return f"{title}: {_DEFAULT_FALLBACK}"
    return normalize_summary(f"{title}: {passage}")


def normalize_summary(value: str) -> str:
    """Collapse whitespace and keep at most two sentences."""
    normalized = _clean_text(value)
    if not normalized:
        return _DEFAULT_FALLBACK
    sentences = re.findall(r"[^.!?]+[.!?]?", normalized)
    summary = " ".join(sentence.strip() for sentence in sentences[:2]).strip()
    if summary and summary[-1] not in ".!?":
        summary = f"{summary}."
    return summary[:_MAX_SUMMARY_CHARS].strip()


def _create_default_agent() -> SummaryAgent:
    from app.agents.chains import create_source_summary_agent

    return create_source_summary_agent()


def _structured_summary(result: Any) -> str:
    if isinstance(result, dict):
        structured = result.get("structured_response", result)
        if hasattr(structured, "summary"):
            return str(structured.summary)
        if isinstance(structured, dict):
            return str(structured.get("summary", ""))
    if hasattr(result, "summary"):
        return str(result.summary)
    return str(result)


def _truncate_to_tokens(text: str, *, max_tokens: int) -> str:
    if max_tokens <= 0:
        return ""
    try:
        import tiktoken

        encoding = tiktoken.get_encoding(settings.KB_CHUNK_TOKENIZER)
        token_ids = encoding.encode(text)
        if len(token_ids) <= max_tokens:
            return text
        return encoding.decode(token_ids[:max_tokens]).strip()
    except Exception:  # noqa: BLE001 - fallback keeps summary path resilient.
        return text[: max_tokens * 4].strip()


def _first_meaningful_passage(chunks: list[dict[str, Any]]) -> str:
    for chunk in chunks:
        text = _chunk_text(chunk)
        if text:
            return text
    return ""


def _chunk_text(chunk: dict[str, Any]) -> str:
    text = chunk.get("text", "")
    return _clean_text(text if isinstance(text, str) else str(text))


def _clean_title(value: str) -> str:
    cleaned = _clean_text(value)
    return cleaned or "Source"


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()
