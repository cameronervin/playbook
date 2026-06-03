"""Ensemble + scoping judges — both are themselves ``Judge``s.

``CompositeJudge`` runs several judges over one trace and merges their scores.
``ScopedJudge`` restricts a judge to specific rubric names. Together they let a
KB spec run the LLM judge on its content rubric AND the Ragas judge on the RAG
rubrics, with no criterion double-scored: the runner passes every rubric to the
composite, and each ScopedJudge ignores rubrics outside its allowlist.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from evals.core.judges.base import Judge
from evals.core.rubric import Rubric
from evals.core.types import GraphRun, Score


@dataclass
class CompositeJudge:
    judges: list[Judge]

    async def score(
        self,
        *,
        run: GraphRun,
        rubric: Rubric,
        expected_output: object,
    ) -> list[Score]:
        results = await asyncio.gather(
            *(
                j.score(run=run, rubric=rubric, expected_output=expected_output)
                for j in self.judges
            )
        )
        return [s for sub in results for s in sub]


@dataclass
class ScopedJudge:
    """Delegate to ``judge`` only for rubrics whose name is in ``rubrics``."""

    judge: Judge
    rubrics: set[str]

    async def score(
        self,
        *,
        run: GraphRun,
        rubric: Rubric,
        expected_output: object,
    ) -> list[Score]:
        if rubric.name not in self.rubrics:
            return []
        return await self.judge.score(run=run, rubric=rubric, expected_output=expected_output)
