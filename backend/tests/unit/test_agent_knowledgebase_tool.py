from __future__ import annotations

from app.agents.tools.knowledgebase import (
    KnowledgebaseToolProfile,
    create_knowledgebase_search_tool,
)
from app.schemas.knowledgebase import KnowledgebaseResult, RetrievedChunk


class FakeKnowledgebaseProvider:
    provider_name = "fake"

    def __init__(self, result: KnowledgebaseResult | None = None) -> None:
        self.result = result
        self.requests: list[dict[str, object]] = []

    async def search(
        self,
        query: str,
        max_docs: int = 10,
        score_threshold: float = 0.7,
        metadata_filter: dict | None = None,
        configuration_id: str | None = None,
    ) -> KnowledgebaseResult:
        self.requests.append(
            {
                "query": query,
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

    async def health_check(self) -> bool:
        return True

    async def resolve_configuration(self) -> str:
        return "fake-config"


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

    result = await tool.ainvoke({"query": "nil disclosure"})

    assert tool.name == "search_playbook_knowledgebase"
    assert "athlete answers" in tool.description
    assert provider.requests == [
        {
            "query": "nil disclosure",
            "max_docs": 3,
            "score_threshold": 0.65,
            "metadata_filter": {"visibility": "athlete"},
            "configuration_id": None,
        }
    ]
    assert "[S-" in result
    assert "NIL Handbook" in result
    assert list(source_registry.values())[0].source_title == "NIL Handbook"


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


async def test_knowledgebase_tool_returns_zero_hit_message() -> None:
    tool = create_knowledgebase_search_tool(
        _profile(no_results_message="No athlete-visible sources found."),
        provider=FakeKnowledgebaseProvider(),
    )

    result = await tool.ainvoke({"query": "unknown"})

    assert result == "No athlete-visible sources found."


async def test_knowledgebase_tool_handles_provider_errors_without_leaking_details() -> None:
    class BrokenProvider(FakeKnowledgebaseProvider):
        async def search(self, *args: object, **kwargs: object) -> KnowledgebaseResult:
            raise RuntimeError("secret transport details")

    tool = create_knowledgebase_search_tool(
        _profile(unavailable_message="Knowledge base unavailable."),
        provider=BrokenProvider(),
    )

    result = await tool.ainvoke({"query": "nil"})

    assert result == "Knowledge base unavailable."
    assert "secret" not in result
