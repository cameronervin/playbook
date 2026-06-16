from __future__ import annotations

from uuid import UUID

from app.agents.tools.knowledgebase import (
    ATHLETE_KB_TOOL_PROFILE,
    KnowledgebaseToolProfile,
    create_knowledgebase_search_tool,
    format_conversation_file_context,
    register_knowledgebase_sources,
)
from app.infrastructure.knowledgebase.providers.local_kb import LocalKBProvider
from app.schemas.knowledgebase import KnowledgebaseResult, RetrievedChunk

ORG_ID = UUID("00000000-0000-0000-0000-000000000099")


class FakeKnowledgebaseProvider:
    provider_name = "fake"

    def __init__(self, result: KnowledgebaseResult | None = None) -> None:
        self.result = result
        self.requests: list[dict[str, object]] = []
        self.admin_upload_requests: list[dict[str, object]] = []

    async def search(
        self,
        query: str,
        organization_id: UUID | str,
        max_docs: int = 10,
        score_threshold: float = 0.7,
        metadata_filter: dict | None = None,
        configuration_id: str | None = None,
    ) -> KnowledgebaseResult:
        self.requests.append(
            {
                "query": query,
                "organization_id": str(organization_id),
                "max_docs": max_docs,
                "score_threshold": score_threshold,
                "metadata_filter": metadata_filter,
                "configuration_id": configuration_id,
            }
        )
        return self.result or KnowledgebaseResult(
            query=query,
            context="",
            sources=[],
            zero_hit=True,
            latency_ms=1,
        )

    async def search_admin_uploads(
        self,
        query: str,
        organization_id: UUID | str,
        max_docs: int = 10,
        score_threshold: float = 0.7,
        metadata_filter: dict | None = None,
        configuration_id: str | None = None,
    ) -> KnowledgebaseResult:
        result = await self.search(
            query=query,
            organization_id=organization_id,
            max_docs=max_docs,
            score_threshold=score_threshold,
            metadata_filter=metadata_filter,
            configuration_id=configuration_id,
        )
        self.admin_upload_requests.append(self.requests[-1])
        return result

    async def health_check(self) -> bool:
        return True

    async def resolve_configuration(self) -> str:
        return "fake-config"


class _FakeLocalKBProvider(LocalKBProvider):
    def __init__(self, settings, payload: dict) -> None:
        super().__init__(settings)
        self.payload = payload
        self.posts: list[tuple[str, dict]] = []

    async def resolve_configuration(self) -> str:
        return "fake-config"

    async def _post(self, path: str, json_body: dict) -> dict:
        self.posts.append((path, json_body))
        return self.payload


class _RecordingLocalKBProvider(LocalKBProvider):
    def __init__(self, settings, payload: dict) -> None:
        super().__init__(settings)
        self.payload = payload
        self.posts: list[tuple[str, dict]] = []

    async def _post(self, path: str, json_body: dict) -> dict:
        self.posts.append((path, json_body))
        return self.payload


async def _invoke_tool(tool, query: str):
    return await tool.ainvoke(
        {"query": query},
        config={"configurable": {"organization_id": str(ORG_ID)}},
    )


def _profile(**overrides: object) -> KnowledgebaseToolProfile:
    values = {
        "tool_name": "search_playbook_knowledgebase",
        "description": "Search Playbook policy knowledge for athlete answers.",
        "metadata_filter": {"visibility": "athlete"},
        "default_max_docs": 3,
        "default_score_threshold": 0.65,
    }
    values.update(overrides)
    return KnowledgebaseToolProfile(**values)


async def test_knowledgebase_tool_uses_profile_name_description_and_filters() -> None:
    provider = FakeKnowledgebaseProvider(
        KnowledgebaseResult(
            query="nil",
            context="context",
            sources=[
                RetrievedChunk(
                    text="Athletes must disclose NIL deals within seven days.",
                    similarity_score=0.91,
                    metadata={
                        "document_id": "00000000-0000-0000-0000-000000000001",
                        "chunk_id": "00000000-0000-0000-0000-000000000002",
                        "source_title": "NIL Handbook",
                        "source_date": "2026-01-15",
                        "is_official": True,
                        "priority": 10,
                    },
                )
            ],
            confidence=0.91,
            zero_hit=False,
            latency_ms=12,
        )
    )
    source_registry = {}
    tool = create_knowledgebase_search_tool(
        _profile(),
        provider=provider,
        source_registry=source_registry,
    )

    result = await _invoke_tool(tool, "nil disclosure")

    assert tool.name == "search_playbook_knowledgebase"
    assert "athlete answers" in tool.description
    assert provider.requests == [
        {
            "query": "nil disclosure",
            "organization_id": str(ORG_ID),
            "max_docs": 3,
            "score_threshold": 0.65,
            "metadata_filter": {"visibility": "athlete"},
            "configuration_id": None,
        }
    ]
    assert "[S-" in result
    assert "NIL Handbook" in result
    assert "Official:" not in result
    assert "Priority:" not in result
    assert list(source_registry.values())[0].source_title == "NIL Handbook"


