"""Custom LLM-as-judge.

Uses an injected LangChain ``BaseChatModel`` (the project's LiteLLM-gateway chat
model) — no vendor SDK is hardcoded. The model is prompted to return JSON scoring
each rubric criterion; parsing is defensive because an OpenAI-compatible gateway
fronting a non-OpenAI model may wrap output in prose or code fences.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

import structlog
from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, Field, create_model

from evals.core.prompts import DEFAULT_PROMPT
from evals.core.rubric import Rubric
from evals.core.types import GraphRun, Score

logger = structlog.get_logger(__name__)

_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)

# Per-block character budget for the judge prompt. The judge model has a finite
# context window; an item's serialized input/output/trajectory can be far larger
# than what the agent under test ever saw (the agent truncates to a token budget;
# the judge otherwise gets the raw artifact). Capping each block keeps the prompt
# bounded so the judge call never overflows. ~24k chars ≈ ~6k tokens per block.
DEFAULT_BLOCK_CHAR_BUDGET = 24_000
# The OUTPUT is the thing being judged, so it gets a more generous cap than the
# (often bulky) raw INPUT and trajectory.
_OUTPUT_BUDGET_MULTIPLIER = 2


def summarize_events(events: list[dict]) -> str:
    """Compact the trajectory so it fits a prompt without dumping raw state."""
    parts: list[str] = []
    for ev in events:
        for node, payload in ev.items():
            parts.append(f"{node}: {json.dumps(payload, default=str)[:300]}")
    return "\n".join(parts) or "(no trajectory captured)"


def _message_text(content: object) -> str:
    """Flatten an AIMessage.content (str or list of content blocks) to text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: list[str] = []
        for block in content:
            if isinstance(block, str):
                chunks.append(block)
            elif isinstance(block, dict) and "text" in block:
                chunks.append(str(block["text"]))
        return "".join(chunks)
    return str(content)


def _truncate_block(text: str, *, limit: int) -> str:
    """Cap a prompt block to ``limit`` chars, keeping the head and marking the cut.

    The head carries the most signal for judging (titles, leading structure), so
    we keep the first ``limit`` chars rather than the tail and append a short,
    explicit marker so the judge knows the block was trimmed.
    """
    if len(text) <= limit:
        return text
    dropped = len(text) - limit
    return f"{text[:limit]}\n…[truncated {dropped} chars]"


def _extract_json(text: str) -> dict:
    """Pull the first JSON object out of a possibly-wrapped model response."""
    cleaned = text.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = _JSON_OBJECT_RE.search(cleaned)
        if match is None:
            raise
        return json.loads(match.group(0))


def _coerce_score(raw: object) -> tuple[float | None, str | None]:
    """Coerce a criterion value to (score, reasoning), tolerating model drift.

    Accepts a bare number, a numeric string, or a ``{"score"|"value": n}`` object
    (the shape some models emit instead of a flat number, which previously crashed
    the judge). Returns ``(None, None)`` when the value can't be coerced so the
    caller can skip that one criterion with a warning instead of aborting the run.
    """
    if isinstance(raw, bool):  # bool is an int subclass; reject to avoid True->1.0
        return None, None
    if isinstance(raw, (int, float)):
        return float(raw), None
    if isinstance(raw, str):
        try:
            return float(raw.strip()), None
        except ValueError:
            return None, None
    if isinstance(raw, dict):
        for key in ("score", "value"):
            if key in raw:
                inner, _ = _coerce_score(raw[key])
                if inner is not None:
                    reasoning = raw.get("reasoning") or raw.get("reason")
                    return inner, (str(reasoning) if reasoning is not None else None)
    return None, None


class _CriterionScore(BaseModel):
    # Reasoning is declared FIRST so structured output emits it before the score:
    # the model reasons, then commits a number conditioned on that reasoning
    # (chain-of-thought), rather than emitting a score and rationalising it after.
    reasoning: str | None = None
    score: float


def _response_model(rubric: Rubric) -> type[BaseModel]:
    """Build a Pydantic schema for structured output: one {score, reasoning} per criterion.

    Scores are plain floats (range guidance stays in the prompt, not the schema, so
    a slightly out-of-range score is captured rather than rejected by the gateway).
    """
    fields: dict[str, tuple[type, object]] = {}
    for c in rubric.criteria:
        fields[c.name] = (_CriterionScore, Field(description=c.description))
    return create_model("JudgeResponse", **fields)  # type: ignore[call-overload]


def _flatten_structured(data: dict) -> dict:
    """Turn the nested structured-output dict into the flat {name, name_reasoning} shape."""
    flat: dict[str, object] = {}
    for name, val in data.items():
        if isinstance(val, dict) and "score" in val:
            flat[name] = val["score"]
            if val.get("reasoning") is not None:
                flat[f"{name}_reasoning"] = val["reasoning"]
        else:
            flat[name] = val
    return flat


@dataclass
class LLMJudge:
    """LLM-as-judge backed by a project-provided chat model (LiteLLM gateway)."""

    chat_model: BaseChatModel
    prompt_template: str = DEFAULT_PROMPT
    block_char_budget: int = DEFAULT_BLOCK_CHAR_BUDGET

    async def score(
        self,
        *,
        run: GraphRun,
        rubric: Rubric,
        expected_output: object,
    ) -> list[Score]:
        budget = self.block_char_budget
        filled = self.prompt_template.format(
            criteria=rubric.criteria_block(),
            input=_truncate_block(json.dumps(run.input, default=str), limit=budget),
            output=_truncate_block(
                json.dumps(run.output, default=str), limit=budget * _OUTPUT_BUDGET_MULTIPLIER
            ),
            trajectory=_truncate_block(summarize_events(run.events), limit=budget),
            expected=_truncate_block(json.dumps(expected_output, default=str), limit=budget),
        )
        parsed = await self._invoke(filled, rubric)
        return self._scores_from_parsed(parsed, rubric)

    async def _invoke(self, prompt: str, rubric: Rubric) -> dict:
        """Get a {criterion: value, criterion_reasoning: str} mapping from the model.

        Prefers provider structured output (constrains the model to a schema, so it
        cannot wrap output in prose or nest scores); falls back to tolerant text
        parsing if the model/gateway doesn't support it or the call fails.
        """
        try:
            schema = _response_model(rubric)
            structured = self.chat_model.with_structured_output(schema)
            result = await structured.ainvoke(prompt)
            data = result if isinstance(result, dict) else result.model_dump()
            return _flatten_structured(data)
        except Exception as exc:  # noqa: BLE001 — any structured-output failure -> text path
            logger.debug("llm_judge_structured_output_fallback", rubric=rubric.name, error=str(exc))
            message = await self.chat_model.ainvoke(prompt)
            return _extract_json(_message_text(message.content))

    def _scores_from_parsed(self, parsed: dict, rubric: Rubric) -> list[Score]:
        scores: list[Score] = []
        for c in rubric.criteria:
            if c.name not in parsed:
                logger.warning("llm_judge_missing_criterion", criterion=c.name, rubric=rubric.name)
                continue
            value, nested_reason = _coerce_score(parsed[c.name])
            if value is None:
                logger.warning(
                    "llm_judge_uncoercible_score",
                    criterion=c.name, rubric=rubric.name, raw=str(parsed[c.name])[:120],
                )
                continue
            scores.append(
                Score(
                    name=c.name,
                    value=value,
                    data_type="NUMERIC",
                    comment=parsed.get(f"{c.name}_reasoning") or nested_reason,
                )
            )
        return scores
