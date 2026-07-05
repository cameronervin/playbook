"""Locust threshold evaluation and artifact writing."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from playbook_load_tests.config import LoadProfile, PlaybookLoadConfig


class StatsLike(Protocol):
    """Subset of Locust stats used by the release gate."""

    fail_ratio: float

    def get_response_time_percentile(self, percentile: float) -> float:
        """Return percentile response time in milliseconds."""


@dataclass(frozen=True)
class ThresholdResult:
    """Decision returned after evaluating load-test thresholds."""

    passed: bool
    reasons: tuple[str, ...]
    metrics: dict[str, object]


def evaluate_thresholds(
    *,
    stats: StatsLike,
    config: PlaybookLoadConfig,
    status_counts: Mapping[int, int],
    stream_p95_ms: float | None,
) -> ThresholdResult:
    """Return a pass/fail decision for the configured gate."""
    reasons: list[str] = []
    p95_ms = float(stats.get_response_time_percentile(0.95) or 0.0)
    fail_ratio = float(stats.fail_ratio or 0.0)
    if fail_ratio > config.fail_ratio_max:
        reasons.append(
            f"failure ratio {fail_ratio:.4f} exceeded max {config.fail_ratio_max:.4f}"
        )
    if p95_ms > config.p95_ms:
        reasons.append(f"p95 response time {p95_ms:.1f}ms exceeded max {config.p95_ms:.1f}ms")
    if stream_p95_ms is not None and stream_p95_ms > config.stream_p95_ms:
        reasons.append(
            f"stream p95 {stream_p95_ms:.1f}ms exceeded max {config.stream_p95_ms:.1f}ms"
        )
    five_xx_count = sum(count for status, count in status_counts.items() if 500 <= status <= 599)
    if five_xx_count:
        reasons.append(f"unexpected 5xx responses observed: {five_xx_count}")
    if config.profile != LoadProfile.RATE_LIMIT and status_counts.get(429, 0):
        reasons.append(f"unexpected 429 responses observed: {status_counts[429]}")
    return ThresholdResult(
        passed=not reasons,
        reasons=tuple(reasons),
        metrics={
            "fail_ratio": fail_ratio,
            "p95_ms": p95_ms,
            "stream_p95_ms": stream_p95_ms,
            "status_counts": {str(status): count for status, count in status_counts.items()},
        },
    )


def write_manifest(
    *,
    artifact_dir: str | None,
    config: PlaybookLoadConfig,
    result: ThresholdResult,
) -> None:
    """Write sanitized machine-readable run metadata when an artifact dir is set."""
    if not artifact_dir:
        return
    path = Path(artifact_dir)
    path.mkdir(parents=True, exist_ok=True)
    payload = {
        "created_at": datetime.now(UTC).isoformat(),
        "config": config.to_manifest(),
        "passed": result.passed,
        "reasons": list(result.reasons),
        "metrics": result.metrics,
    }
    (path / "manifest.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
