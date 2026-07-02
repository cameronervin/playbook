"""Executor-backed eval adapters for Playbook production workflows.

The eval runner only knows about ``GraphRun``. This module is the small bridge
that can invoke the real worker executors when DB fixtures exist, while staying
easy to unit-test with fake graph providers, fake models, and lightweight
session doubles.
"""

from __future__ import annotations

import inspect
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import yaml
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.agents.tools.knowledgebase import register_knowledgebase_sources
from app.infrastructure.knowledgebase.providers.base import (
    DEFAULT_KB_MAX_DOCS,
    DEFAULT_KB_SCORE_THRESHOLD,
    BaseKnowledgebaseProvider,
)
from app.schemas.knowledgebase import KnowledgebaseResult, RetrievedChunk
from evals.core.types import GraphRun

ItemSeeder = Callable[..., Mapping[str, Any] | Awaitable[Mapping[str, Any] | None] | None]
ProviderFactory = Callable[[], Any]
SessionFactory = Callable[[], Any]

_DATASET_DIR = Path(__file__).resolve().parents[1] / "datasets"
_KB_FIXTURE_PATH = _DATASET_DIR / "_fixtures" / "playbook_kb_sources.yaml"
_ATHLETE_REQUIRED_FIELDS = (
    "task_id",
    "conversation_id",
    "athlete_user_id",
    "user_message_id",
    "assistant_message_id",
    "organization_id",
)
_ADMIN_REQUIRED_FIELDS = (
    "task_id",
    "session_id",
    "admin_user_id",
    "user_message_id",
    "assistant_message_id",
    "organization_id",
    "window_start",
    "window_end",
)
_TITLE_REQUIRED_FIELDS = _ATHLETE_REQUIRED_FIELDS


@dataclass(frozen=True, slots=True)
class RetrievalRecord:
    """One KB retrieval request plus the result returned to the executor."""

    tool_name: str
    request: dict[str, Any]
    result: KnowledgebaseResult

    @property
    def documents(self) -> list[str]:
        """Retrieved context texts in KB-service order."""
        return [chunk.text for chunk in self.result.sources if chunk.text]

    @property
    def sources(self) -> list[dict[str, Any]]:
        """JSON-safe source metadata for trajectory inspection."""
        return [
            {
                "source_key": source.source_key,
                "source_title": source.source_title,
                "text": source.text,
                "metadata": dict(source.metadata or {}),
                "similarity_score": source.similarity_score,
            }
            for source in _registered_sources(self.result)
        ]


class RecordingKnowledgebaseProvider(BaseKnowledgebaseProvider):
    """KB provider wrapper/test double that records admin and file searches."""

    def __init__(
        self,
        *,
        inner: Any | None = None,
        admin_upload_chunks: Sequence[RetrievedChunk] | None = None,
        conversation_file_chunks: Sequence[RetrievedChunk] | None = None,
    ) -> None:
        self.inner = inner
        self._admin_upload_chunks = (
            list(admin_upload_chunks) if admin_upload_chunks is not None else None
        )
        self._conversation_file_chunks = (
            list(conversation_file_chunks)
            if conversation_file_chunks is not None
            else None
        )
        self.records: list[RetrievalRecord] = []

    @property
    def provider_name(self) -> str:
        inner_name = getattr(self.inner, "provider_name", None)
        return f"recording:{inner_name}" if inner_name else "recording"

    async def search(
        self,
        query: str,
        organization_id: UUID | str,
        max_docs: int = DEFAULT_KB_MAX_DOCS,
        score_threshold: float = DEFAULT_KB_SCORE_THRESHOLD,
        metadata_filter: dict | None = None,
        configuration_id: str | None = None,
    ) -> KnowledgebaseResult:
        result = await self._resolve_result(
            tool_name="search",
            chunks=self._admin_upload_chunks,
            delegate_name="search",
            query=query,
            organization_id=organization_id,
            max_docs=max_docs,
            score_threshold=score_threshold,
            metadata_filter=metadata_filter,
            configuration_id=configuration_id,
        )
        self._record(
            "search",
            result,
            query=query,
            organization_id=organization_id,
            max_docs=max_docs,
            score_threshold=score_threshold,
            metadata_filter=metadata_filter,
            configuration_id=configuration_id,
        )
        return result

    async def search_admin_uploads(
        self,
        query: str,
        organization_id: UUID | str,
        max_docs: int = DEFAULT_KB_MAX_DOCS,
        score_threshold: float = DEFAULT_KB_SCORE_THRESHOLD,
        metadata_filter: dict | None = None,
        configuration_id: str | None = None,
    ) -> KnowledgebaseResult:
        result = await self._resolve_result(
            tool_name="search_admin_uploads",
            chunks=self._admin_upload_chunks,
            delegate_name="search_admin_uploads",
            query=query,
            organization_id=organization_id,
            max_docs=max_docs,
            score_threshold=score_threshold,
            metadata_filter=metadata_filter,
            configuration_id=configuration_id,
        )
        self._record(
            "search_admin_uploads",
            result,
            query=query,
            organization_id=organization_id,
            max_docs=max_docs,
            score_threshold=score_threshold,
            metadata_filter=metadata_filter,
            configuration_id=configuration_id,
        )
        return result

    async def search_conversation_files(
        self,
        query: str,
        organization_id: UUID | str,
        conversation_id: UUID | str,
        file_ids: list[UUID | str] | None = None,
        max_docs: int = DEFAULT_KB_MAX_DOCS,
        score_threshold: float = DEFAULT_KB_SCORE_THRESHOLD,
        configuration_id: str | None = None,
    ) -> KnowledgebaseResult:
        chunks = _filter_conversation_file_chunks(
            self._conversation_file_chunks,
            conversation_id=conversation_id,
            file_ids=file_ids,
        )
        result = await self._resolve_result(
            tool_name="search_conversation_files",
            chunks=chunks,
            delegate_name="search_conversation_files",
            query=query,
            organization_id=organization_id,
            conversation_id=conversation_id,
            file_ids=file_ids,
            max_docs=max_docs,
            score_threshold=score_threshold,
            configuration_id=configuration_id,
        )
        self._record(
            "search_conversation_files",
            result,
            query=query,
            organization_id=organization_id,
            conversation_id=conversation_id,
            file_ids=[str(file_id) for file_id in file_ids or []],
            max_docs=max_docs,
            score_threshold=score_threshold,
            configuration_id=configuration_id,
        )
        return result

    async def health_check(self) -> bool:
        if self.inner is not None and hasattr(self.inner, "health_check"):
            return bool(await self.inner.health_check())
        return True

    async def resolve_configuration(self) -> str:
        if self.inner is not None and hasattr(self.inner, "resolve_configuration"):
            return str(await self.inner.resolve_configuration())
        return "recording"

    async def close(self) -> None:
        if self.inner is not None and hasattr(self.inner, "close"):
            await self.inner.close()

    def __getattr__(self, name: str) -> Any:
        if self.inner is None:
            raise AttributeError(name)
        return getattr(self.inner, name)

    async def _resolve_result(
        self,
        *,
        tool_name: str,
        chunks: Sequence[RetrievedChunk] | None,
        delegate_name: str,
        **kwargs: Any,
    ) -> KnowledgebaseResult:
        if chunks is not None:
            return _knowledgebase_result_from_chunks(
                query=str(kwargs["query"]),
                chunks=chunks,
                max_docs=_int_or_default(kwargs.get("max_docs"), DEFAULT_KB_MAX_DOCS),
                score_threshold=_float_or_default(
                    kwargs.get("score_threshold"),
                    DEFAULT_KB_SCORE_THRESHOLD,
                ),
            )
        if self.inner is not None and hasattr(self.inner, delegate_name):
            return await getattr(self.inner, delegate_name)(**kwargs)
        return KnowledgebaseResult(
            query=str(kwargs["query"]),
            context="",
            sources=[],
            confidence=None,
            zero_hit=True,
            latency_ms=0,
        )

    def _record(self, tool_name: str, result: KnowledgebaseResult, **request: Any) -> None:
        self.records.append(
            RetrievalRecord(
                tool_name=tool_name,
                request=_jsonish_mapping(request),
                result=result,
            )
        )