async def test_knowledgebase_tool_formats_citation_ready_metadata() -> None:
    provider = FakeKnowledgebaseProvider(
        KnowledgebaseResult(
            query="nil",
            context="context",
            sources=[
                RetrievedChunk(
                    text="Athletes must disclose NIL deals before participation.",
                    similarity_score=0.93,
                    metadata={
                        "document_id": "00000000-0000-0000-0000-000000000011",
                        "kb_service_document_id": "00000000-0000-0000-0000-000000000021",
                        "chunk_id": "00000000-0000-0000-0000-000000000012",
                        "chunk_index": 4,
                        "source_title": "NIL Handbook",
                    },
                )
            ],
            confidence=0.93,
            zero_hit=False,
            latency_ms=12,
        )
    )
    tool = create_knowledgebase_search_tool(_profile(), provider=provider)

    result = await _invoke_tool(tool, "nil disclosure")

    assert "Document ID: 00000000-0000-0000-0000-000000000011" in result
    assert "KB Service Document ID: 00000000-0000-0000-0000-000000000021" in result
    assert "Chunk ID: 00000000-0000-0000-0000-000000000012" in result
    assert "Chunk index: 4" in result


async def test_local_kb_provider_accepts_canonical_results_payload(test_settings) -> None:
    provider = _FakeLocalKBProvider(
        test_settings,
        {
            "results": [
                {
                    "document_id": "00000000-0000-0000-0000-000000000011",
                    "kb_service_document_id": "00000000-0000-0000-0000-000000000021",
                    "chunk_id": "00000000-0000-0000-0000-000000000012",
                    "chunk_index": 3,
                    "text": "NIL deals must be disclosed.",
                    "score": 0.91,
                    "metadata": {"source_title": "NIL Handbook"},
                }
            ],
            "query": "nil disclosure",
            "total": 1,
        },
    )

    result = await provider.search("nil disclosure", organization_id=ORG_ID)
    await provider.close()

    assert provider.posts[0][0] == "/api/kb/search"
    assert provider.posts[0][1]["organization_id"] == str(ORG_ID)
    assert provider.posts[0][1]["limit"] == 10
    assert provider.posts[0][1]["visibility_context"] == {"role": "athlete"}
    assert result.zero_hit is False
    assert result.sources[0].metadata["document_id"] == (
        "00000000-0000-0000-0000-000000000011"
    )
    assert result.sources[0].metadata["kb_service_document_id"] == (
        "00000000-0000-0000-0000-000000000021"
    )
    assert result.sources[0].metadata["chunk_id"] == (
        "00000000-0000-0000-0000-000000000012"
    )
    assert result.sources[0].metadata["chunk_index"] == 3
    assert result.sources[0].metadata["source_title"] == "NIL Handbook"
    assert result.sources[0].metadata["score"] == 0.91


async def test_local_kb_provider_ranks_near_matches_by_source_date_only(
    test_settings,
) -> None:
    provider = _FakeLocalKBProvider(
        test_settings,
        {
            "results": [
                {
                    "document_id": "00000000-0000-0000-0000-000000000011",
                    "kb_service_document_id": "00000000-0000-0000-0000-000000000021",
                    "chunk_id": "00000000-0000-0000-0000-000000000012",
                    "chunk_index": 1,
                    "text": "Older high-priority guidance.",
                    "score": 0.93,
                    "metadata": {
                        "source_title": "Older Guide",
                        "source_date": "2026-01-01",
                        "is_official": True,
                        "priority": 100,
                    },
                },
                {
                    "document_id": "00000000-0000-0000-0000-000000000031",
                    "kb_service_document_id": "00000000-0000-0000-0000-000000000041",
                    "chunk_id": "00000000-0000-0000-0000-000000000032",
                    "chunk_index": 2,
                    "text": "Newer normal guidance.",
                    "score": 0.91,
                    "metadata": {
                        "source_title": "Newer Guide",
                        "source_date": "2026-03-01",
                        "is_official": False,
                        "priority": 0,
                    },
                },
            ],
            "query": "nil disclosure",
            "total": 2,
        },
    )

    result = await provider.search("nil disclosure", organization_id=ORG_ID)
    await provider.close()

    assert [chunk.metadata["source_title"] for chunk in result.sources] == [
        "Newer Guide",
        "Older Guide",
    ]


async def test_local_kb_provider_does_not_accept_legacy_chunks_payload(
    test_settings,
) -> None:
    provider = _FakeLocalKBProvider(
        test_settings,
        {
            "chunks": [
                {
                    "document_id": "00000000-0000-0000-0000-000000000031",
                    "kb_service_document_id": "00000000-0000-0000-0000-000000000041",
                    "chunk_id": "00000000-0000-0000-0000-000000000032",
                    "chunk_index": 9,
                    "text": "Compliance text.",
                    "score": 0.88,
                    "metadata": {
                        "source_title": "Compliance Manual",
                        "source_date": "2026-02-01",
                    },
                }
            ],
            "query": "compliance",
            "total": 1,
        },
    )

    result = await provider.search("compliance", organization_id=ORG_ID)
    await provider.close()

    assert provider.posts[0][0] == "/api/kb/search"
    assert result.zero_hit is True
    assert result.sources == []


