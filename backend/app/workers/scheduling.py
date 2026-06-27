"""Shared scheduling constants for backend worker maintenance tasks."""

from __future__ import annotations

MAINTENANCE_STARTUP_EXPIRES_SECONDS = 60
MAINTENANCE_RESCHEDULE_EXPIRES_GRACE_SECONDS = 60


def expires_for_countdown(countdown: int) -> int:
    """Return an expiry window for delayed maintenance tasks."""
    return max(0, countdown) + MAINTENANCE_RESCHEDULE_EXPIRES_GRACE_SECONDS
