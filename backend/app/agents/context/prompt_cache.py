"""Prompt-cache routing metadata for agent runs.

Pattern: provider-specific ``cache_control`` headers are applied by the LLM
gateway layer. This module just produces stable cache keys/versioning that can
be threaded through LangGraph ``configurable`` so prefix stability is auditable
across runs.

The scaffold ships caching disabled by default; ``build_cache_config`` returns
an empty dict unless ``settings.PROMPT_CACHE_ENABLED`` is set.
"""

from __future__ import annotations

from uuid import UUID

from app.core.config import settings


def build_cache_config(
    *, mode: str, phase: str, example_id: UUID | str | None = None
) -> dict[str, str]:
    """Return LangGraph configurable cache-routing fields (or empty if disabled)."""
    if not getattr(settings, "PROMPT_CACHE_ENABLED", False):
        return {}

    namespace_root = getattr(settings, "AGENT_CACHE_NAMESPACE", "agent")
    namespace = f"{namespace_root}:{mode}:{phase}"
    if example_id is not None:
        namespace = f"{namespace}:{example_id}"

    return {
        "cache_namespace": namespace,
        "prompt_version": getattr(settings, "AGENT_PROMPT_VERSION", "v1"),
        "policy_version": getattr(settings, "AGENT_POLICY_VERSION", "v1"),
    }
