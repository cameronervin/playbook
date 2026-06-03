"""The Judge Protocol — one async ``score`` method, many implementations.

Selecting a judge is setting one field on a spec; the runner never branches on
judge kind. ``TYPE_CHECKING`` imports keep this free of a runtime cycle with
``types.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from evals.core.rubric import Rubric
    from evals.core.types import GraphRun, Score


@runtime_checkable
class Judge(Protocol):
    async def score(
        self,
        *,
        run: "GraphRun",
        rubric: "Rubric",
        expected_output: object,
    ) -> list["Score"]:
        ...
