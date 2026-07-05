"""Configuration model for Playbook Locust runs."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlparse

from playbook_load_tests.auth import BearerTokenPool

DEFAULT_API_BASE_URL = "http://localhost:8000"
DEFAULT_FAIL_RATIO_MAX = 0.01
DEFAULT_P95_MS = 1500.0
DEFAULT_STREAM_P95_MS = 60_000.0


class LoadProfile(StrEnum):
    """Supported load-test profiles."""

    SMOKE = "smoke"
    BASELINE = "baseline"
    LIVE_AGENT = "live-agent"
    RATE_LIMIT = "rate-limit"


class StreamMode(StrEnum):
    """How live agent scenarios handle returned SSE stream URLs."""

    ENQUEUE = "enqueue"
    WAIT = "wait"


@dataclass(frozen=True)
class ProfileDefaults:
    """Locust runtime defaults for one profile."""

    users: int
    spawn_rate: float
    run_time: str
    user_classes: tuple[str, ...]
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class PlaybookLoadConfig:
    """Runtime configuration, sourced from env vars and optional Locust args."""

    profile: LoadProfile
    target: str
    api_base_url: str
    kb_base_url: str | None
    stream_mode: StreamMode
    allow_production_target: bool
    fail_ratio_max: float
    p95_ms: float
    stream_p95_ms: float
    athlete_tokens: BearerTokenPool
    admin_tokens: BearerTokenPool
    super_admin_tokens: BearerTokenPool
    kb_api_secret: str
    organization_id: str

    @classmethod
    def from_environment(cls, parsed_options: object | None = None) -> PlaybookLoadConfig:
        """Build config from environment and Locust custom CLI options."""
        data = dict(os.environ)
        if parsed_options is not None:
            _copy_option(data, parsed_options, "playbook_profile", "PLAYBOOK_LOAD_PROFILE")
            _copy_option(data, parsed_options, "playbook_target", "PLAYBOOK_LOAD_TARGET")
            _copy_option(data, parsed_options, "playbook_kb_host", "PLAYBOOK_KB_BASE_URL")
            _copy_option(data, parsed_options, "playbook_stream_mode", "PLAYBOOK_LOAD_STREAM_MODE")
            _copy_option(
                data,
                parsed_options,
                "playbook_allow_production_target",
                "PLAYBOOK_LOAD_ALLOW_PRODUCTION_TARGET",
            )
        host = getattr(parsed_options, "host", None) if parsed_options is not None else None
        if host:
            data["PLAYBOOK_API_BASE_URL"] = str(host)
        return cls.from_mapping(data)

    @classmethod
    def from_mapping(cls, data: Mapping[str, str]) -> PlaybookLoadConfig:
        """Build config from a mapping of environment-style keys."""
        profile = LoadProfile(data.get("PLAYBOOK_LOAD_PROFILE", LoadProfile.SMOKE.value))
        target = data.get("PLAYBOOK_LOAD_TARGET", "local").strip().lower() or "local"
        api_base_url = _strip_trailing_slash(
            data.get("PLAYBOOK_API_BASE_URL", DEFAULT_API_BASE_URL)
        )
        kb_base_url = _optional_url(
            data.get("PLAYBOOK_KB_BASE_URL") or data.get("STAGING_KB_BASE_URL")
        )
        allow_production_target = _parse_bool(
            data.get("PLAYBOOK_LOAD_ALLOW_PRODUCTION_TARGET", "false")
        )
        if (
            _target_is_production(target) or is_production_target(api_base_url)
        ) and not allow_production_target:
            raise ValueError(
                "Refusing to load test production-like target. Set "
                "PLAYBOOK_LOAD_ALLOW_PRODUCTION_TARGET=true only for an approved run."
            )

        return cls(
            profile=profile,
            target=target,
            api_base_url=api_base_url,
            kb_base_url=kb_base_url,
            stream_mode=StreamMode(
                data.get("PLAYBOOK_LOAD_STREAM_MODE", StreamMode.ENQUEUE.value)
            ),
            allow_production_target=allow_production_target,
            fail_ratio_max=float(
                data.get("PLAYBOOK_LOAD_FAIL_RATIO_MAX", DEFAULT_FAIL_RATIO_MAX)
            ),
            p95_ms=float(data.get("PLAYBOOK_LOAD_P95_MS", DEFAULT_P95_MS)),
            stream_p95_ms=float(
                data.get("PLAYBOOK_LOAD_STREAM_P95_MS", DEFAULT_STREAM_P95_MS)
            ),
            athlete_tokens=BearerTokenPool(
                _parse_token_list(data.get("PLAYBOOK_ATHLETE_BEARER_TOKENS", ""))
            ),
            admin_tokens=BearerTokenPool(
                _parse_token_list(data.get("PLAYBOOK_ADMIN_BEARER_TOKENS", ""))
            ),
            super_admin_tokens=BearerTokenPool(
                _parse_token_list(data.get("PLAYBOOK_SUPER_ADMIN_BEARER_TOKENS", ""))
            ),
            kb_api_secret=data.get("PLAYBOOK_KB_API_SECRET", "").strip(),
            organization_id=data.get("PLAYBOOK_LOAD_ORGANIZATION_ID", "").strip(),
        )

    @property
    def profile_defaults(self) -> ProfileDefaults:
        """Return default Locust CLI values for this profile."""
        return profile_defaults(self.profile)

    @property
    def is_local(self) -> bool:
        """Whether the target looks like a local/development URL."""
        host = (urlparse(self.api_base_url).hostname or "").lower()
        return self.target in {"local", "development", "dev"} or host in {
            "localhost",
            "127.0.0.1",
            "::1",
        }

    def safe_summary(self) -> str:
        """Return a compact, secret-free summary for logs/manifests."""
        return (
            f"profile={self.profile.value} target={self.target} "
            f"api_base_url={self.api_base_url} "
            f"kb_base_url={'set' if self.kb_base_url else 'unset'} "
            f"stream_mode={self.stream_mode.value} "
            f"athlete_tokens={len(self.athlete_tokens.values)} "
            f"admin_tokens={len(self.admin_tokens.values)} "
            f"super_admin_tokens={len(self.super_admin_tokens.values)} "
            f"kb_secret={'set' if self.kb_api_secret else 'unset'}"
        )

    def to_manifest(self) -> dict[str, object]:
        """Return sanitized manifest metadata."""
        return {
            "profile": self.profile.value,
            "target": self.target,
            "api_base_url": self.api_base_url,
            "kb_base_url_configured": self.kb_base_url is not None,
            "stream_mode": self.stream_mode.value,
            "allow_production_target": self.allow_production_target,
            "thresholds": {
                "fail_ratio_max": self.fail_ratio_max,
                "p95_ms": self.p95_ms,
                "stream_p95_ms": self.stream_p95_ms,
            },
            "credential_counts": {
                "athlete_tokens": len(self.athlete_tokens.values),
                "admin_tokens": len(self.admin_tokens.values),
                "super_admin_tokens": len(self.super_admin_tokens.values),
                "kb_api_secret": bool(self.kb_api_secret),
            },
        }


def profile_defaults(profile: LoadProfile) -> ProfileDefaults:
    """Return default Locust shape and class list for a profile."""
    if profile == LoadProfile.SMOKE:
        return ProfileDefaults(
            users=5,
            spawn_rate=1.0,
            run_time="2m",
            user_classes=(
                "PublicReadinessUser",
                "AthleteReadOnlyUser",
                "AdminReadOnlyUser",
            ),
            tags=("cheap",),
        )
    if profile == LoadProfile.BASELINE:
        return ProfileDefaults(
            users=25,
            spawn_rate=5.0,
            run_time="10m",
            user_classes=(
                "PublicReadinessUser",
                "AthleteReadOnlyUser",
                "AdminReadOnlyUser",
            ),
            tags=("cheap",),
        )
    if profile == LoadProfile.LIVE_AGENT:
        return ProfileDefaults(
            users=5,
            spawn_rate=1.0,
            run_time="10m",
            user_classes=("AthleteChatEnqueueUser", "AdminChatUser", "KBSearchUser"),
            tags=("live",),
        )
    return ProfileDefaults(
        users=5,
        spawn_rate=1.0,
        run_time="2m",
        user_classes=("RateLimitProbeUser",),
        tags=("rate-limit",),
    )


def is_production_target(url: str) -> bool:
    """Conservatively identify production-like HTTP targets."""
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    if not hostname:
        return False
    if hostname in {"localhost", "127.0.0.1", "::1"}:
        return False
    if hostname.startswith("10.") or hostname.startswith("192.168."):
        return False
    if hostname.endswith(".local"):
        return False
    if any(marker in hostname for marker in ("staging", "stage", "dev", "sandbox")):
        return False
    return parsed.scheme == "https"


def _target_is_production(target: str) -> bool:
    return target.lower() in {"prod", "production"}


def _strip_trailing_slash(value: str) -> str:
    return value.strip().rstrip("/")


def _optional_url(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    return _strip_trailing_slash(value)


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_token_list(value: str) -> tuple[str, ...]:
    stripped = value.strip()
    if not stripped:
        return ()
    if stripped.startswith("["):
        parsed = json.loads(stripped)
        if not isinstance(parsed, list):
            raise ValueError("token list JSON must be an array")
        return tuple(str(item).strip() for item in parsed if str(item).strip())
    return tuple(item.strip() for item in stripped.split(",") if item.strip())


def _copy_option(
    data: dict[str, str],
    parsed_options: object,
    attr_name: str,
    env_name: str,
) -> None:
    value = getattr(parsed_options, attr_name, None)
    if value is not None and value != "":
        data[env_name] = str(value)
