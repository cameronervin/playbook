"""Repositories for admin analytics and dashboard insight records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import Depends
from sqlalchemy import String, and_, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.infrastructure.db.session import get_db
from app.models.analytics import DashboardInsight, DashboardInsightRun
from app.models.conversations import Conversation, ConversationMessage


@dataclass(frozen=True, slots=True)
class AnalyticsQueryRecord:
    """Internal joined query row used by admin analytics services."""

    message_id: UUID
    conversation_id: UUID
    athlete_id: UUID
    text: str
    created_at: datetime
    response_status: str | None
    answer_type: str | None
    topic_labels: list[str]
    risk_labels: list[str]
    unanswered_reason: str | None


class AdminAnalyticsRepository:
    """Data access for org-scoped admin analytics over athlete messages."""

    def __init__(self, session: AsyncSession = Depends(get_db)) -> None:
        self.session = session

    async def list_query_records(
        self,
        *,
        organization_id: UUID,
        window_start: datetime,
        window_end: datetime,
        limit: int = 5000,
        offset: int = 0,
    ) -> list[AnalyticsQueryRecord]:
        """Return user query rows paired with their assistant response metadata."""
        user_message = aliased(ConversationMessage)
        assistant_message = aliased(ConversationMessage)
        assistant_user_message_id = assistant_message.message_metadata[
            "user_message_id"
        ].as_string()
        stmt = (
            select(
                user_message,
                assistant_message,
                Conversation.athlete_id,
            )
            .join(Conversation, user_message.conversation_id == Conversation.id)
            .outerjoin(
                assistant_message,
                and_(
                    assistant_message.conversation_id == user_message.conversation_id,
                    assistant_message.role == "assistant",
                    assistant_user_message_id == cast(user_message.id, String),
                ),
            )
            .where(
                Conversation.organization_id == organization_id,
                user_message.role == "user",
                user_message.created_at >= window_start,
                user_message.created_at < window_end,
            )
            .order_by(user_message.created_at.desc(), user_message.id.asc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        records: list[AnalyticsQueryRecord] = []
        for user_row, assistant_row, athlete_id in result.all():
            records.append(
                AnalyticsQueryRecord(
                    message_id=user_row.id,
                    conversation_id=user_row.conversation_id,
                    athlete_id=athlete_id,
                    text=user_row.content,
                    created_at=user_row.created_at,
                    response_status=assistant_row.status if assistant_row else None,
                    answer_type=_answer_type(assistant_row),
                    topic_labels=_string_list(
                        assistant_row.topic_labels if assistant_row else []
                    ),
                    risk_labels=_string_list(
                        assistant_row.risk_labels if assistant_row else []
                    ),
                    unanswered_reason=_unanswered_reason(assistant_row),
                )
            )
        return records


class DashboardInsightRunRepository:
    """Data access for dashboard insight run lifecycle records."""

    def __init__(self, session: AsyncSession = Depends(get_db)) -> None:
        self.session = session

    async def create(
        self,
        *,
        organization_id: UUID,
        requested_by: UUID | None,
        trigger_type: str,
        window_start: datetime,
        window_end: datetime,
        source_filters: dict[str, Any] | None = None,
        status: str = "pending",
    ) -> DashboardInsightRun:
        """Create a dashboard insight run without committing."""
        row = DashboardInsightRun(
            organization_id=organization_id,
            requested_by=requested_by,
            trigger_type=trigger_type,
            status=status,
            window_start=window_start,
            window_end=window_end,
        )
        if source_filters is not None:
            row.source_filters = source_filters
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return row

    async def get(self, run_id: UUID) -> DashboardInsightRun | None:
        """Return a dashboard insight run by ID."""
        result = await self.session.execute(
            select(DashboardInsightRun).where(DashboardInsightRun.id == run_id)
        )
        return result.scalar_one_or_none()

    async def get_for_organization(
        self,
        *,
        organization_id: UUID,
        run_id: UUID,
    ) -> DashboardInsightRun | None:
        """Return one run scoped to an organization."""
        result = await self.session.execute(
            select(DashboardInsightRun).where(
                DashboardInsightRun.id == run_id,
                DashboardInsightRun.organization_id == organization_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_organization(
        self,
        organization_id: UUID,
        *,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[DashboardInsightRun]:
        """Return dashboard insight runs for one organization."""
        stmt = select(DashboardInsightRun).where(
            DashboardInsightRun.organization_id == organization_id
        )
        if status is not None:
            stmt = stmt.where(DashboardInsightRun.status == status)
        result = await self.session.scalars(
            stmt.order_by(
                DashboardInsightRun.created_at.desc(),
                DashboardInsightRun.id.asc(),
            )
            .limit(limit)
            .offset(offset)
        )
        return list(result.all())

    async def find_existing(
        self,
        *,
        organization_id: UUID,
        trigger_type: str,
        window_start: datetime,
        window_end: datetime,
    ) -> DashboardInsightRun | None:
        """Return an existing run for an idempotent scheduled window."""
        result = await self.session.execute(
            select(DashboardInsightRun).where(
                DashboardInsightRun.organization_id == organization_id,
                DashboardInsightRun.trigger_type == trigger_type,
                DashboardInsightRun.window_start == window_start,
                DashboardInsightRun.window_end == window_end,
            )
        )
        return result.scalar_one_or_none()

    async def update_status(
        self,
        run: DashboardInsightRun,
        *,
        status: str,
        error_message: str | None = None,
    ) -> DashboardInsightRun:
        """Update a dashboard insight run status without committing."""
        run.status = status
        run.error_message = error_message
        await self.session.flush()
        await self.session.refresh(run)
        return run


class DashboardInsightRepository:
    """Data access for generated dashboard insight outputs."""

    def __init__(self, session: AsyncSession = Depends(get_db)) -> None:
        self.session = session

    async def create(
        self,
        *,
        run_id: UUID,
        summary: str,
        headline_cards: list[dict[str, Any]],
        topic_breakdown: list[dict[str, Any]],
        unanswered_questions: list[dict[str, Any]],
        risk_breakdown: list[dict[str, Any]],
        recommended_attention_areas: list[str],
        source_message_ids: list[str],
    ) -> DashboardInsight:
        """Persist a generated dashboard insight output without committing."""
        row = DashboardInsight(
            run_id=run_id,
            summary=summary,
            headline_cards=headline_cards,
            topic_breakdown=topic_breakdown,
            unanswered_questions=unanswered_questions,
            risk_breakdown=risk_breakdown,
            recommended_attention_areas=recommended_attention_areas,
            source_message_ids=source_message_ids,
        )
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return row

    async def get_for_organization(
        self,
        *,
        organization_id: UUID,
        insight_id: UUID,
    ) -> DashboardInsight | None:
        """Return one insight output scoped through its run organization."""
        result = await self.session.execute(
            select(DashboardInsight)
            .join(DashboardInsightRun, DashboardInsight.run_id == DashboardInsightRun.id)
            .where(
                DashboardInsight.id == insight_id,
                DashboardInsightRun.organization_id == organization_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_for_run(self, run_id: UUID) -> DashboardInsight | None:
        """Return the generated insight output for a run, if present."""
        result = await self.session.execute(
            select(DashboardInsight).where(DashboardInsight.run_id == run_id)
        )
        return result.scalar_one_or_none()

    async def list_by_organization(
        self,
        organization_id: UUID,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[DashboardInsight]:
        """Return generated insight outputs for one organization."""
        result = await self.session.scalars(
            select(DashboardInsight)
            .join(DashboardInsightRun, DashboardInsight.run_id == DashboardInsightRun.id)
            .where(DashboardInsightRun.organization_id == organization_id)
            .order_by(DashboardInsight.generated_at.desc(), DashboardInsight.id.asc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.all())

    async def latest_completed(
        self,
        *,
        organization_id: UUID,
        window_start: datetime | None = None,
        window_end: datetime | None = None,
    ) -> DashboardInsight | None:
        """Return the latest completed output for one organization/window."""
        stmt = (
            select(DashboardInsight)
            .join(DashboardInsightRun, DashboardInsight.run_id == DashboardInsightRun.id)
            .where(
                DashboardInsightRun.organization_id == organization_id,
                DashboardInsightRun.status == "completed",
            )
        )
        if window_start is not None:
            stmt = stmt.where(DashboardInsightRun.window_start == window_start)
        if window_end is not None:
            stmt = stmt.where(DashboardInsightRun.window_end == window_end)
        result = await self.session.scalars(
            stmt.order_by(DashboardInsight.generated_at.desc(), DashboardInsight.id.asc())
            .limit(1)
        )
        return result.first()

    async def list_completed_for_window(
        self,
        *,
        organization_id: UUID,
        window_start: datetime,
        window_end: datetime,
        limit: int = 5,
    ) -> list[DashboardInsight]:
        """Return completed insight outputs whose run windows overlap a window."""
        result = await self.session.scalars(
            select(DashboardInsight)
            .join(DashboardInsightRun, DashboardInsight.run_id == DashboardInsightRun.id)
            .where(
                DashboardInsightRun.organization_id == organization_id,
                DashboardInsightRun.status == "completed",
                DashboardInsightRun.window_start < window_end,
                DashboardInsightRun.window_end > window_start,
            )
            .order_by(DashboardInsight.generated_at.desc(), DashboardInsight.id.asc())
            .limit(limit)
        )
        return list(result.all())

    async def count_for_run(self, run_id: UUID) -> int:
        """Return number of insight outputs attached to a run."""
        result = await self.session.scalar(
            select(func.count())
            .select_from(DashboardInsight)
            .where(DashboardInsight.run_id == run_id)
        )
        return int(result or 0)


def _answer_type(assistant_row: ConversationMessage | None) -> str | None:
    if assistant_row is None:
        return None
    raw = assistant_row.message_metadata.get("answer_type") or assistant_row.safety_outcome
    return str(raw) if raw else None


def _unanswered_reason(assistant_row: ConversationMessage | None) -> str | None:
    if assistant_row is None:
        return "no_assistant_response"
    answer_type = _answer_type(assistant_row)
    if assistant_row.status in {"declined", "failed"}:
        return assistant_row.status
    if answer_type in {"unsupported", "refusal"}:
        return answer_type
    return None


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    return [str(value)]
