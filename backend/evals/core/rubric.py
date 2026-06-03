"""Rubric model — what "good" means for a given agent.

A rubric is a named set of criteria loaded from YAML. The same rubric file works
for both judges: the LLM judge inlines ``criteria_block()`` into its prompt, and
the Ragas judge maps criterion names to metrics (falling back to AspectCritic,
which uses the criterion ``description`` as its definition).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import yaml


@dataclass
class Criterion:
    name: str
    description: str
    scale: tuple[float, float] = (0.0, 1.0)


@dataclass
class Rubric:
    name: str
    description: str
    criteria: list[Criterion] = field(default_factory=list)

    def criteria_block(self) -> str:
        """Render criteria for inlining into an LLM judge prompt."""
        return "\n".join(
            f"- {c.name} ({c.scale[0]}–{c.scale[1]}): {c.description}"
            for c in self.criteria
        )

    def response_schema(self) -> dict:
        """JSON schema hint for structured judge output (one float + reasoning per criterion)."""
        props: dict[str, dict] = {}
        for c in self.criteria:
            props[c.name] = {"type": "number"}
            props[f"{c.name}_reasoning"] = {"type": "string"}
        return {
            "type": "object",
            "properties": props,
            "required": [c.name for c in self.criteria],
        }


def load_rubric(path: str) -> Rubric:
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    criteria = [
        Criterion(
            name=c["name"],
            description=c["description"],
            scale=tuple(c.get("scale", (0.0, 1.0))),
        )
        for c in data.get("criteria", [])
    ]
    return Rubric(
        name=data["name"],
        description=data.get("description", ""),
        criteria=criteria,
    )
