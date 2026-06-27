from __future__ import annotations

import pytest

from app.services.summary_service import (
    SummarySource,
    build_summary_input,
    fallback_summary,
    normalize_summary,
    summarize_source,
)


def _chunks(count: int) -> list[dict]:
    return [
        {
            "text": f"Chunk {index} explains NIL approval steps and disclosure timing.",
            "metadata": {"chunk_index": index},
        }
        for index in range(count)
    ]


def test_build_summary_input_caps_long_input_deterministically() -> None:
    source = SummarySource(
        filename="nil-handbook.pdf",
        source_title="NIL Handbook",
        metadata={"source_type": "admin_upload"},
        parse_result={"selected_parser": "native_pdf", "route": "native"},
        chunks=_chunks(20),
    )

    first = build_summary_input(source, max_tokens=75)
    second = build_summary_input(source, max_tokens=75)

    assert first == second
    assert "NIL Handbook" in first
    assert "native_pdf" in first
    assert "Chunk 0 explains" in first
    assert len(first) < 500


def test_fallback_summary_uses_clean_title_and_first_meaningful_passage() -> None:
    source = SummarySource(
        filename="contract.pdf",
        source_title="Contract",
        metadata={"source_type": "conversation_file"},
        parse_result={},
        chunks=[
            {"text": " \n \t"},
            {"text": "This agreement covers NIL appearance obligations."},
        ],
    )

    assert (
        fallback_summary(source)
        == "Contract: This agreement covers NIL appearance obligations."
    )


def test_normalize_summary_limits_sentences_and_whitespace() -> None:
    raw = "  First sentence.   Second sentence! Third sentence should be removed. "

    assert normalize_summary(raw) == "First sentence. Second sentence!"


@pytest.mark.asyncio
async def test_summarize_source_returns_structured_agent_summary() -> None:
    class FakeAgent:
        async def ainvoke(self, payload):
            assert payload["messages"][0]["role"] == "user"
            return {
                "structured_response": {
                    "summary": "This handbook explains NIL disclosure timing.",
                }
            }

    source = SummarySource(
        filename="nil-handbook.pdf",
        source_title="NIL Handbook",
        metadata={"source_type": "admin_upload"},
        parse_result={},
        chunks=_chunks(2),
    )

    assert (
        await summarize_source(source, agent=FakeAgent(), max_input_tokens=3000)
        == "This handbook explains NIL disclosure timing."
    )


@pytest.mark.asyncio
async def test_summarize_source_falls_back_when_agent_fails() -> None:
    class FailingAgent:
        async def ainvoke(self, payload):
            raise RuntimeError("upstream unavailable")

    source = SummarySource(
        filename="contract.pdf",
        source_title="Contract",
        metadata={"source_type": "conversation_file"},
        parse_result={},
        chunks=[{"text": "This agreement covers NIL appearance obligations."}],
    )

    assert (
        await summarize_source(source, agent=FailingAgent(), max_input_tokens=3000)
        == "Contract: This agreement covers NIL appearance obligations."
    )
