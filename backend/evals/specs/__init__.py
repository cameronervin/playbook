"""Per-agent eval specs + the REGISTRY the CLI runs against."""

from __future__ import annotations

from evals.core.types import EvalSpec
from evals.specs.admin_chat import SPEC as admin_chat_spec
from evals.specs.athlete_chat import SPEC as athlete_chat_spec
from evals.specs.conversation_title import SPEC as conversation_title_spec
from evals.specs.dashboard_insights import SPEC as dashboard_insights_spec

REGISTRY: dict[str, EvalSpec] = {
    athlete_chat_spec.name: athlete_chat_spec,
    admin_chat_spec.name: admin_chat_spec,
    dashboard_insights_spec.name: dashboard_insights_spec,
    conversation_title_spec.name: conversation_title_spec,
}

__all__ = ["REGISTRY"]
