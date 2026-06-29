"""Dashboard insight run and output service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError, NotFoundError
from app.models.analytics import DashboardInsight, DashboardInsightRun
from app.models.identity import User
from app.repositories.analytics import (
    DashboardInsightRepository,
    DashboardInsightRunRepository,
)
from app.repositories.identity import OrganizationRepository
from app.schemas.admin_analytics import (
    DashboardInsightResponse,
    DashboardInsightRunCreateRequest,
    DashboardInsightRunResponse,
    DashboardInsightRunStartResponse,
)
from app.services.admin_analytics import resolve_analytics_window
from app.services.audit_service import AuditLogService
from app.workers.dispatcher import (
    DashboardInsightsTaskDispatcher,
    DashboardInsightsTaskPayload,
)

logger = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class NightlyDashboardInsightScheduleResult:
    """Summary of nightly dashboard insight run scheduling."""

    status: str
    created: int
    dispatched: int
    skipped: int

    def to_payload(self) -> dict[str, int | str]:
        """Return JSON-safe Celery result payload."""
        return {
            "status": self.status,
            "created": self.created,
            "dispatched": self.dispatched,
            "skipped": self.skipped,
        }


class DashboardInsightService:
    """Coordinate dashboard insight run lifecycle and admin APIs."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        run_repo: DashboardInsightRunRepository | None = None,
        insight_repo: DashboardInsightRepository | None = None,
        organization_repo: OrganizationRepository | None = None,
        audit_service: AuditLogService | None = None,
        dispatcher: DashboardInsightsTaskDispatcher | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.session = session
        self.run_repo = run_repo or DashboardInsightRunRepository(session)
        self.insight_repo = insight_repo or DashboardInsightRepository(session)
        self.organization_repo = organization_repo or OrganizationRepository(session)
        self.audit_service = audit_service or AuditLogService(session)
        self.dispatcher = dispatcher or DashboardInsightsTaskDispatcher()
        self.settings = settings or get_settings()

    async def create_manual_run(
        self,
        *,
        actor: User,
        request: DashboardInsightRunCreateRequest,
    ) -> DashboardInsightRunStartResponse:
        """Create a manual run, audit it, dispatch generation, and return status."""
        window_start, window_end = resolve_analytics_window(
            window=None,
            window_start=request.window_start,
            window_end=request.window_end,
            settings=self.settings,
        )
        run = await self.run_repo.create(
            organization_id=actor.organization_id,
            requested_by=actor.id,
            trigger_type="manual",
            window_start=window_start,
            window_end=window_end,
            source_filters=request.source_filters,
        )
        await self.audit_service.record(
            actor=actor,
            organization_id=actor.organization_id,
            action="dashboard_insight_run.manual_triggered",
            target_type="dashboard_insight_run",
            target_id=run.id,
            metadata={
                "window_start": window_start.isoformat(),
                "window_end": window_end.isoformat(),
                "source_filters": request.source_filters,
            },
        )
        await self.session.commit()
        try:
            self.dispatcher.dispatch(
                payload=DashboardInsightsTaskPayload(
                    run_id=run.id,
                    organization_id=actor.organization_id,
                )
            )
        except Exception as exc:
            logger.error(
                "dashboard_insight_dispatch_failed",
                run_id=str(run.id),
                organization_id=str(actor.organization_id),
                error_type=type(exc).__name__,
                exc_info=True,
            )
            await self.run_repo.update_status(
                run,
                status="failed",
                error_message="dashboard_insight_dispatch_failed",
            )
            await self.session.commit()
            raise AppError(
                "Failed to enqueue dashboard insight run",
                ErrorCode.AGENT_FAILED,
                retryable=True,
                details={"run_id": str(run.id)},
            ) from exc
        return DashboardInsightRunStartResponse(run_id=run.id, status=run.status)

    async def get_run(
        self,
        *,
        actor: User,
        run_id: UUID,
    ) -> DashboardInsightRunResponse:
        """Return one org-scoped run with optional generated output."""
        run = await self.run_repo.get_for_organization(
            organization_id=actor.organization_id,
            run_id=run_id,
        )
        if run is None:
            raise NotFoundError("Dashboard insight run", str(run_id))
        output = await self.insight_repo.get_for_run(run.id)
        return dashboard_run_to_response(run, output=output)

    async def list_runs(
        self,
        *,
        actor: User,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[DashboardInsightRunResponse]:
        """List org-scoped dashboard insight runs."""
        runs = await self.run_repo.list_by_organization(
            actor.organization_id,
            status=status,
            limit=limit,
            offset=offset,
        )
        responses: list[DashboardInsightRunResponse] = []
        for run in runs:
            responses.append(
                dashboard_run_to_response(
                    run,
                    output=await self.insight_repo.get_for_run(run.id),
                )
            )
        return responses

    async def list_outputs(
        self,
        *,
        actor: User,
        limit: int = 100,
        offset: int = 0,
    ) -> list[DashboardInsightResponse]:
        """List generated dashboard insight outputs for one organization."""
        outputs = await self.insight_repo.list_by_organization(
            actor.organization_id,
            limit=limit,
            offset=offset,
        )
        return [dashboard_insight_to_response(output) for output in outputs]

    async def get_output(
        self,
        *,
        actor: User,
        insight_id: UUID,
    ) -> DashboardInsightResponse:
        """Return one generated dashboard insight output."""
        output = await self.insight_repo.get_for_organization(
            organization_id=actor.organization_id,
            insight_id=insight_id,
        )
        if output is None:
            raise NotFoundError("Dashboard insight output", str(insight_id))
        return dashboard_insight_to_response(output)

    async def get_current(
        self,
        *,
        actor: User,
        window: str | None = None,
        window_start: datetime | None = None,
        window_end: datetime | None = None,
    ) -> DashboardInsightResponse:
        """Return the latest completed dashboard insight for an org/window."""
        resolved_start = None
        resolved_end = None
        if window or window_start or window_end:
            resolved_start, resolved_end = resolve_analytics_window(
                window=window,
                window_start=window_start,
                window_end=window_end,
                settings=self.settings,
            )
        output = await self.insight_repo.latest_completed(
            organization_id=actor.organization_id,
            window_start=resolved_start,
            window_end=resolved_end,
        )
        if output is None:
            raise NotFoundError("Dashboard insight output", "current")
        return dashboard_insight_to_response(output)

    async def schedule_nightly_runs(self) -> NightlyDashboardInsightScheduleResult:
        """Create and dispatch nightly dashboard insight runs for active orgs."""
        if not bool(getattr(self.settings, "DASHBOARD_INSIGHTS_NIGHTLY_ENABLED", True)):
            return NightlyDashboardInsightScheduleResult(
                status="disabled",
                created=0,
                dispatched=0,
                skipped=0,
            )
        window_days = int(
            getattr(self.settings, "DASHBOARD_INSIGHTS_NIGHTLY_WINDOW_DAYS", 7)
        )
        now = datetime.now(UTC)
        window_end = now.replace(hour=0, minute=0, second=0, microsecond=0)
        window_start = window_end - timedelta(days=window_days)
        created = 0
        dispatched = 0
        skipped = 0
        created_runs: list[DashboardInsightRun] = []
        organizations = await self.organization_repo.list_active(limit=500)
        for organization in organizations:
            existing = await self.run_repo.find_existing(
                organization_id=organization.id,
                trigger_type="nightly",
                window_start=window_start,
                window_end=window_end,
            )
            if existing is not None:
                skipped += 1
                continue
            run = await self.run_repo.create(
                organization_id=organization.id,
                requested_by=None,
                trigger_type="nightly",
                window_start=window_start,
                window_end=window_end,
                source_filters={},
            )
            created += 1
            created_runs.append(run)
        await self.session.commit()

        for run in created_runs:
            try:
                self.dispatcher.dispatch(
                    payload=DashboardInsightsTaskPayload(
                        run_id=run.id,
                        organization_id=run.organization_id,
                    )
                )
                dispatched += 1
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "dashboard_insight_nightly_dispatch_failed",
                    run_id=str(run.id),
                    organization_id=str(run.organization_id),
                    error_type=type(exc).__name__,
                    exc_info=True,
                )
                await self.run_repo.update_status(
                    run,
                    status="failed",
                    error_message="dashboard_insight_dispatch_failed",
                )
                await self.session.commit()

        status = "scheduled" if dispatched == created else "partial"
        return NightlyDashboardInsightScheduleResult(
            status=status,
            created=created,
            dispatched=dispatched,
            skipped=skipped,
        )


