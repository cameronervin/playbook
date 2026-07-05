"""Judge implementations + an optional config-driven factory.

Specs instantiate judges directly (e.g. ``LLMJudge(chat_model=...)``); ``JUDGES``
and ``build_judge`` exist only for the case where judges are ever selected from
config/YAML. Importing this package does NOT import ragas — the Ragas judge defers
its ragas imports to call time, so LLM-only specs work without ragas installed.
"""

from __future__ import annotations

from evals.core.judges.base import Judge
from evals.core.judges.composite import CompositeJudge, ScopedJudge
from evals.core.judges.deterministic import DeterministicJudge
from evals.core.judges.llm import LLMJudge
from evals.core.judges.ragas import RagasJudge

JUDGES = {
    "deterministic": DeterministicJudge,
    "llm": LLMJudge,
    "ragas": RagasJudge,
    "composite": CompositeJudge,
    "scoped": ScopedJudge,
}


def build_judge(cfg: dict) -> Judge:
    cfg = dict(cfg)  # don't mutate the caller's dict
    kind = cfg.pop("kind")
    if kind == "composite":
        cfg["judges"] = [build_judge(c) for c in cfg["judges"]]
    return JUDGES[kind](**cfg)


__all__ = [
    "Judge",
    "LLMJudge",
    "RagasJudge",
    "DeterministicJudge",
    "CompositeJudge",
    "ScopedJudge",
    "build_judge",
    "JUDGES",
]
