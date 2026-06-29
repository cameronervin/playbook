"""Node factories for the dashboard insights LangGraph."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

import structlog
from langchain_core.messages import HumanMessage
from langgraph.runtime import Runtime

from app.agents.runtime_context import DashboardInsightsRuntimeContext
from app.agents.states.dashboard_insights_state import (
    DashboardInsightsState,
    DashboardInsightsStructuredResponse,
)
from app.core.exceptions import NotFoundError
from app.repositories.analytics import (
    DashboardInsightRepository,
    DashboardInsightRunRepository,
)
from app.services.admin_analytics import AdminAnalyticsService, format_snapshot_context

logger = structlog.get_logger(__name__)


def create_dashboard_insights_nodes(*, chains: dict[str, Any]) -> dict[str, Any]:
    """Create all nodes needed by the dashboard insights graph."""

    async def load_run(
        state: DashboardInsightsState,
        runtime: Runtime[DashboardInsightsRuntimeContext],
    ) -> dict[str, Any]:
        """Validate run ownership and mark generation as processing."""
        context = runtime.context
        run_repo = DashboardInsightRunRepository(context.session)
        run_id = UUID(state["run_id"])
        organization_id = UUID(state["organization_id"])
        run = await run_repo.get_for_organization(
            organization_id=organization_id,
            run_id=run_id,
        )
        if run is None:
            raise NotFoundError("Dashboard insight run", str(run_id))
        await run_repo.update_status(run, status="processing", error_message=None)
        await context.session.commit()
        logger.info(
            "dashboard_insights_run_loaded",
            run_id=str(run.id),
            organization_id=str(run.organization_id),
            trigger_type=run.trigger_type,
        )
        return {
            "window_start": run.window_start.isoformat(),
            "window_end": run.window_end.isoformat(),
            "source_filters": run.source_filters,
        }

    async def build_snapshot(
        state: DashboardInsightsState,
        runtime: Runtime[DashboardInsightsRuntimeContext],
    ) -> dict[str, Any]:
        """Load deterministic anonymized analytics snapshot for the run."""
        context = runtime.context
        service = AdminAnalyticsService(context.session, settings=context.settings)
        snapshot = await service.build_snapshot(
            organization_id=UUID(state["organization_id"]),
            window_start=datetime.fromisoformat(state["window_start"]),
            window_end=datetime.fromisoformat(state["window_end"]),
            source_filters=state.get("source_filters", {}),
        )
        context.analytics_snapshot = snapshot
        return {
            "snapshot_context": format_snapshot_context(snapshot),
            "source_message_ids": [
                str(message_id) for message_id in snapshot.source_message_ids
            ],
        }

    async def generate_insights(
        state: DashboardInsightsState,
        runtime: Runtime[DashboardInsightsRuntimeContext],
    ) -> dict[str, Any]:
        """Invoke the structured dashboard insight chain or return empty output."""
        snapshot = runtime.context.analytics_snapshot
        if snapshot is not None and snapshot.summary.query_volume == 0:
            structured = _empty_structured_response()
        else:
            result = await chains["dashboard_insights"].ainvoke(
                {
                    "messages": [
                        HumanMessage(
                            content=(
                                "Generate dashboard insight output for this "
                                "admin analytics snapshot."
                            )
                        )
                    ],
                    "run_id": state["run_id"],
                    "organization_id": state["organization_id"],
                    "window_start": state["window_start"],
                    "window_end": state["window_end"],
                    "source_filters": state.get("source_filters", {}),
                    "snapshot_context": state.get("snapshot_context", ""),
                    "source_message_ids": state.get("source_message_ids", []),
                },
                config=_chain_config(state),
                context=runtime.context,
            )
            structured = _structured_response(result)
        return {
            "summary": structured.summary.strip(),
            "headline_cards": structured.headline_cards,
            "topic_breakdown": structured.topic_breakdown,
            "unanswered_questions": structured.unanswered_questions,
            "risk_breakdown": structured.risk_breakdown,
            "recommended_attention_areas": structured.recommended_attention_areas,
            "source_message_ids": _valid_source_ids(
                structured.source_message_ids,
                state.get("source_message_ids", []),
            ),
        }

    async def save_output(
        state: DashboardInsightsState,
        runtime: Runtime[DashboardInsightsRuntimeContext],
    ) -> dict[str, Any]:
        """Persist generated output and mark run completed."""
        context = runtime.context
        run_repo = DashboardInsightRunRepository(context.session)
        insight_repo = DashboardInsightRepository(context.session)
        run_id = UUID(state["run_id"])
        run = await run_repo.get(run_id)
        if run is None:
            raise NotFoundError("Dashboard insight run", str(run_id))
        existing_count = await insight_repo.count_for_run(run.id)
        if existing_count == 0:
            await insight_repo.create(
                run_id=run.id,
                summary=state.get("summary", "").strip(),
                headline_cards=state.get("headline_cards", []),
                topic_breakdown=state.get("topic_breakdown", []),
                unanswered_questions=state.get("unanswered_questions", []),
                risk_breakdown=state.get("risk_breakdown", []),
                recommended_attention_areas=state.get(
                    "recommended_attention_areas",
                    [],
                ),
                source_message_ids=state.get("source_message_ids", []),
            )
        await run_repo.update_status(run, status="completed", error_message=None)
        await context.session.commit()
        return {
            "completion_result": {
                "status": "completed",
                "run_id": str(run.id),
                "organization_id": str(run.organization_id),
            }
        }

    return {
        "load_run": load_run,
        "build_snapshot": build_snapshot,
        "generate_insights": generate_insights,
        "save_output": save_output,
    }


def _chain_config(state: DashboardInsightsState) -> dict[str, object]:
    return {
        "configurable": {
            "run_id": state["run_id"],
            "organization_id": state["organization_id"],
        }
    }


def _structured_response(result: Any) -> DashboardInsightsStructuredResponse:
    if isinstance(result, DashboardInsightsStructuredResponse):
        return result
    if isinstance(result, dict):
        structured = result.get("structured_response", result)
        return DashboardInsightsStructuredResponse.model_validate(structured)
    return DashboardInsightsStructuredResponse.model_validate(result)


def _empty_structured_response() -> DashboardInsightsStructuredResponse:
    return DashboardInsightsStructuredResponse(
        summary="No athlete query data was found for this window.",
        headline_cards=[],
        topic_breakdown=[],
        unanswered_questions=[],
        risk_breakdown=[],
        recommended_attention_areas=[],
        source_message_ids=[],
    )


def _valid_source_ids(candidate_ids: list[str], allowed_ids: list[str]) -> list[str]:
    allowed = {str(item) for item in allowed_ids}
    valid: list[str] = []
    for candidate_id in candidate_ids:
        normalized = str(candidate_id)
        if normalized in allowed and normalized not in valid:
            valid.append(normalized)
    return valid
