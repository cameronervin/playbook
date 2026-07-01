"""Seed local Phase 4 dashboard analytics data and trigger insight generation.

This script is local-development tooling. It creates deterministic synthetic
athlete turns that flow through the same analytics repository joins used by the
admin dashboard, then optionally starts a real dashboard insight run.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal
from uuid import UUID

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker  # noqa: E402

from app.core.config import Settings, get_settings  # noqa: E402
from app.core.exceptions import AppError  # noqa: E402
from app.infrastructure.db.session import (  # noqa: E402
    cleanup_db_engine,
    get_session_factory,
)
from app.models.conversations import Conversation  # noqa: E402
from app.models.identity import User  # noqa: E402
from app.repositories.conversations import (  # noqa: E402
    ConversationMessageRepository,
    ConversationRepository,
)
from app.repositories.identity import UserRepository  # noqa: E402
from app.schemas.admin_analytics import DashboardInsightRunCreateRequest  # noqa: E402
from app.services.dashboard_insights import DashboardInsightService  # noqa: E402
from scripts.phase1_dev_auth import seed_phase1_users  # noqa: E402

SeedWindow = Literal["7d", "30d"]

DEMO_PREFIX = "[phase4-demo]"
POLL_INTERVAL_SECONDS = 3
POLL_TIMEOUT_SECONDS = 180


@dataclass(frozen=True, slots=True)
class DemoTurnSpec:
    """One synthetic athlete question and paired assistant response."""

    question: str
    answer: str
    created_at: datetime
    topic_labels: list[str]
    risk_labels: list[str]
    answer_type: str = "grounded_answer"
    assistant_status: str = "complete"
    unanswered_reason: str | None = None


@dataclass(frozen=True, slots=True)
class SeedResult:
    """Summary of synthetic data seeded for local validation."""

    athlete_id: UUID
    admin_id: UUID
    organization_id: UUID
    deleted_conversations: int
    inserted_turns: int


def build_demo_turn_specs(now: datetime | None = None) -> list[DemoTurnSpec]:
    """Return deterministic synthetic turns covering dashboard analytics paths."""
    anchor = _aware_utc(now) if now is not None else datetime.now(UTC)
    day = timedelta(days=1)
    hour = timedelta(hours=1)

    return [
        DemoTurnSpec(
            question=f"{DEMO_PREFIX} Do I need to disclose a local apparel NIL deal before I sign?",
            answer="Yes. Submit the NIL activity for compliance review before signing.",
            created_at=anchor - (day * 6) - hour,
            topic_labels=["nil", "compliance"],
            risk_labels=["compliance"],
        ),
        DemoTurnSpec(
            question=f"{DEMO_PREFIX} Can I post a sponsored gym video if the company gives me free gear?",
            answer="Yes, but disclose the in-kind benefit and avoid school marks without approval.",
            created_at=anchor - (day * 5) - (hour * 3),
            topic_labels=["nil"],
            risk_labels=["compliance"],
        ),
        DemoTurnSpec(
            question=f"{DEMO_PREFIX} What forms do I use for a summer camp appearance payment?",
            answer="Use the NIL disclosure workflow and include the appearance agreement.",
            created_at=anchor - (day * 5),
            topic_labels=["nil", "process"],
            risk_labels=[],
        ),
        DemoTurnSpec(
            question=f"{DEMO_PREFIX} Is it okay for a booster to introduce me to a brand?",
            answer="A booster introduction can create compliance risk. Ask compliance before responding.",
            created_at=anchor - (day * 4) - (hour * 2),
            topic_labels=["nil", "compliance"],
            risk_labels=["compliance"],
        ),
        DemoTurnSpec(
            question=f"{DEMO_PREFIX} Can I text a recruit who asked about our team visit schedule?",
            answer="Do not contact the recruit directly. Send the request to the recruiting office.",
            created_at=anchor - (day * 4),
            topic_labels=["recruiting", "compliance"],
            risk_labels=["recruiting"],
        ),
        DemoTurnSpec(
            question=f"{DEMO_PREFIX} Where do I upload travel receipts after an official team trip?",
            answer="Upload receipts in the travel reimbursement workflow within seven days.",
            created_at=anchor - (day * 3) - (hour * 5),
            topic_labels=["process"],
            risk_labels=[],
        ),
        DemoTurnSpec(
            question=f"{DEMO_PREFIX} I missed a study hall check-in. Who should I notify?",
            answer="Notify academic support and your sport administrator with the reason for the miss.",
            created_at=anchor - (day * 3),
            topic_labels=["process"],
            risk_labels=[],
        ),
        DemoTurnSpec(
            question=f"{DEMO_PREFIX} Can a collective promise me a deal if I transfer friends here?",
            answer="This is not supported. Escalate to compliance before taking any action.",
            created_at=anchor - (day * 2) - (hour * 4),
            topic_labels=["nil", "recruiting", "compliance"],
            risk_labels=["recruiting", "compliance"],
            answer_type="unsupported",
            unanswered_reason="unsupported",
        ),
        DemoTurnSpec(
            question=f"{DEMO_PREFIX} What is the policy for using department photos in a paid post?",
            answer="Use only approved media assets and disclose the paid post before publishing.",
            created_at=anchor - (day * 2),
            topic_labels=["nil", "process"],
            risk_labels=["compliance"],
        ),
        DemoTurnSpec(
            question=f"{DEMO_PREFIX} Can my family accept free tickets from a recruit's parent?",
            answer="No. Treat that as a recruiting compliance concern and report it to compliance.",
            created_at=anchor - day - (hour * 2),
            topic_labels=["recruiting", "compliance"],
            risk_labels=["recruiting", "compliance"],
        ),
        DemoTurnSpec(
            question=f"{DEMO_PREFIX} Why did my reimbursement request get returned?",
            answer="The request is missing required itemized receipts.",
            created_at=anchor - (hour * 6),
            topic_labels=["process"],
            risk_labels=[],
        ),
        DemoTurnSpec(
            question=f"{DEMO_PREFIX} Can I use an agent to negotiate a shoe deal?",
            answer="Agent involvement depends on the agreement scope. Send the contract to compliance first.",
            created_at=anchor - hour,
            topic_labels=["nil", "compliance"],
            risk_labels=["compliance"],
        ),
    ]


def is_demo_conversation_title(title: str | None) -> bool:
    """Return true only for conversations owned by this local validation script."""
    return bool(title and title.startswith(DEMO_PREFIX))


def resolve_seed_window(
    window: SeedWindow,
    *,
    now: datetime | None = None,
) -> tuple[datetime, datetime]:
    """Resolve a local seed/generation window."""
    resolved_end = _aware_utc(now) if now is not None else datetime.now(UTC)
    days = 30 if window == "30d" else 7
    return resolved_end - timedelta(days=days), resolved_end


async def seed_dashboard_demo_data(
    session: AsyncSession,
    *,
    settings: Settings,
    now: datetime | None = None,
) -> SeedResult:
    """Seed deterministic users and synthetic analytics turns."""
    seeded = await seed_phase1_users(session, settings)
    athlete = seeded["athlete"]
    admin = seeded["admin"]
    organization_id = athlete.organization_id

    deleted = await _delete_prior_demo_conversations(
        session,
        athlete_id=athlete.user_id,
        organization_id=organization_id,
    )

    conversation_repo = ConversationRepository(session)
    message_repo = ConversationMessageRepository(session)
    inserted = 0
    for index, turn in enumerate(build_demo_turn_specs(now=now), start=1):
        conversation = await conversation_repo.create(
            organization_id=organization_id,
            athlete_id=athlete.user_id,
            title=f"{DEMO_PREFIX} dashboard validation {index:02d}",
        )
        user_message = await message_repo.create(
            conversation_id=conversation.id,
            role="user",
            content=turn.question,
            created_at=turn.created_at,
        )
        assistant_metadata = {
            "user_message_id": str(user_message.id),
            "answer_type": turn.answer_type,
        }
        if turn.unanswered_reason:
            assistant_metadata["unanswered_reason"] = turn.unanswered_reason
        assistant_created_at = turn.created_at + timedelta(microseconds=1)
        await message_repo.create(
            conversation_id=conversation.id,
            role="assistant",
            content=turn.answer,
            status=turn.assistant_status,
            safety_outcome=turn.answer_type,
            topic_labels=turn.topic_labels,
            risk_labels=turn.risk_labels,
            metadata=assistant_metadata,
            created_at=assistant_created_at,
        )
        await conversation_repo.update_last_message_at(
            conversation,
            last_message_at=assistant_created_at,
        )
        inserted += 1

    await session.commit()
    return SeedResult(
        athlete_id=athlete.user_id,
        admin_id=admin.user_id,
        organization_id=organization_id,
        deleted_conversations=deleted,
        inserted_turns=inserted,
    )


async def trigger_dashboard_run(
    session: AsyncSession,
    *,
    actor: User,
    settings: Settings,
    window: SeedWindow,
    now: datetime | None = None,
) -> UUID:
    """Trigger a manual dashboard insight run for the seeded validation window."""
    window_start, window_end = resolve_seed_window(window, now=now)
    service = DashboardInsightService(session, settings=settings)
    response = await service.create_manual_run(
        actor=actor,
        request=DashboardInsightRunCreateRequest(
            window_start=window_start,
            window_end=window_end,
            source_filters={},
        ),
    )
    return response.run_id


async def poll_dashboard_run(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    actor_id: UUID,
    run_id: UUID,
    settings: Settings,
    timeout_seconds: int = POLL_TIMEOUT_SECONDS,
) -> str:
    """Poll a dashboard insight run until it finishes or the timeout expires."""
    deadline = datetime.now(UTC) + timedelta(seconds=timeout_seconds)
    last_status = "pending"
    while datetime.now(UTC) < deadline:
        async with session_factory() as session:
            actor = await _get_required_user(session, actor_id)
            run = await DashboardInsightService(session, settings=settings).get_run(
                actor=actor,
                run_id=run_id,
            )
        last_status = run.status
        print(f"Dashboard insight run {run_id} status: {run.status}")
        if run.status == "completed":
            print(
                "Dashboard insight completed: "
                f"{run.output.summary if run.output else 'no output attached'}"
            )
            return run.status
        if run.status == "failed":
            print(
                "Dashboard insight failed: "
                f"{_sanitize_error(run.error_message) or 'no sanitized error'}"
            )
            return run.status
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
    print(
        f"Dashboard insight run {run_id} did not finish within "
        f"{timeout_seconds} seconds; last status was {last_status}."
    )
    return last_status


async def _delete_prior_demo_conversations(
    session: AsyncSession,
    *,
    athlete_id: UUID,
    organization_id: UUID,
) -> int:
    result = await session.scalars(
        select(Conversation).where(
            Conversation.athlete_id == athlete_id,
            Conversation.organization_id == organization_id,
            Conversation.title.like(f"{DEMO_PREFIX}%"),
        )
    )
    conversations = [
        conversation
        for conversation in result.all()
        if is_demo_conversation_title(conversation.title)
    ]
    for conversation in conversations:
        await session.delete(conversation)
    await session.flush()
    return len(conversations)


async def _get_required_user(session: AsyncSession, user_id: UUID) -> User:
    user = await UserRepository(session).get(user_id)
    if user is None:
        raise RuntimeError(f"Seeded user {user_id} was not found")
    return user


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _sanitize_error(error_message: str | None) -> str | None:
    if not error_message:
        return None
    return error_message.replace("\n", " ")[:240]


async def _run(args: argparse.Namespace) -> None:
    settings = get_settings()
    session_factory = get_session_factory(settings)
    run_id: UUID | None = None
    seed_result: SeedResult | None = None

    try:
        async with session_factory() as session:
            if not args.skip_seed:
                seed_result = await seed_dashboard_demo_data(session, settings=settings)
                print(
                    "Seeded Phase 4 dashboard demo data: "
                    f"{seed_result.inserted_turns} turns inserted, "
                    f"{seed_result.deleted_conversations} prior demo conversations removed."
                )
            else:
                seeded = await seed_phase1_users(session, settings)
                await session.commit()
                seed_result = SeedResult(
                    athlete_id=seeded["athlete"].user_id,
                    admin_id=seeded["admin"].user_id,
                    organization_id=seeded["athlete"].organization_id,
                    deleted_conversations=0,
                    inserted_turns=0,
                )

            if not args.seed_only:
                actor = await _get_required_user(session, seed_result.admin_id)
                try:
                    run_id = await trigger_dashboard_run(
                        session,
                        actor=actor,
                        settings=settings,
                        window=args.window,
                    )
                    print(f"Triggered dashboard insight run: {run_id}")
                except AppError as exc:
                    run_id = _run_id_from_app_error(exc)
                    print(
                        "Dashboard insight run could not be enqueued: "
                        f"{exc.code.value if hasattr(exc.code, 'value') else exc.code}"
                    )
                    if run_id:
                        print(f"Failed run id: {run_id}")
                    raise

        if args.poll and run_id is not None and seed_result is not None:
            await poll_dashboard_run(
                session_factory,
                actor_id=seed_result.admin_id,
                run_id=run_id,
                settings=settings,
            )
    finally:
        await cleanup_db_engine()


def _run_id_from_app_error(error: AppError) -> UUID | None:
    details = getattr(error, "details", None)
    if not isinstance(details, dict):
        return None
    raw = details.get("run_id")
    if not isinstance(raw, str):
        return None
    try:
        return UUID(raw)
    except ValueError:
        return None


def main() -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Seed Phase 4 local analytics data and trigger dashboard insights.",
    )
    parser.add_argument(
        "--seed-only",
        action="store_true",
        help="Seed synthetic analytics data without triggering a dashboard insight run.",
    )
    parser.add_argument(
        "--trigger-run",
        action="store_true",
        help="Trigger a run after seeding. This is the default unless --seed-only is set.",
    )
    parser.add_argument(
        "--poll",
        action="store_true",
        default=True,
        help="Poll the triggered run until completed or failed. Enabled by default.",
    )
    parser.add_argument(
        "--no-poll",
        action="store_false",
        dest="poll",
        help="Trigger the run and exit without polling.",
    )
    parser.add_argument(
        "--skip-seed",
        action="store_true",
        help="Reuse existing seeded users/data and only trigger a dashboard run.",
    )
    parser.add_argument(
        "--window",
        choices=("7d", "30d"),
        default="7d",
        help="Dashboard insight window to generate.",
    )
    args = parser.parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
