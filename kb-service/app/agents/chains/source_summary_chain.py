"""Source-summary agent factory."""
from __future__ import annotations

from typing import Any

from app.agents.prompts.source_summary_prompt import SOURCE_SUMMARY_SYSTEM_PROMPT
from app.agents.states.source_summary_state import SourceSummaryStructuredResponse
from app.core.config import settings


def create_source_summary_agent() -> Any:
    """Create a lightweight structured agent for canonical source summaries."""
    from langchain.agents import create_agent  # noqa: PLC0415
    from langchain.agents.structured_output import ToolStrategy  # noqa: PLC0415
    from langchain_openai import ChatOpenAI  # noqa: PLC0415

    model = ChatOpenAI(
        model=settings.LITELLM_SUMMARY_MODEL,
        base_url=settings.LITELLM_BASE_URL,
        api_key=settings.LITELLM_API_KEY,
        temperature=0,
        max_tokens=settings.KB_SUMMARY_MAX_OUTPUT_TOKENS,
        timeout=settings.KB_EMBED_REQUEST_TIMEOUT_SECONDS,
    )
    return create_agent(
        model=model,
        tools=[],
        system_prompt=SOURCE_SUMMARY_SYSTEM_PROMPT,
        response_format=ToolStrategy(SourceSummaryStructuredResponse),
        name="kb_source_summary",
    )