def dashboard_run_to_response(
    run: DashboardInsightRun,
    *,
    output: DashboardInsight | None,
) -> DashboardInsightRunResponse:
    """Map a dashboard insight run ORM object to a public DTO."""
    return DashboardInsightRunResponse(
        id=run.id,
        organization_id=run.organization_id,
        requested_by=run.requested_by,
        trigger_type=run.trigger_type,
        status=run.status,
        window_start=run.window_start,
        window_end=run.window_end,
        source_filters=run.source_filters,
        error_message=run.error_message,
        created_at=run.created_at,
        updated_at=run.updated_at,
        output=dashboard_insight_to_response(output) if output else None,
    )


def dashboard_insight_to_response(
    insight: DashboardInsight,
) -> DashboardInsightResponse:
    """Map a dashboard insight output ORM object to a public DTO."""
    return DashboardInsightResponse(
        id=insight.id,
        run_id=insight.run_id,
        summary=insight.summary,
        headline_cards=list(insight.headline_cards),
        topic_breakdown=list(insight.topic_breakdown),
        unanswered_questions=list(insight.unanswered_questions),
        risk_breakdown=list(insight.risk_breakdown),
        recommended_attention_areas=[
            str(item) for item in insight.recommended_attention_areas
        ],
        source_message_ids=[UUID(str(item)) for item in insight.source_message_ids],
        generated_at=insight.generated_at,
    )
