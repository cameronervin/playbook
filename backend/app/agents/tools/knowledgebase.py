"""Reusable knowledge-base search tool factory for agent workflows."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

import structlog
from langchain.tools import ToolRuntime
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, ConfigDict, Field

from app.agents.runtime_context import AthleteChatRuntimeContext
from app.core.exceptions import KnowledgebaseError
from app.schemas.knowledgebase import KnowledgebaseResult, RetrievedChunk

logger = structlog.get_logger(__name__)
_KB_ORGANIZATION_ID: ContextVar[str | None] = ContextVar(
    "kb_organization_id",
    default=None,
)
_KB_CONVERSATION_ID: ContextVar[str | None] = ContextVar(
    "kb_conversation_id",
    default=None,
)
_KB_CONVERSATION_FILE_IDS: ContextVar[tuple[str, ...]] = ContextVar(
    "kb_conversation_file_ids",
    default=(),
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
        "athlete NIL, compliance, recruiting, reporting, academic support, team "
        "travel, Teamworks, extra-benefit, and process guidance. Use this before "
        "making unsupported policy or process claims, including questions about "
        "tutoring, study hall, absence letters, per diem, rides, meals, fees, "
        "memberships, lodging, services, or transportation benefits. If no "
        "returned source supports the answer, stop searching and answer "
        "unsupported."
    ),
    metadata_filter={"visibility_policy": {"scope": "all_athletes"}},
)


ATHLETE_CONVERSATION_FILE_TOOL_PROFILE = KnowledgebaseToolProfile(
    tool_name="search_conversation_files",
    description=(
        "Search ready uploaded files attached to the current athlete conversation. "
        "Use this only when ready uploaded files exist and the athlete asks about "
        "contracts, forms, documents, or conversation-specific file contents."
    ),
    no_results_message=(
        "No relevant uploaded conversation file context found. Stop using "
        "search_conversation_files for this answer."
    ),
    unavailable_message="Conversation file search temporarily unavailable.",
)


class KnowledgebaseSearchInput(BaseModel):
    """Arguments for official athlete KB search."""

    model_config = ConfigDict(extra="allow")

    query: str = Field(
        description=(
            "focused official policy or process search terms for the athlete's "
            "current NIL, compliance, recruiting, reporting, academic-support, "
            "team travel, Teamworks, extra-benefit, or department process "
            "question. Do not repeat an equivalent query in the same answer."
        )
    )
    max_docs: int | None = Field(
        default=None,
        ge=1,
        le=10,
        description=(
            "Use a small value, usually 3 to 5. Increase only when the question "
            "requires comparing multiple official sources."
        ),
    )
    score_threshold: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "Optional retrieval threshold. Lower only when the first focused "
            "search misses and one more broader search is justified."
        ),
    )


class ConversationFileSearchInput(BaseModel):
    """Arguments for private ready-file search."""

    model_config = ConfigDict(extra="allow")

    query: str = Field(
        description=(
            "Focused search terms for uploaded-file content. Use only when ready "
            "uploaded conversation files exist. Do not call this tool when ready "
            "file count is 0."
        )
    )
    max_docs: int | None = Field(
        default=None,
        ge=1,
        le=10,
        description=(
            "Usually 1 to 3 excerpts are enough for an uploaded-file answer."
        ),
    )
    score_threshold: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "Optional private-file retrieval threshold. Lower only for one "
            "broader retry after a focused uploaded-file search misses."
        ),
    )


@contextmanager
def knowledgebase_organization_context(organization_id: str) -> Iterator[None]:
    """Bind organization scope for KB tools invoked without LangChain config."""
    token = _KB_ORGANIZATION_ID.set(organization_id)
    try:
        yield
    finally:
        _KB_ORGANIZATION_ID.reset(token)


@contextmanager
def conversation_file_search_context(
    *,
    organization_id: str,
    conversation_id: str,
    file_ids: Sequence[str],
) -> Iterator[None]:
    """Bind trusted private file scope for conversation-file search tools."""
    organization_token = _KB_ORGANIZATION_ID.set(organization_id)
    conversation_token = _KB_CONVERSATION_ID.set(conversation_id)
    file_ids_token = _KB_CONVERSATION_FILE_IDS.set(
        tuple(str(file_id) for file_id in file_ids if str(file_id).strip())
    )
    try:
        yield
    finally:
        _KB_CONVERSATION_FILE_IDS.reset(file_ids_token)
        _KB_CONVERSATION_ID.reset(conversation_token)
        _KB_ORGANIZATION_ID.reset(organization_token)


def create_knowledgebase_search_tool(
    profile: KnowledgebaseToolProfile,
) -> StructuredTool:
    """Create a named KB search tool using a profile-specific model contract."""

    async def _search(
        query: str,
        runtime: ToolRuntime,
        max_docs: int | None = None,
        score_threshold: float | None = None,
        # LangChain injects runtime config only when the annotation is exactly RunnableConfig.
        config: RunnableConfig = None,
    ) -> str:
        runtime_config = _runtime_config(runtime, config)
        runtime_context = _runtime_context(runtime, tool_name=profile.tool_name)
        if runtime_context is None:
            return profile.unavailable_message
        kb_provider = runtime_context.knowledgebase_provider
        registry = runtime_context.source_registry
        organization_id = (
            _organization_id_from_config(runtime_config) or _KB_ORGANIZATION_ID.get()
        )
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


def create_conversation_file_search_tool(
    profile: KnowledgebaseToolProfile,
) -> StructuredTool:
    """Create a private conversation-file search tool with hidden scope."""

    async def _search(
        query: str,
        runtime: ToolRuntime,
        max_docs: int | None = None,
        score_threshold: float | None = None,
        # LangChain injects runtime config only when the annotation is exactly RunnableConfig.
        config: RunnableConfig = None,
    ) -> str:
        runtime_config = _runtime_config(runtime, config)
        runtime_context = _runtime_context(runtime, tool_name=profile.tool_name)
        if runtime_context is None:
            return profile.unavailable_message
        kb_provider = runtime_context.knowledgebase_provider
        registry = runtime_context.source_registry
        organization_id = (
            _organization_id_from_config(runtime_config) or _KB_ORGANIZATION_ID.get()
        )
        conversation_id = (
            _conversation_id_from_config(runtime_config) or _KB_CONVERSATION_ID.get()
        )
        file_ids = _conversation_file_ids_from_config(runtime_config) or list(
            _KB_CONVERSATION_FILE_IDS.get()
        )
        if not organization_id or not conversation_id:
            logger.warning(
                "agent_conversation_file_tool_missing_scope",
                tool_name=profile.tool_name,
                has_organization=bool(organization_id),
                has_conversation=bool(conversation_id),
            )
            return profile.unavailable_message
        if not file_ids:
            return (
                "No ready uploaded conversation files are available. Stop using "
                "search_conversation_files for this answer."
            )

        resolved_max_docs = max_docs or profile.default_max_docs
        resolved_score_threshold = (
            score_threshold
            if score_threshold is not None
            else profile.default_score_threshold
        )

        logger.info(
            "agent_conversation_file_tool_request",
            tool_name=profile.tool_name,
            max_docs=resolved_max_docs,
            score_threshold=resolved_score_threshold,
            file_count=len(file_ids),
        )

        try:
            result = await kb_provider.search_conversation_files(
                query=query,
                organization_id=organization_id,
                conversation_id=conversation_id,
                file_ids=file_ids,
                max_docs=resolved_max_docs,
                score_threshold=resolved_score_threshold,
                configuration_id=profile.configuration_id,
            )
        except KnowledgebaseError as exc:
            logger.warning(
                "agent_conversation_file_tool_unavailable",
                tool_name=profile.tool_name,
                error_type=type(exc).__name__,
            )
            return profile.unavailable_message
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "agent_conversation_file_tool_unexpected_error",
                tool_name=profile.tool_name,
                error_type=type(exc).__name__,
                exc_info=True,
            )
            return profile.unavailable_message

        return _format_conversation_file_search_result(
            result,
            profile=profile,
            registry=registry,
        )

    return StructuredTool.from_function(
        coroutine=_search,
        name=profile.tool_name,
        description=profile.description,
        args_schema=ConversationFileSearchInput,
    )


def _runtime_config(
    runtime: ToolRuntime,
    config: RunnableConfig | None,
) -> RunnableConfig | None:
    if config is not None:
        return config
    runtime_config = getattr(runtime, "config", None)
    return runtime_config if isinstance(runtime_config, Mapping) else None


def _runtime_context(
    runtime: ToolRuntime,
    *,
    tool_name: str,
) -> AthleteChatRuntimeContext | None:
    context = getattr(runtime, "context", None)
    if isinstance(context, AthleteChatRuntimeContext):
        return context
    logger.warning(
        "agent_kb_tool_missing_runtime_context",
        tool_name=tool_name,
        context_type=type(context).__name__ if context is not None else None,
    )
    return None


def _organization_id_from_config(config: RunnableConfig | None) -> str | None:
    configurable: Mapping[str, Any] | None = None
    if isinstance(config, Mapping):
        raw_configurable = config.get("configurable")
        if isinstance(raw_configurable, Mapping):
            configurable = raw_configurable
    value = configurable.get("organization_id") if configurable else None
    return str(value) if value else None


def _conversation_id_from_config(config: RunnableConfig | None) -> str | None:
    configurable = _configurable_mapping(config)
    value = configurable.get("conversation_id") if configurable else None
    return str(value) if value else None


def _conversation_file_ids_from_config(config: RunnableConfig | None) -> list[str]:
    configurable = _configurable_mapping(config)
    if not configurable:
        return []
    return _string_list(configurable.get("conversation_file_ready_file_ids"))


def _configurable_mapping(config: RunnableConfig | None) -> Mapping[str, Any] | None:
    if not isinstance(config, Mapping):
        return None
    raw_configurable = config.get("configurable")
    return raw_configurable if isinstance(raw_configurable, Mapping) else None


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


def _format_conversation_file_search_result(
    result: KnowledgebaseResult,
    *,
    profile: KnowledgebaseToolProfile,
    registry: SourceRegistry,
) -> str:
    if result.zero_hit or not result.sources:
        return profile.no_results_message

    sources = register_knowledgebase_sources(result, registry=registry)
    return format_conversation_file_context(sources)


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
        if source.similarity_score is not None:
            lines.append(f"Relevance: {source.similarity_score:.3f}")
        lines.append(f"Excerpt: {source.text}")
        sections.append("\n".join(lines))

    return "\n\n".join(
        [
            "## Conversation File Context",
            (
                "Use the excerpts below as evidence for this conversation only. "
                "Uploaded file summaries are orientation only and must not be "
                "cited as evidence."
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
        lines.append(f"Relevance: {source.similarity_score:.3f}")
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


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, Sequence):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []
