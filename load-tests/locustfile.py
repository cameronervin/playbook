"""Playbook Locust entrypoint."""

from __future__ import annotations

import logging
import os

from locust import events

from playbook_load_tests.config import LoadProfile, PlaybookLoadConfig, StreamMode
from playbook_load_tests.runtime import (
    get_config,
    record_status,
    reset_runtime_metrics,
    set_config,
    status_counts,
    stream_p95_ms,
)
from playbook_load_tests.scenarios import (
    AdminChatUser,
    AdminReadOnlyUser,
    AthleteChatEnqueueUser,
    AthleteReadOnlyUser,
    KBSearchUser,
    PublicReadinessUser,
    RateLimitProbeUser,
)
from playbook_load_tests.thresholds import evaluate_thresholds, write_manifest

logger = logging.getLogger(__name__)


@events.init_command_line_parser.add_listener
def add_playbook_arguments(parser) -> None:
    """Add Playbook-specific Locust options."""
    parser.add_argument(
        "--playbook-profile",
        choices=[profile.value for profile in LoadProfile],
        default=None,
        help="Playbook load profile. Defaults to PLAYBOOK_LOAD_PROFILE or smoke.",
    )
    parser.add_argument(
        "--playbook-target",
        default=None,
        help="Human target label such as local, staging, or prod.",
    )
    parser.add_argument(
        "--playbook-kb-host",
        default=None,
        help="Optional direct KB-service base URL.",
    )
    parser.add_argument(
        "--playbook-stream-mode",
        choices=[mode.value for mode in StreamMode],
        default=None,
        help="Whether live agent scenarios only enqueue or wait for SSE completion.",
    )
    parser.add_argument(
        "--playbook-allow-production-target",
        action="store_true",
        default=None,
        help="Allow production-like targets for an explicitly approved run.",
    )


@events.init.add_listener
def configure_playbook(environment, **_kwargs) -> None:
    """Install run config once Locust has parsed options."""
    config = PlaybookLoadConfig.from_environment(environment.parsed_options)
    set_config(config)
    reset_runtime_metrics()
    logger.info("playbook_load_config %s", config.safe_summary())


@events.request.add_listener
def record_response_status(response=None, **_kwargs) -> None:
    """Track response status codes for release-gate threshold checks."""
    record_status(getattr(response, "status_code", None))


@events.quitting.add_listener
def enforce_thresholds(environment, **_kwargs) -> None:
    """Fail the process when load-test thresholds are exceeded."""
    config = get_config()
    result = evaluate_thresholds(
        stats=environment.stats.total,
        config=config,
        status_counts=status_counts(),
        stream_p95_ms=stream_p95_ms(),
    )
    write_manifest(
        artifact_dir=os.getenv("PLAYBOOK_LOAD_ARTIFACT_DIR"),
        config=config,
        result=result,
    )
    if result.passed:
        environment.process_exit_code = 0
        logger.info("playbook_load_thresholds_passed metrics=%s", result.metrics)
        return
    environment.process_exit_code = 1
    for reason in result.reasons:
        logger.error("playbook_load_threshold_failed %s", reason)


__all__ = [
    "AdminChatUser",
    "AdminReadOnlyUser",
    "AthleteChatEnqueueUser",
    "AthleteReadOnlyUser",
    "KBSearchUser",
    "PublicReadinessUser",
    "RateLimitProbeUser",
]
