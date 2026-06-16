"""Reusable knowledge-base search tool factory for agent workflows."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

import structlog
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings
from app.core.exceptions import KnowledgebaseError
from app.infrastructure.knowledgebase import (
    BaseKnowledgebaseProvider,
    get_kb_provider,
)
from app.schemas.knowledgebase import KnowledgebaseResult, RetrievedChunk

logger = structlog.get_logger(__name__)
_KB_ORGANIZATION_ID: ContextVar[str | None] = ContextVar(
    "kb_organization_id",
    default=None,
)


class KnowledgebaseSearchInput(BaseModel):
    """Input schema for reusable KB search tools."""

    query: str = Field(..., description="Natural language retrieval query")
    max_docs: int | None = Field(
        default=None,
        ge=1,
        le=50,
        description="Optional maximum number of chunks to retrieve",
    )
    score_threshold: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Optional minimum similarity threshold",
    )


@dataclass(frozen=True)
class KnowledgebaseToolProfile:
    """Use-case-specific configuration for a reusable KB search tool."""

    tool_name: str
    description: str
    default_max_docs: int = 10
    default_score_threshold: float = 0.7
    metadata_filter: dict[str, Any] | None = None
    configuration_id: str | None = None
    no_results_message: str = "No relevant knowledge base context found."
    unavailable_message: str = "Knowledge base temporarily unavailable."


@dataclass(frozen=True)
class KnowledgebaseSource:
    """Citation-ready source captured from a KB tool result."""

    source_key: str
    source_title: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    similarity_score: float | None = None


SourceRegistry = dict[str, KnowledgebaseSource]
SENSITIVE_SOURCE_METADATA_KEYS = {
    "source_uri",
    "presigned_url",
    "signed_url",
    "raw_text",
    "extracted_text",
    "file_contents",
    "model_input",
    "model_inputs",
}

ATHLETE_KB_TOOL_PROFILE = KnowledgebaseToolProfile(
    tool_name="search_playbook_knowledgebase",
    description=(
        "Search official Playbook athletic department knowledge base sources for "
        "athlete NIL, compliance, recruiting, reporting, and process guidance. "
        "Use this before making policy or process claims."
    ),
    metadata_filter={"visibility_policy": {"scope": "all_athletes"}},
)


@contextmanager
def knowledgebase_organization_context(organization_id: str) -> Iterator[None]:
    """Bind organization scope for KB tools invoked without LangChain config."""
    token = _KB_ORGANIZATION_ID.set(organization_id)
    try:
        yield
    finally:
        _KB_ORGANIZATION_ID.reset(token)


def create_knowledgebase_search_tool(
    profile: KnowledgebaseToolProfile,
    *,
    provider: BaseKnowledgebaseProvider | None = None,
    app_settings: Settings | None = None,
    source_registry: SourceRegistry | None = None,
) -> StructuredTool:
    """Create a named KB search tool using a profile-specific model contract."""
    settings = app_settings or get_settings()
    registry = source_registry if source_registry is not None else {}

    async def _search(
        query: str,
        max_docs: int | None = None,
        score_threshold: float | None = None,
        # LangChain injects runtime config only when the annotation is exactly RunnableConfig.
        config: RunnableConfig = None,
    ) -> str:
        kb_provider = provider or get_kb_provider(app_settings=settings)
        organization_id = _organization_id_from_config(config) or _KB_ORGANIZATION_ID.get()
        if not organization_id:
            logger.warning(
                "agent_kb_tool_missing_organization",
                tool_name=profile.tool_name,
            )
            return profile.unavailable_message
        resolved_max_docs = max_docs or profile.default_max_docs
        resolved_score_threshold = (
            score_threshold
            if score_threshold is not None
            else profile.default_score_threshold
        )

        logger.info(
            "agent_kb_tool_request",
            tool_name=profile.tool_name,
            max_docs=resolved_max_docs,
            score_threshold=resolved_score_threshold,
        )

        try:
            result = await kb_provider.search_admin_uploads(
                query=query,
                organization_id=organization_id,
                max_docs=resolved_max_docs,
                score_threshold=resolved_score_threshold,
                metadata_filter=profile.metadata_filter,
                configuration_id=profile.configuration_id,
            )
        except KnowledgebaseError as exc:
            logger.warning(
                "agent_kb_tool_unavailable",
                tool_name=profile.tool_name,
                error_type=type(exc).__name__,
            )
            return profile.unavailable_message
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "agent_kb_tool_unexpected_error",
                tool_name=profile.tool_name,
                error_type=type(exc).__name__,
                exc_info=True,
            )
            return profile.unavailable_message

        return _format_search_result(result, profile=profile, registry=registry)

    return StructuredTool.from_function(
        coroutine=_search,
        name=profile.tool_name,
        description=profile.description,
        args_schema=KnowledgebaseSearchInput,
    )


def _organization_id_from_config(config: RunnableConfig | None) -> str | None:
    configurable: Mapping[str, Any] | None = None
    if isinstance(config, Mapping):
        raw_configurable = config.get("configurable")
        if isinstance(raw_configurable, Mapping):
            configurable = raw_configurable
    value = configurable.get("organization_id") if configurable else None
    return str(value) if value else None


def _format_search_result(
    result: KnowledgebaseResult,
    *,
    profile: KnowledgebaseToolProfile,
    registry: SourceRegistry,
) -> str:
    if result.zero_hit or not result.sources:
        return profile.no_results_message

    sources = register_knowledgebase_sources(result, registry=registry)
    return "\n\n".join(
        _format_source(source, rank=rank)
        for rank, source in enumerate(sources, start=1)
    )


def register_knowledgebase_sources(
    result: KnowledgebaseResult,
    *,
    registry: SourceRegistry,
) -> list[KnowledgebaseSource]:
    """Register citation-ready chunks and return their source records."""
    if result.zero_hit or not result.sources:
        return []

    sources: list[KnowledgebaseSource] = []
    for rank, chunk in enumerate(result.sources, start=1):
        source = _source_from_chunk(chunk, rank=rank)
        registry[source.source_key] = source
        sources.append(source)
    return sources


def format_conversation_file_context(
    sources: list[KnowledgebaseSource],
) -> str:
    """Format deterministic private file context for the athlete chat model."""
    if not sources:
        return ""

    sections: list[str] = []
    for rank, source in enumerate(sources, start=1):
        meta = source.metadata
        lines = [
            f"[{source.source_key}] {source.source_title}",
            f"Rank: {rank}",
            "Source type: conversation_file",
        ]
        for key, label in (
            ("conversation_file_id", "Conversation file ID"),
            ("conversation_id", "Conversation ID"),
            ("kb_service_document_id", "KB Service Document ID"),
            ("chunk_id", "Chunk ID"),
            ("chunk_index", "Chunk index"),
        ):
            if meta.get(key) is not None:
                lines.append(f"{label}: {meta[key]}")
        if meta.get("source_locator") is not None:
            lines.append(
                "Locator: "
                + json.dumps(meta["source_locator"], sort_keys=True, default=str)
            )
        if meta.get("source_summary"):
            lines.append(
                "Source summary (orientation only): "
                + str(meta["source_summary"])
            )
        if source.similarity_score is not None:
            lines.append(f"Similarity: {source.similarity_score:.3f}")
        lines.append(f"Excerpt: {source.text}")
        sections.append("\n".join(lines))

    return "\n\n".join(
        [
            "## Conversation File Context",
            (
                "Use the excerpts below as evidence for this conversation only. "
                "Source summaries are orientation only and must not be cited as "
                "evidence."
            ),
            *sections,
        ]
    )


def _source_from_chunk(chunk: RetrievedChunk, *, rank: int) -> KnowledgebaseSource:
    metadata = _sanitize_source_metadata(dict(chunk.metadata or {}))
    source_title = str(
        metadata.get("source_title")
        or metadata.get("doc_title")
        or metadata.get("filename")
        or "Unknown Source"
    )
    key_basis = "|".join(
        [
            str(metadata.get("source_type", "")),
            str(metadata.get("document_id", "")),
            str(metadata.get("conversation_file_id", "")),
            str(metadata.get("chunk_id", "")),
            str(rank),
            chunk.text[:120],
        ]
    )
    source_key = f"S-{hashlib.sha1(key_basis.encode('utf-8')).hexdigest()[:8]}"
    return KnowledgebaseSource(
        source_key=source_key,
        source_title=source_title,
        text=chunk.text,
        metadata=metadata,
        similarity_score=chunk.similarity_score,
    )


def _format_source(source: KnowledgebaseSource, *, rank: int) -> str:
    lines = [
        f"[{source.source_key}] {source.source_title}",
        f"Rank: {rank}",
    ]
    for key, label in (
        ("source_type", "Source type"),
        ("document_id", "Document ID"),
        ("kb_service_document_id", "KB Service Document ID"),
        ("chunk_id", "Chunk ID"),
        ("chunk_index", "Chunk index"),
        ("source_date", "Source date"),
    ):
        if key in source.metadata and source.metadata[key] is not None:
            lines.append(f"{label}: {source.metadata[key]}")
    if source.similarity_score is not None:
        lines.append(f"Similarity: {source.similarity_score:.3f}")
    lines.append(f"Excerpt: {source.text}")
    return "\n".join(lines)


def _sanitize_source_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in metadata.items():
        if key in SENSITIVE_SOURCE_METADATA_KEYS:
            continue
        if isinstance(value, dict):
            sanitized[key] = _sanitize_source_metadata(value)
        else:
            sanitized[key] = value
    return sanitized
