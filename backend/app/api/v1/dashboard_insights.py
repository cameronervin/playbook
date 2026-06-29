"""Admin dashboard insight routes."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.api.v1.dependencies import AdminUserDep, DashboardInsightServiceDep
from app.schemas.admin_analytics import (
    DashboardInsightResponse,
    DashboardInsightRunCreateRequest,
    DashboardInsightRunResponse,
    DashboardInsightRunStartResponse,
)

router = APIRouter(prefix="/admin/dashboard-insights", tags=["Dashboard Insights"])


@router.get("/current", response_model=DashboardInsightResponse)
async def get_current_dashboard_insight(
    actor: AdminUserDep,
    service: DashboardInsightServiceDep,
    window: Annotated[str | None, Query(pattern=r"^[1-9][0-9]*d$")] = None,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
) -> DashboardInsightResponse:
    """Get the latest completed dashboard insight output."""
    return await service.get_current(
        actor=actor,
        window=window,
        window_start=window_start,
        window_end=window_end,
    )


@router.get("/outputs", response_model=list[DashboardInsightResponse])
async def list_dashboard_insight_outputs(
    actor: AdminUserDep,
    service: DashboardInsightServiceDep,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[DashboardInsightResponse]:
    """List generated dashboard insight outputs."""
    return await service.list_outputs(actor=actor, limit=limit, offset=offset)


@router.get("/outputs/{insight_id}", response_model=DashboardInsightResponse)
async def get_dashboard_insight_output(
    insight_id: UUID,
    actor: AdminUserDep,
    service: DashboardInsightServiceDep,
) -> DashboardInsightResponse:
    """Get one generated dashboard insight output."""
    return await service.get_output(actor=actor, insight_id=insight_id)


@router.get("/runs", response_model=list[DashboardInsightRunResponse])
async def list_dashboard_insight_runs(
    actor: AdminUserDep,
    service: DashboardInsightServiceDep,
    run_status: str | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[DashboardInsightRunResponse]:
    """List dashboard insight generation runs."""
    return await service.list_runs(
        actor=actor,
        status=run_status,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/runs",
    response_model=DashboardInsightRunStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_dashboard_insight_run(
    request: DashboardInsightRunCreateRequest,
    actor: AdminUserDep,
    service: DashboardInsightServiceDep,
) -> DashboardInsightRunStartResponse:
    """Start manual dashboard insight generation."""
    return await service.create_manual_run(actor=actor, request=request)


@router.get("/runs/{run_id}", response_model=DashboardInsightRunResponse)
async def get_dashboard_insight_run(
    run_id: UUID,
    actor: AdminUserDep,
    service: DashboardInsightServiceDep,
) -> DashboardInsightRunResponse:
    """Get one dashboard insight run status and output."""
    return await service.get_run(actor=actor, run_id=run_id)
