from __future__ import annotations

from dataclasses import dataclass

from playbook_load_tests.config import LoadProfile, PlaybookLoadConfig
from playbook_load_tests.thresholds import evaluate_thresholds


@dataclass
class FakeStats:
    fail_ratio: float = 0.0
    response_time: float = 100.0

    def get_response_time_percentile(self, _percentile: float) -> float:
        return self.response_time


def _config(**overrides: object) -> PlaybookLoadConfig:
    data = {
        "PLAYBOOK_API_BASE_URL": "https://staging.example.com",
        "PLAYBOOK_LOAD_PROFILE": "smoke",
    }
    data.update({key: str(value) for key, value in overrides.items()})
    return PlaybookLoadConfig.from_mapping(data)


def test_thresholds_pass_with_healthy_stats() -> None:
    result = evaluate_thresholds(
        stats=FakeStats(fail_ratio=0.0, response_time=250.0),
        config=_config(),
        status_counts={200: 100, 202: 2},
        stream_p95_ms=900.0,
    )

    assert result.passed is True
    assert result.reasons == ()


def test_thresholds_fail_for_ratio_latency_5xx_and_unexpected_429() -> None:
    result = evaluate_thresholds(
        stats=FakeStats(fail_ratio=0.02, response_time=2000.0),
        config=_config(),
        status_counts={200: 100, 429: 1, 503: 1},
        stream_p95_ms=70_000.0,
    )

    assert result.passed is False
    assert any("failure ratio" in reason for reason in result.reasons)
    assert any("p95 response time" in reason for reason in result.reasons)
    assert any("stream p95" in reason for reason in result.reasons)
    assert any("5xx" in reason for reason in result.reasons)
    assert any("429" in reason for reason in result.reasons)


def test_rate_limit_profile_allows_429_results() -> None:
    result = evaluate_thresholds(
        stats=FakeStats(fail_ratio=0.0, response_time=100.0),
        config=_config(PLAYBOOK_LOAD_PROFILE=LoadProfile.RATE_LIMIT.value),
        status_counts={200: 2, 429: 30},
        stream_p95_ms=None,
    )

    assert result.passed is True
