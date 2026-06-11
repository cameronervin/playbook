"""Token-based context budgeting for agent middleware.

Pattern: injected context is estimated (chars/4 heuristic — accurate enough for
a guardrail without a tokenizer dependency) and trimmed to a per-chain budget.
Budgets are read from ``settings.context_token_budget_map`` when present; the
scaffold ships without budgets configured, so ``enforce_context_token_budget``
is a no-op until you add them.
"""

from __future__ import annotations

import structlog

from app.core.config import Settings, get_settings

logger = structlog.get_logger(__name__)

CHARS_PER_TOKEN = 4
_TRUNCATION_NOTICE = "\n\n[Context truncated to fit chain token budget]"


def estimate_tokens(text: str) -> int:
    """Estimate token count from text length."""
    if not text:
        return 0
    return max(1, len(text) // CHARS_PER_TOKEN)


def truncate_to_token_budget(text: str, max_tokens: int) -> str:
    """Trim ``text`` to ``max_tokens``, preferring a word boundary."""
    if max_tokens <= 0 or estimate_tokens(text) <= max_tokens:
        return text

    char_budget = max_tokens * CHARS_PER_TOKEN
    truncated = text[:char_budget]
    last_ws = truncated.rfind(" ")
    if last_ws > char_budget * 0.8:
        truncated = truncated[:last_ws]
    return truncated.rstrip(" ,.;:-") + _TRUNCATION_NOTICE


def _budget_for(phase: str, settings: Settings | None = None) -> int | None:
    """Look up the per-chain token budget, if the app configures one."""
    app_settings = settings or get_settings()
    budget_map = getattr(app_settings, "context_token_budget_map", None) or {}
    return budget_map.get(phase)


def enforce_context_token_budget(
    context: str,
    *,
    phase: str,
    example_id: str,
    settings: Settings | None = None,
) -> str:
    """Enforce a per-chain token budget on injected context.

    No-op when no budget is configured for ``phase``. When the context exceeds
    the budget it is truncated (and a warning is logged).
    """
    budget = _budget_for(phase, settings)
    if budget is None:
        return context

    original_tokens = estimate_tokens(context)
    if original_tokens <= budget:
        return context

    truncated = truncate_to_token_budget(context, budget)
    logger.warning(
        "context_truncated_to_token_budget",
        phase=phase,
        example_id=example_id,
        original_tokens=original_tokens,
        budget_tokens=budget,
        truncated_tokens=estimate_tokens(truncated),
    )
    return truncated
