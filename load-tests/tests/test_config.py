from __future__ import annotations

import pytest

from playbook_load_tests.config import (
    LoadProfile,
    PlaybookLoadConfig,
    is_production_target,
    profile_defaults,
)


def test_profile_defaults_match_release_plan() -> None:
    smoke = profile_defaults(LoadProfile.SMOKE)
    baseline = profile_defaults(LoadProfile.BASELINE)
    live_agent = profile_defaults(LoadProfile.LIVE_AGENT)

    assert (smoke.users, smoke.spawn_rate, smoke.run_time) == (5, 1.0, "2m")
    assert (baseline.users, baseline.spawn_rate, baseline.run_time) == (25, 5.0, "10m")
    assert (live_agent.users, live_agent.spawn_rate, live_agent.run_time) == (5, 1.0, "10m")


def test_config_rejects_production_targets_without_override() -> None:
    with pytest.raises(ValueError, match="Refusing to load test production"):
        PlaybookLoadConfig.from_mapping(
            {
                "PLAYBOOK_LOAD_PROFILE": "smoke",
                "PLAYBOOK_LOAD_TARGET": "prod",
                "PLAYBOOK_API_BASE_URL": "https://app.example.com",
            }
        )


def test_config_parses_token_lists_without_exposing_secret_values() -> None:
    config = PlaybookLoadConfig.from_mapping(
        {
            "PLAYBOOK_LOAD_PROFILE": "baseline",
            "PLAYBOOK_API_BASE_URL": "https://staging.example.com",
            "PLAYBOOK_ATHLETE_BEARER_TOKENS": "athlete-1, athlete-2",
            "PLAYBOOK_ADMIN_BEARER_TOKENS": '["admin-1", "admin-2"]',
        }
    )

    assert config.athlete_tokens.values == ("athlete-1", "athlete-2")
    assert config.admin_tokens.values == ("admin-1", "admin-2")
    assert "athlete-1" not in config.safe_summary()
    assert "admin-1" not in config.safe_summary()
    assert "athlete_tokens=2" in config.safe_summary()


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://app.example.com", True),
        ("https://playbook.example.edu", True),
        ("https://staging.example.com", False),
        ("http://localhost:8000", False),
        ("http://127.0.0.1:8000", False),
    ],
)
def test_production_target_detection(url: str, expected: bool) -> None:
    assert is_production_target(url) is expected
