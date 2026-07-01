"""Unit tests for the local Phase 4 dashboard validation seeder."""

from __future__ import annotations

from datetime import UTC, datetime

from scripts.phase4_dashboard_seed import (
    DEMO_PREFIX,
    build_demo_turn_specs,
    is_demo_conversation_title,
    resolve_seed_window,
)


def test_build_demo_turn_specs_cover_dashboard_topics_and_risks() -> None:
    now = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)

    turns = build_demo_turn_specs(now=now)

    assert len(turns) >= 10
    topics = {label for turn in turns for label in turn.topic_labels}
    risks = {label for turn in turns for label in turn.risk_labels}
    answer_types = {turn.answer_type for turn in turns}
    assert {"nil", "compliance", "recruiting", "process"}.issubset(topics)
    assert {"compliance", "recruiting"}.issubset(risks)
    assert {"grounded_answer", "unsupported"}.issubset(answer_types)
    assert any(turn.unanswered_reason == "unsupported" for turn in turns)
    assert all(turn.question.startswith(DEMO_PREFIX) for turn in turns)


def test_demo_conversation_title_scope_is_narrow() -> None:
    assert is_demo_conversation_title(f"{DEMO_PREFIX} NIL disclosure timing")
    assert not is_demo_conversation_title("NIL disclosure timing")
    assert not is_demo_conversation_title(f"Archived {DEMO_PREFIX} NIL disclosure timing")


def test_resolve_seed_window_returns_bounded_utc_window() -> None:
    now = datetime(2026, 7, 1, 12, 30, tzinfo=UTC)

    start, end = resolve_seed_window("7d", now=now)

    assert start.isoformat() == "2026-06-24T12:30:00+00:00"
    assert end is now
