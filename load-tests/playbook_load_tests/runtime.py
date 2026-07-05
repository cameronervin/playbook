"""Runtime state shared by Locust event hooks and user classes."""

from __future__ import annotations

from collections import Counter

from playbook_load_tests.config import PlaybookLoadConfig

_config: PlaybookLoadConfig | None = None
_status_counts: Counter[int] = Counter()
_stream_durations_ms: list[float] = []


def set_config(config: PlaybookLoadConfig) -> None:
    """Install the active run config."""
    global _config
    _config = config


def get_config() -> PlaybookLoadConfig:
    """Return the active run config, falling back to environment values."""
    global _config
    if _config is None:
        _config = PlaybookLoadConfig.from_environment()
    return _config


def reset_runtime_metrics() -> None:
    """Clear counters for a fresh Locust run."""
    _status_counts.clear()
    _stream_durations_ms.clear()


def record_status(status_code: int | None) -> None:
    """Record an HTTP response status code."""
    if status_code is not None:
        _status_counts[int(status_code)] += 1


def status_counts() -> dict[int, int]:
    """Return copied status counts."""
    return dict(_status_counts)


def record_stream_duration(response_time_ms: float) -> None:
    """Record a completed stream duration."""
    _stream_durations_ms.append(response_time_ms)


def stream_p95_ms() -> float | None:
    """Return p95 stream duration in milliseconds, if stream waits ran."""
    if not _stream_durations_ms:
        return None
    values = sorted(_stream_durations_ms)
    index = max(0, min(len(values) - 1, int(round(0.95 * (len(values) - 1)))))
    return values[index]