async def test_local_kb_provider_resolves_default_configuration_without_manual_collection(
    test_settings,
) -> None:
    provider = _RecordingLocalKBProvider(
        test_settings,
        {"id": "00000000-0000-0000-0000-000000000051"},
    )

    first = await provider.resolve_configuration()
    second = await provider.resolve_configuration()
    await provider.close()

    assert first == "00000000-0000-0000-0000-000000000051"
    assert second == first
    assert provider.posts == [("/api/kb/configuration/resolve", {})]


async def test_athlete_kb_tool_filters_by_visibility_policy_scope() -> None:
    provider = FakeKnowledgebaseProvider()
    tool = create_knowledgebase_search_tool(
        ATHLETE_KB_TOOL_PROFILE,
        provider=provider,
    )

    await _invoke_tool(tool, "nil disclosure")

    assert provider.admin_upload_requests == provider.requests
    assert provider.requests == [
        {
            "query": "nil disclosure",
            "organization_id": str(ORG_ID),
            "max_docs": 10,
            "score_threshold": 0.7,
            "metadata_filter": {"visibility_policy": {"scope": "all_athletes"}},
            "configuration_id": None,
        }
    ]


async def test_knowledgebase_tool_uses_admin_upload_provider_method() -> None:
    provider = FakeKnowledgebaseProvider()
    tool = create_knowledgebase_search_tool(
        ATHLETE_KB_TOOL_PROFILE,
        provider=provider,
    )

    await _invoke_tool(tool, "compliance")

    assert len(provider.admin_upload_requests) == 1
    assert provider.admin_upload_requests[0]["metadata_filter"] == {
        "visibility_policy": {"scope": "all_athletes"}
    }


def test_conversation_file_context_registers_sources_and_redacts_sensitive_metadata() -> None:
    registry = {}
    result = KnowledgebaseResult(
        query="approval",
        context="context",
        sources=[
            RetrievedChunk(
                text="The contract requires department approval before signing.",
                similarity_score=0.92,
                metadata={
                    "source_type": "conversation_file",
                    "document_id": "00000000-0000-0000-0000-000000000031",
                    "conversation_id": "00000000-0000-0000-0000-000000000041",
                    "conversation_file_id": "00000000-0000-0000-0000-000000000031",
                    "kb_service_document_id": "00000000-0000-0000-0000-000000000051",
                    "chunk_id": "00000000-0000-0000-0000-000000000061",
                    "chunk_index": 7,
                    "source_title": "contract.pdf",
                    "source_summary": "A summary that orients the file.",
                    "source_locator": {"type": "page", "page_number": 3},
                    "source_uri": "https://storage.test/file.pdf?signature=secret",
                    "raw_text": "full private file text",
                },
            )
        ],
        confidence=0.92,
        zero_hit=False,
        latency_ms=3,
    )

    sources = register_knowledgebase_sources(result, registry=registry)
    context = format_conversation_file_context(sources)

    assert sources[0].source_key in registry
    assert sources[0].metadata["source_type"] == "conversation_file"
    assert "signature=secret" not in context
    assert "full private file text" not in context
    assert "Source summary (orientation only)" in context
    assert "Excerpt: The contract requires department approval" in context


async def test_knowledgebase_tool_profiles_can_be_reused_for_distinct_agents() -> None:
    provider = FakeKnowledgebaseProvider()
    athlete_tool = create_knowledgebase_search_tool(
        _profile(tool_name="search_playbook_knowledgebase"),
        provider=provider,
    )
    admin_tool = create_knowledgebase_search_tool(
        _profile(
            tool_name="search_compliance_knowledgebase",
            description="Search compliance knowledge for admin analysis.",
            metadata_filter={"visibility": "admin"},
        ),
        provider=provider,
    )

    assert athlete_tool.name == "search_playbook_knowledgebase"
    assert admin_tool.name == "search_compliance_knowledgebase"
    assert "admin analysis" in admin_tool.description
    assert "organization_id" not in athlete_tool.args


async def test_knowledgebase_tool_returns_zero_hit_message() -> None:
    tool = create_knowledgebase_search_tool(
        _profile(no_results_message="No athlete-visible sources found."),
        provider=FakeKnowledgebaseProvider(),
    )

    result = await _invoke_tool(tool, "unknown")

    assert result == "No athlete-visible sources found."


async def test_knowledgebase_tool_handles_provider_errors_without_leaking_details() -> None:
    class BrokenProvider(FakeKnowledgebaseProvider):
        async def search(self, *args: object, **kwargs: object) -> KnowledgebaseResult:
            raise RuntimeError("secret transport details")

    tool = create_knowledgebase_search_tool(
        _profile(unavailable_message="Knowledge base unavailable."),
        provider=BrokenProvider(),
    )

    result = await _invoke_tool(tool, "nil")

    assert result == "Knowledge base unavailable."
    assert "secret" not in result
