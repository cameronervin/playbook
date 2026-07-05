"""Worker-facing executor for dashboard insight generation."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog
from langchain_core.language_models import BaseChatModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph_provider import AgentGraphProvider
from app.agents.runtime_context import DashboardInsightsRuntimeContext
from app.core.config import Settings
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError
from app.observability.agent_trace import build_graph_invoke_config
from app.repositories.analytics import DashboardInsightRunRepository

logger = structlog.get_logger(__name__)

DASHBOARD_INSIGHTS_MODE = "dashboard_insights"
DASHBOARD_INSIGHTS_PHASE = "generate"


class DashboardInsightsExecutor:
    """Execute the dashboard insight graph for one persisted run."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        chat_model: BaseChatModel,
        settings: Settings,
        checkpointer: Any | None = None,
        graph_provider: AgentGraphProvider | None = None,
    ) -> None:
        self.session = session
        self.chat_model = chat_model
        self.settings = settings
        self.checkpointer = checkpointer
        self.graph_provider = graph_provider or AgentGraphProvider(
            chat_model=self.chat_model,
            title_model=self.chat_model,
            settings=settings,
            checkpointer=checkpointer,
        )
        self.run_repo = DashboardInsightRunRepository(session)

    async def execute(
        self,
        *,
        task_id: str,
        run_id: UUID,
        organization_id: UUID,
    ) -> dict[str, Any]:
        """Run the dashboard insight graph and return its completion payload."""
        graph = self.graph_provider.dashboard_insights_graph()
        runtime_context = DashboardInsightsRuntimeContext(
            session=self.session,
            settings=self.settings,
        )
        config = build_graph_invoke_config(
            thread_id=run_id,
            phase=DASHBOARD_INSIGHTS_PHASE,
            mode=DASHBOARD_INSIGHTS_MODE,
            settings=self.settings,
            extra_configurable={
                "task_id": task_id,
                "run_id": str(run_id),
                "organization_id": str(organization_id),
            },
        )
        result = await graph.ainvoke(
            {
                "run_id": str(run_id),
                "organization_id": str(organization_id),
            },
            config=config,
            context=runtime_context,
        )
        completion_result = _completion_result(result)
        if completion_result is None:
            raise AppError(
                "Dashboard insights graph finished without a completion result",
                ErrorCode.AGENT_FAILED,
                retryable=True,
                details={"run_id": str(run_id)},
            )
        logger.info(
            "dashboard_insights_run_completed",
            task_id=task_id,
            run_id=str(run_id),
            organization_id=str(organization_id),
        )
        return completion_result

    async def mark_failed(
        self,
        *,
        task_id: str,
        run_id: UUID,
        organization_id: UUID,
        error_type: str,
    ) -> None:
        """Mark a dashboard insight run as failed after task-level errors."""
        run = await self.run_repo.get_for_organization(
            organization_id=organization_id,
            run_id=run_id,
        )
        if run is None:
            logger.warning(
                "dashboard_insights_failed_run_missing",
                task_id=task_id,
                run_id=str(run_id),
                organization_id=str(organization_id),
            )
            return
        await self.run_repo.update_status(
            run,
            status="failed",
            error_message=error_type,
        )
        await self.session.commit()


def _completion_result(result: Any) -> dict[str, Any] | None:
    if not isinstance(result, dict):
        return None
    completion = result.get("completion_result")
    return completion if isinstance(completion, dict) else None