class RecordingStreamService:
    """Drop-in stream service wrapper that captures answer chunks and events."""

    def __init__(self, inner: Any | None = None) -> None:
        self.inner = inner
        self.progress_events: list[dict[str, Any]] = []
        self.chunk_events: list[dict[str, Any]] = []
        self.complete_events: list[dict[str, Any]] = []
        self.langgraph_parts: list[dict[str, Any]] = []
        self.error_events: list[dict[str, Any]] = []

    @property
    def answer_text(self) -> str:
        return "".join(str(event["content"]) for event in self.chunk_events)

    async def publish_progress(
        self,
        task_id: str,
        *,
        status: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        self.progress_events.append(
            {"task_id": task_id, "status": status, "metadata": metadata or {}}
        )
        if self.inner is not None:
            return await self.inner.publish_progress(
                task_id,
                status=status,
                metadata=metadata,
            )
        return _stream_id("progress", len(self.progress_events))

    async def publish_chunk(
        self,
        task_id: str,
        *,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        self.chunk_events.append(
            {"task_id": task_id, "content": content, "metadata": metadata or {}}
        )
        if self.inner is not None:
            return await self.inner.publish_chunk(
                task_id,
                content=content,
                metadata=metadata,
            )
        return _stream_id("chunk", len(self.chunk_events))

    async def publish_complete(
        self,
        task_id: str,
        *,
        data: dict[str, Any] | None = None,
    ) -> str:
        self.complete_events.append({"task_id": task_id, "data": data or {}})
        if self.inner is not None:
            return await self.inner.publish_complete(task_id, data=data)
        return _stream_id("complete", len(self.complete_events))

    async def publish_error(
        self,
        task_id: str,
        *,
        message: str,
        code: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        self.error_events.append(
            {
                "task_id": task_id,
                "message": message,
                "code": code,
                "metadata": metadata or {},
            }
        )
        if self.inner is not None:
            return await self.inner.publish_error(
                task_id,
                message=message,
                code=code,
                metadata=metadata,
            )
        return _stream_id("error", len(self.error_events))

    async def publish_langgraph_part(
        self,
        task_id: str,
        part: dict[str, Any],
    ) -> str | None:
        self.langgraph_parts.append({"task_id": task_id, "part": part})
        if self.inner is not None:
            return await self.inner.publish_langgraph_part(task_id, part)
        return _stream_id("langgraph", len(self.langgraph_parts))


def graph_run_events(
    *,
    kb_provider: RecordingKnowledgebaseProvider | None = None,
    citations: Sequence[Any] | None = None,
    admin_references: Sequence[Any] | None = None,
    extra_events: Sequence[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Build trajectory events that existing judges can consume."""
    events: list[dict[str, Any]] = []
    if kb_provider is not None:
        events.extend(_retriever_event(record) for record in kb_provider.records)
    if citations:
        events.append({"citations": {"sources": _jsonish_sequence(citations)}})
    if admin_references:
        events.append(
            {"admin_references": {"references": _jsonish_sequence(admin_references)}}
        )
    if extra_events:
        events.extend(extra_events)
    return events


def build_graph_run(
    *,
    input_data: Any,
    executor_output: Any,
    kb_provider: RecordingKnowledgebaseProvider | None = None,
    stream_service: RecordingStreamService | None = None,
    citations: Sequence[Any] | None = None,
    admin_references: Sequence[Any] | None = None,
    extra_events: Sequence[dict[str, Any]] | None = None,
) -> GraphRun:
    """Normalize an executor result into the eval harness ``GraphRun`` shape."""
    output = _output_mapping(executor_output)
    answer_text = stream_service.answer_text if stream_service is not None else ""
    if answer_text and "answer" not in output:
        output["answer"] = answer_text
    resolved_citations = citations if citations is not None else _sequence_or_none(
        output.get("citations")
    )
    resolved_references = (
        admin_references
        if admin_references is not None
        else _sequence_or_none(output.get("references"))
    )
    return GraphRun(
        input=input_data,
        output=output,
        events=graph_run_events(
            kb_provider=kb_provider,
            citations=resolved_citations,
            admin_references=resolved_references,
            extra_events=extra_events,
        ),
        trace_id=None,
    )


def make_athlete_chat_executor_adapter(
    *,
    session: Any | None = None,
    session_factory: SessionFactory | None = None,
    settings: Any | None = None,
    chat_model: Any | None = None,
    title_model: Any | None = None,
    knowledgebase_provider: Any | None = None,
    knowledgebase_provider_factory: ProviderFactory | None = None,
    stream_service: Any | None = None,
    checkpointer: Any | None = None,
    graph_provider: Any | None = None,
    title_executor_factory: Any | None = None,
    item_seeder: ItemSeeder | None = None,
    executor_cls: type[Any] | None = None,
) -> Callable[..., Awaitable[GraphRun]]:
    """Return an adapter that runs ``AthleteChatExecutor`` for one dataset item."""

    async def adapter(*, item: Any) -> GraphRun:
        item_input = _mapping_item_input(item)
        resolved_settings = settings or _default_settings()
        async with _session_scope(
            session=session,
            session_factory=session_factory,
            settings=resolved_settings,
        ) as active_session:
            run_input = await _seeded_input(
                item_input,
                session=active_session,
                item_seeder=item_seeder,
            )
            if _missing_fields(run_input, _ATHLETE_REQUIRED_FIELDS):
                run_input = {
                    **run_input,
                    **await seed_athlete_chat_eval_item(
                        item_input=run_input,
                        session=active_session,
                    ),
                }
            kb_recorder = _recording_kb_provider(
                knowledgebase_provider=knowledgebase_provider,
                knowledgebase_provider_factory=knowledgebase_provider_factory,
                settings=resolved_settings,
                item_input=run_input,
            )
            stream_recorder = _recording_stream_service(stream_service)
            executor_type = executor_cls or _athlete_chat_executor_cls()
            kwargs: dict[str, Any] = {
                "session": active_session,
                "chat_model": chat_model or _default_chat_model(resolved_settings),
                "title_model": title_model,
                "knowledgebase_provider": kb_recorder,
                "stream_service": stream_recorder,
                "settings": resolved_settings,
                "checkpointer": checkpointer,
                "graph_provider": graph_provider,
            }
            if title_executor_factory is not None:
                kwargs["title_executor_factory"] = title_executor_factory
            executor = executor_type(**kwargs)
            output = await executor.execute(**_athlete_execute_kwargs(run_input))
            persisted_output, persisted_citations = await _athlete_persisted_evidence(
                session=active_session,
                assistant_message_id=run_input["assistant_message_id"],
            )
            return build_graph_run(
                input_data=run_input,
                executor_output={**_output_mapping(output), **persisted_output},
                kb_provider=kb_recorder,
                stream_service=stream_recorder,
                citations=persisted_citations or None,
            )

    return adapter


def make_admin_chat_executor_adapter(
    *,
    session: Any | None = None,
    session_factory: SessionFactory | None = None,
    settings: Any | None = None,
    chat_model: Any | None = None,
    stream_service: Any | None = None,
    checkpointer: Any | None = None,
    graph_provider: Any | None = None,
    item_seeder: ItemSeeder | None = None,
    executor_cls: type[Any] | None = None,
) -> Callable[..., Awaitable[GraphRun]]:
    """Return an adapter that runs ``AdminChatExecutor`` for one dataset item."""

    async def adapter(*, item: Any) -> GraphRun:
        item_input = _mapping_item_input(item)
        resolved_settings = settings or _default_settings()
        async with _session_scope(
            session=session,
            session_factory=session_factory,
            settings=resolved_settings,
        ) as active_session:
            run_input = await _seeded_input(
                item_input,
                session=active_session,
                item_seeder=item_seeder,
            )
            if _missing_fields(run_input, _ADMIN_REQUIRED_FIELDS):
                run_input = {
                    **run_input,
                    **await seed_admin_chat_eval_item(
                        item_input=run_input,
                        session=active_session,
                    ),
                }
            stream_recorder = _recording_stream_service(stream_service)
            executor_type = executor_cls or _admin_chat_executor_cls()
            executor = executor_type(
                session=active_session,
                chat_model=chat_model or _default_chat_model(resolved_settings),
                stream_service=stream_recorder,
                settings=resolved_settings,
                checkpointer=checkpointer,
                graph_provider=graph_provider,
            )
            output = await executor.execute(**_admin_execute_kwargs(run_input))
            return build_graph_run(
                input_data=run_input,
                executor_output=output,
                stream_service=stream_recorder,
            )

    return adapter


def make_conversation_title_executor_adapter(
    *,
    session: Any | None = None,
    session_factory: SessionFactory | None = None,
    settings: Any | None = None,
    title_model: Any | None = None,
    checkpointer: Any | None = None,
    graph_provider: Any | None = None,
    item_seeder: ItemSeeder | None = None,
    executor_cls: type[Any] | None = None,
) -> Callable[..., Awaitable[GraphRun]]:
    """Return an adapter that runs ``ConversationTitleExecutor`` per item."""

    async def adapter(*, item: Any) -> GraphRun:
        item_input = _mapping_item_input(item)
        resolved_settings = settings or _default_settings()
        async with _session_scope(
            session=session,
            session_factory=session_factory,
            settings=resolved_settings,
        ) as active_session:
            run_input = await _seeded_input(
                item_input,
                session=active_session,
                item_seeder=item_seeder,
            )
            if _missing_fields(run_input, _TITLE_REQUIRED_FIELDS):
                run_input = {
                    **run_input,
                    **await seed_conversation_title_eval_item(
                        item_input=run_input,
                        session=active_session,
                    ),
                }
            executor_type = executor_cls or _conversation_title_executor_cls()
            executor = executor_type(
                session=active_session,
                title_model=title_model or _default_chat_model(resolved_settings),
                settings=resolved_settings,
                checkpointer=checkpointer,
                graph_provider=graph_provider,
            )
            title = await executor.execute(**_title_execute_kwargs(run_input))
            return build_graph_run(
                input_data=run_input,
                executor_output={"conversation_title": title},
            )

    return adapter


def _retriever_event(record: RetrievalRecord) -> dict[str, Any]:
    return {
        "retriever": {
            "tool_name": record.tool_name,
            "query": record.request.get("query"),
            "documents": record.documents,
            "sources": record.sources,
        }
    }


def _registered_sources(result: KnowledgebaseResult) -> list[Any]:
    registry: dict[str, Any] = {}
    return register_knowledgebase_sources(result, registry=registry)


def _knowledgebase_result_from_chunks(
    *,
    query: str,
    chunks: Sequence[RetrievedChunk],
    max_docs: int,
    score_threshold: float,
) -> KnowledgebaseResult:
    filtered = [
        chunk
        for chunk in chunks
        if chunk.similarity_score is None or chunk.similarity_score >= score_threshold
    ][:max_docs]
    return KnowledgebaseResult(
        query=query,
        context="\n\n".join(chunk.text for chunk in filtered),
        sources=list(filtered),
        confidence=filtered[0].similarity_score if filtered else None,
        zero_hit=not filtered,
        latency_ms=0,
    )


def _filter_conversation_file_chunks(
    chunks: Sequence[RetrievedChunk] | None,
    *,
    conversation_id: UUID | str,
    file_ids: Sequence[UUID | str] | None,
) -> Sequence[RetrievedChunk] | None:
    if chunks is None:
        return None
    conversation_key = str(conversation_id)
    file_keys = {str(file_id) for file_id in file_ids or []}
    return [
        chunk
        for chunk in chunks
        if str(chunk.metadata.get("conversation_id", conversation_key)) == conversation_key
        and (
            not file_keys
            or str(chunk.metadata.get("conversation_file_id", "")) in file_keys
        )
    ]


def _mapping_item_input(item: Any) -> dict[str, Any]:
    if isinstance(item, Mapping):
        raw_input = item.get("input")
    else:
        raw_input = getattr(item, "input", None)
    if not isinstance(raw_input, Mapping):
        raise TypeError("Eval executor adapters require mapping item.input")
    return dict(raw_input)


async def _seeded_input(
    item_input: dict[str, Any],
    *,
    session: Any,
    item_seeder: ItemSeeder | None,
) -> dict[str, Any]:
    if item_seeder is None:
        return dict(item_input)
    seeded = await _maybe_await(item_seeder(item_input=item_input, session=session))
    if seeded is None:
        return dict(item_input)
    if not isinstance(seeded, Mapping):
        raise TypeError("Eval item seeder must return a mapping or None")
    return {**item_input, **dict(seeded)}


async def _athlete_persisted_evidence(
    *,
    session: Any,
    assistant_message_id: Any,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Read persisted athlete citations after executor completion for eval scoring."""

    if not hasattr(session, "execute"):
        return {}, []

    from app.repositories.conversations import (  # noqa: PLC0415
        ConversationMessageRepository,
        MessageCitationRepository,
    )

    assistant_id = _uuid_value(assistant_message_id, "assistant_message_id")
    message = await ConversationMessageRepository(session).get(assistant_id)
    if message is None:
        return {}, []

    metadata = dict(getattr(message, "message_metadata", {}) or {})
    source_keys = [
        str(source_key)
        for source_key in metadata.get("source_keys", [])
        if str(source_key).strip()
    ]
    output: dict[str, Any] = {}
    if source_keys:
        output["cited_source_keys"] = source_keys
    if getattr(message, "content", "") and not output.get("answer"):
        output["answer"] = message.content

    citations = await MessageCitationRepository(session).list_by_message(assistant_id)
    citation_events: list[dict[str, Any]] = []
    for index, citation in enumerate(citations):
        event: dict[str, Any] = {}
        if index < len(source_keys):
            event["source_key"] = source_keys[index]
        if getattr(citation, "source_title", None):
            event["source_title"] = citation.source_title
        if getattr(citation, "document_id", None) is not None:
            event["document_id"] = str(citation.document_id)
        if getattr(citation, "chunk_id", None) is not None:
            event["chunk_id"] = str(citation.chunk_id)
        source_metadata = dict(getattr(citation, "source_metadata", {}) or {})
        event.update(_jsonish_mapping(source_metadata))
        if event:
            citation_events.append(event)

    if not citation_events and source_keys:
        citation_events = [{"source_key": source_key} for source_key in source_keys]

    return output, citation_events


@asynccontextmanager
async def _session_scope(
    *,
    session: Any | None,
    session_factory: SessionFactory | None,
    settings: Any,
) -> AsyncIterator[Any]:
    if session is not None:
        yield session
        return

    factory = session_factory or _default_session_factory(settings)
    candidate = factory()
    if hasattr(candidate, "__aenter__") and hasattr(candidate, "__aexit__"):
        async with candidate as active_session:
            yield active_session
        return

    active_session = await _maybe_await(candidate)
    try:
        yield active_session
    finally:
        close = getattr(active_session, "close", None)
        if close is not None:
            await _maybe_await(close())


def _recording_kb_provider(
    *,
    knowledgebase_provider: Any | None,
    knowledgebase_provider_factory: ProviderFactory | None,
    settings: Any,
    item_input: Mapping[str, Any] | None = None,
) -> RecordingKnowledgebaseProvider:
    provider = knowledgebase_provider
    if provider is None:
        if knowledgebase_provider_factory is not None:
            provider = knowledgebase_provider_factory()
        elif item_input is not None and "retrieved_source_ids" in item_input:
            chunks = _fixture_chunks_for_item(item_input)
            return RecordingKnowledgebaseProvider(
                admin_upload_chunks=[
                    chunk
                    for chunk in chunks
                    if chunk.metadata.get("source_type") != "conversation_file"
                ],
                conversation_file_chunks=[
                    chunk
                    for chunk in chunks
                    if chunk.metadata.get("source_type") == "conversation_file"
                ],
            )
        else:
            from app.infrastructure.knowledgebase import (  # noqa: PLC0415
                get_kb_provider,
            )

            provider = get_kb_provider(app_settings=settings)
    if isinstance(provider, RecordingKnowledgebaseProvider):
        return provider
    return RecordingKnowledgebaseProvider(inner=provider)


async def seed_athlete_chat_eval_item(
    *,
    item_input: Mapping[str, Any],
    session: Any,
) -> dict[str, Any]:
    """Seed the minimal persisted athlete-chat state for one portable eval case."""

    organization, athlete = await _create_eval_org_and_user(
        session=session,
        role="athlete",
        email_prefix="eval-athlete",
        provider_prefix="eval-athlete",
    )
    from app.repositories.conversations import (  # noqa: PLC0415
        ConversationFileRepository,
        ConversationMessageRepository,
        ConversationRepository,
    )

    question = _prompt_text(item_input)
    task_id = f"eval-athlete-{uuid4().hex}"
    conversation = await ConversationRepository(session).create(
        organization_id=organization.id,
        athlete_id=athlete.id,
        title=None,
    )
    message_repo = ConversationMessageRepository(session)
    user_message = await message_repo.create(
        conversation_id=conversation.id,
        role="user",
        content=question,
    )
    assistant_message = await message_repo.create(
        conversation_id=conversation.id,
        role="assistant",
        content="",
        status="streaming",
        metadata={
            "task_id": task_id,
            "user_message_id": str(user_message.id),
            "is_first_turn": True,
            "provisional_title": _provisional_title(question),
        },
    )
    attached_file_ids: list[str] = []
    if _has_conversation_file_sources(item_input):
        file = await ConversationFileRepository(session).create(
            conversation_id=conversation.id,
            uploaded_by=athlete.id,
            filename="eval-upload.txt",
            content_type="text/plain",
            size_bytes=max(len(question), 1),
            storage_key=f"eval/{conversation.id}/eval-upload.txt",
            message_id=user_message.id,
            extraction_status="ready",
            extracted_char_count=max(len(question), 1),
            extraction_metadata={"source": "eval_fixture"},
        )
        file.chunk_count = max(1, len(_fixture_chunks_for_item(item_input)))
        attached_file_ids.append(str(file.id))
        await session.flush()

    return {
        "task_id": task_id,
        "conversation_id": str(conversation.id),
        "athlete_user_id": str(athlete.id),
        "user_message_id": str(user_message.id),
        "assistant_message_id": str(assistant_message.id),
        "organization_id": str(organization.id),
        "attached_file_ids": attached_file_ids,
    }


async def seed_conversation_title_eval_item(
    *,
    item_input: Mapping[str, Any],
    session: Any,
) -> dict[str, Any]:
    """Seed a title-eligible first-turn assistant message for one eval case."""

    from app.repositories.conversations import (  # noqa: PLC0415
        ConversationMessageRepository,
    )

    seeded = await seed_athlete_chat_eval_item(item_input=item_input, session=session)
    message_repo = ConversationMessageRepository(session)
    assistant_message = await message_repo.get(UUID(str(seeded["assistant_message_id"])))
    if assistant_message is not None:
        await message_repo.update_status_and_content(
            assistant_message,
            status="complete",
            content="I can help with that.",
            metadata={
                **assistant_message.message_metadata,
                "task_id": seeded["task_id"],
                "user_message_id": seeded["user_message_id"],
                "is_first_turn": True,
                "provisional_title": _provisional_title(_prompt_text(item_input)),
            },
        )
    return seeded


async def seed_admin_chat_eval_item(
    *,
    item_input: Mapping[str, Any],
    session: Any,
) -> dict[str, Any]:
    """Seed admin-chat state and anonymized analytics rows from one eval snapshot."""

    organization, admin = await _create_eval_org_and_user(
        session=session,
        role="admin",
        email_prefix="eval-admin",
        provider_prefix="eval-admin",
    )
    from app.repositories.admin_chat import (  # noqa: PLC0415
        AdminChatMessageRepository,
        AdminChatSessionRepository,
    )

    window_start, window_end = _window_bounds(item_input)
    task_id = f"eval-admin-{uuid4().hex}"
    chat_session = await AdminChatSessionRepository(session).create(
        organization_id=organization.id,
        created_by=admin.id,
        title="Eval admin chat",
        context_window_start=window_start,
        context_window_end=window_end,
    )
    message_repo = AdminChatMessageRepository(session)
    user_message = await message_repo.create(
        session_id=chat_session.id,
        role="user",
        content=_prompt_text(item_input),
    )
    assistant_message = await message_repo.create(
        session_id=chat_session.id,
        role="assistant",
        content="",
        status="streaming",
        metadata={
            "task_id": task_id,
            "user_message_id": str(user_message.id),
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
        },
    )
    analytics_refs = await _seed_admin_snapshot_rows(
        session=session,
        organization_id=organization.id,
        window_start=window_start,
        window_end=window_end,
        snapshot=_mapping_or_empty(item_input.get("snapshot")),
    )
    insight_refs = await _seed_dashboard_insight_refs(
        session=session,
        organization_id=organization.id,
        admin_user_id=admin.id,
        window_start=window_start,
        window_end=window_end,
        item_input=item_input,
    )
    allowed_references = [
        {"type": "metric", "id": "analytics.summary"},
        *analytics_refs,
        *insight_refs,
    ]
    return {
        "task_id": task_id,
        "session_id": str(chat_session.id),
        "admin_user_id": str(admin.id),
        "user_message_id": str(user_message.id),
        "assistant_message_id": str(assistant_message.id),
        "organization_id": str(organization.id),
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "allowed_references": allowed_references,
    }


def _missing_fields(mapping: Mapping[str, Any], field_names: Sequence[str]) -> list[str]:
    return [field_name for field_name in field_names if mapping.get(field_name) in (None, "")]


async def _create_eval_org_and_user(
    *,
    session: Any,
    role: str,
    email_prefix: str,
    provider_prefix: str,
) -> tuple[Any, Any]:
    from app.repositories.identity import (  # noqa: PLC0415
        OrganizationRepository,
        UserRepository,
    )

    nonce = uuid4().hex
    organization = await OrganizationRepository(session).create(
        name="Playbook Eval Athletics",
        slug=f"playbook-eval-{nonce[:12]}",
    )
    user = await UserRepository(session).create(
        organization_id=organization.id,
        email=f"{email_prefix}-{nonce}@example.test",
        name="Eval User",
        auth_provider="eval",
        provider_subject=f"{provider_prefix}-{nonce}",
        role=role,
        sport_team="Evaluation",
    )
    return organization, user


def _prompt_text(item_input: Mapping[str, Any]) -> str:
    for key in ("question", "query", "prompt"):
        value = item_input.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "Evaluation prompt"


def _provisional_title(question: str) -> str:
    words = [word.strip(".,?!:;()[]{}\"'").title() for word in question.split()]
    kept = [word for word in words if word][:6]
    return " ".join(kept) or "Evaluation Conversation"


def _mapping_or_empty(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _window_bounds(item_input: Mapping[str, Any]) -> tuple[datetime, datetime]:
    explicit_start = _datetime_or_none(item_input.get("window_start"))
    explicit_end = _datetime_or_none(item_input.get("window_end"))
    if explicit_start is not None and explicit_end is not None:
        return explicit_start, explicit_end

    now = datetime.now(UTC)
    window = str(item_input.get("window") or "last_7_days").strip().lower()
    if window == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start, now
    if window in {"last_30_days", "30d"}:
        return now - timedelta(days=30), now
    return now - timedelta(days=7), now


def _datetime_or_none(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


async def _seed_admin_snapshot_rows(
    *,
    session: Any,
    organization_id: UUID,
    window_start: datetime,
    window_end: datetime,
    snapshot: Mapping[str, Any],
) -> list[dict[str, str]]:
    query_volume = _positive_int(snapshot.get("query_volume"))
    if query_volume <= 0:
        return []

    from app.repositories.conversations import (  # noqa: PLC0415
        ConversationMessageRepository,
        ConversationRepository,
    )
    from app.repositories.identity import UserRepository  # noqa: PLC0415

    athlete = await UserRepository(session).create(
        organization_id=organization_id,
        email=f"eval-analytics-athlete-{uuid4().hex}@example.test",
        name="Eval Athlete",
        auth_provider="eval",
        provider_subject=f"eval-analytics-athlete-{uuid4().hex}",
        role="athlete",
        sport_team="Evaluation",
    )
    conversation = await ConversationRepository(session).create(
        organization_id=organization_id,
        athlete_id=athlete.id,
        title="Eval analytics source",
    )
    message_repo = ConversationMessageRepository(session)
    topics = _label_slots(snapshot.get("top_topics"), query_volume, fallback="other")
    risk_labels_by_index = _risk_labels_by_index(snapshot.get("risk_counts"), query_volume)
    unanswered_count = min(_positive_int(snapshot.get("unanswered_count")), query_volume)
    created_at = window_start + ((window_end - window_start) / 2)

    refs: list[dict[str, str]] = []
    for index in range(query_volume):
        topic = topics[index]
        question = f"Synthetic {topic} eval question {index + 1}"
        user_message = await message_repo.create(
            conversation_id=conversation.id,
            role="user",
            content=question,
            created_at=created_at,
        )
        answer_type = "unsupported" if index < unanswered_count else "grounded_answer"
        await message_repo.create(
            conversation_id=conversation.id,
            role="assistant",
            content="" if answer_type == "unsupported" else "Synthetic eval response.",
            status="complete",
            safety_outcome=answer_type,
            topic_labels=[topic] if topic != "other" else [],
            risk_labels=risk_labels_by_index[index],
            metadata={
                "answer_type": answer_type,
                "user_message_id": str(user_message.id),
                "source": "eval_seed",
            },
            created_at=created_at,
        )
        refs.append({"type": "query", "id": str(user_message.id)})
    return refs


async def _seed_dashboard_insight_refs(
    *,
    session: Any,
    organization_id: UUID,
    admin_user_id: UUID,
    window_start: datetime,
    window_end: datetime,
    item_input: Mapping[str, Any],
) -> list[dict[str, str]]:
    aliases = [
        ref
        for ref in _reference_strings(item_input.get("allowed_references"))
        if ref.startswith("dashboard_insight:")
    ]
    if not aliases:
        return []

    from app.repositories.analytics import (  # noqa: PLC0415
        DashboardInsightRepository,
        DashboardInsightRunRepository,
    )

    refs: list[dict[str, str]] = []
    for alias in aliases:
        run = await DashboardInsightRunRepository(session).create(
            organization_id=organization_id,
            requested_by=admin_user_id,
            trigger_type="eval_seed",
            window_start=window_start,
            window_end=window_end,
            status="completed",
        )
        insight = await DashboardInsightRepository(session).create(
            run_id=run.id,
            summary=f"Synthetic dashboard insight for {alias}.",
            headline_cards=[{"label": "Eval insight", "value": 1}],
            topic_breakdown=[],
            unanswered_questions=[],
            risk_breakdown=[],
            recommended_attention_areas=["Review the seeded eval snapshot."],
            source_message_ids=[],
        )
        refs.append({"type": "dashboard_insight", "id": str(insight.id)})
    return refs


def _positive_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return max(value, 0)
    if isinstance(value, float):
        return max(int(value), 0)
    if isinstance(value, str) and value.isdecimal():
        return max(int(value), 0)
    return 0


def _label_slots(value: Any, count: int, *, fallback: str) -> list[str]:
    labels: list[str] = []
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        for item in value:
            item_mapping = _mapping_or_empty(item)
            label = str(item_mapping.get("label") or "").strip().lower()
            if not label:
                continue
            labels.extend([label] * min(_positive_int(item_mapping.get("count")), count))
    return (labels + [fallback] * count)[:count]


def _risk_labels_by_index(value: Any, count: int) -> list[list[str]]:
    slots: list[list[str]] = [[] for _ in range(count)]
    if not isinstance(value, Mapping):
        return slots
    for label, raw_count in value.items():
        normalized = str(label).strip().lower()
        if not normalized:
            continue
        for index in range(min(_positive_int(raw_count), count)):
            slots[index].append(normalized)
    return slots


def _reference_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        reference_type = value.get("type")
        reference_id = value.get("id")
        if reference_type and reference_id:
            return [f"{reference_type}:{reference_id}"]
        return []
    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray | str):
        refs: list[str] = []
        for item in value:
            refs.extend(_reference_strings(item))
        return refs
    return []


def _has_conversation_file_sources(item_input: Mapping[str, Any]) -> bool:
    return any(
        chunk.metadata.get("source_type") == "conversation_file"
        for chunk in _fixture_chunks_for_item(item_input)
    )


def _fixture_chunks_for_item(item_input: Mapping[str, Any]) -> list[RetrievedChunk]:
    source_ids = _reference_strings(item_input.get("retrieved_source_ids"))
    if not source_ids:
        return []
    fixtures = _fixture_source_map()
    chunks: list[RetrievedChunk] = []
    for rank, source_id in enumerate(source_ids, start=1):
        fixture = fixtures.get(source_id)
        if fixture is None:
            continue
        metadata = {
            key: value
            for key, value in fixture.items()
            if key not in {"text", "expected_output"}
        }
        metadata.setdefault("source_id", source_id)
        metadata.setdefault("source_title", fixture.get("title") or source_id)
        chunks.append(
            RetrievedChunk(
                text=str(fixture.get("text") or ""),
                metadata=metadata,
                similarity_score=max(0.5, 0.99 - (rank * 0.01)),
            )
        )
    return chunks


def _fixture_source_map() -> dict[str, Mapping[str, Any]]:
    if not _KB_FIXTURE_PATH.exists():
        return {}
    loaded = yaml.safe_load(_KB_FIXTURE_PATH.read_text(encoding="utf-8")) or []
    fixtures: dict[str, Mapping[str, Any]] = {}
    if not isinstance(loaded, list):
        return fixtures
    for item in loaded:
        if not isinstance(item, Mapping):
            continue
        raw_input = item.get("input")
        payload: dict[str, Any] = {}
        if isinstance(raw_input, Mapping):
            payload.update(raw_input)
        payload.update({key: value for key, value in item.items() if key != "input"})
        source_id = str(payload.get("source_id") or "").strip()
        if source_id:
            fixtures[source_id] = payload
    return fixtures


def _recording_stream_service(stream_service: Any | None) -> RecordingStreamService:
    if isinstance(stream_service, RecordingStreamService):
        return stream_service
    return RecordingStreamService(inner=stream_service)


def _athlete_execute_kwargs(run_input: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "task_id": _required_str(run_input, "task_id"),
        "conversation_id": _required_uuid(run_input, "conversation_id"),
        "athlete_user_id": _required_uuid(run_input, "athlete_user_id"),
        "user_message_id": _required_uuid(run_input, "user_message_id"),
        "assistant_message_id": _required_uuid(run_input, "assistant_message_id"),
        "organization_id": _required_uuid(run_input, "organization_id"),
        "attached_file_ids": _uuid_list(run_input.get("attached_file_ids")),
    }


def _admin_execute_kwargs(run_input: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "task_id": _required_str(run_input, "task_id"),
        "session_id": _required_uuid(run_input, "session_id"),
        "admin_user_id": _required_uuid(run_input, "admin_user_id"),
        "user_message_id": _required_uuid(run_input, "user_message_id"),
        "assistant_message_id": _required_uuid(run_input, "assistant_message_id"),
        "organization_id": _required_uuid(run_input, "organization_id"),
        "window_start": _required_str(run_input, "window_start"),
        "window_end": _required_str(run_input, "window_end"),
    }


def _title_execute_kwargs(run_input: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "task_id": _required_str(run_input, "task_id"),
        "conversation_id": _required_uuid(run_input, "conversation_id"),
        "athlete_user_id": _required_uuid(run_input, "athlete_user_id"),
        "user_message_id": _required_uuid(run_input, "user_message_id"),
        "assistant_message_id": _required_uuid(run_input, "assistant_message_id"),
        "organization_id": _required_uuid(run_input, "organization_id"),
    }


def _required_str(mapping: Mapping[str, Any], field_name: str) -> str:
    value = mapping.get(field_name)
    if value in (None, ""):
        raise ValueError(f"Missing required eval input field: {field_name}")
    return str(value)


def _required_uuid(mapping: Mapping[str, Any], field_name: str) -> UUID:
    return _uuid_value(_required_str(mapping, field_name), field_name)


def _uuid_list(value: Any) -> list[UUID]:
    if value is None:
        return []
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise TypeError("attached_file_ids must be a sequence")
    return [_uuid_value(item, "attached_file_ids") for item in value]


def _uuid_value(value: Any, field_name: str) -> UUID:
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except ValueError as exc:
        raise ValueError(f"Invalid UUID for eval input field: {field_name}") from exc


def _output_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "model_dump"):
        dumped = value.model_dump()
        return dict(dumped) if isinstance(dumped, Mapping) else {"value": dumped}
    return {"value": value}


def _sequence_or_none(value: Any) -> Sequence[Any] | None:
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return value
    return None


def _jsonish_sequence(values: Sequence[Any]) -> list[Any]:
    return [_jsonish(value) for value in values]


def _jsonish_mapping(mapping: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): _jsonish(value) for key, value in mapping.items()}


def _jsonish(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Mapping):
        return _jsonish_mapping(value)
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return [_jsonish(item) for item in value]
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return value


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _int_or_default(value: Any, default: int) -> int:
    return int(value) if value is not None else default


def _float_or_default(value: Any, default: float) -> float:
    return float(value) if value is not None else default


def _stream_id(prefix: str, index: int) -> str:
    return f"recording-{prefix}-{index}"


def _default_settings() -> Any:
    from app.core.config import get_settings  # noqa: PLC0415

    return get_settings()


def _default_session_factory(settings: Any) -> SessionFactory:
    return lambda: _eval_session_scope(settings)


@asynccontextmanager
async def _eval_session_scope(settings: Any) -> AsyncIterator[AsyncSession]:
    """Create an eval-local session/engine so live evals do not share loop-bound pools."""

    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    try:
        async with session_factory() as session:
            yield session
    finally:
        await engine.dispose()


def _default_chat_model(settings: Any) -> Any:
    from app.infrastructure.llm.factory import get_llm_provider  # noqa: PLC0415

    return get_llm_provider(app_settings=settings).get_chat_model()


def _athlete_chat_executor_cls() -> type[Any]:
    from app.agents.executors.athlete_chat_executor import (  # noqa: PLC0415
        AthleteChatExecutor,
    )

    return AthleteChatExecutor


def _admin_chat_executor_cls() -> type[Any]:
    from app.agents.executors.admin_chat_executor import (  # noqa: PLC0415
        AdminChatExecutor,
    )

    return AdminChatExecutor


def _conversation_title_executor_cls() -> type[Any]:
    from app.agents.executors.conversation_title_executor import (  # noqa: PLC0415
        ConversationTitleExecutor,
    )

    return ConversationTitleExecutor
