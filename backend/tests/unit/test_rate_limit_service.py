from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.core.config import Settings
from app.services.rate_limit import (
    InMemoryRateLimitStore,
    RateLimitPolicy,
    RateLimitService,
)


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "DATABASE_URL": "postgresql+asyncpg://app:pass@localhost:5432/playbook",
        "SECRET_KEY": "test-secret-value-that-is-long-enough",
        "OAUTH_STATE_SECRET": "test-oauth-secret-value-that-is-long-enough",
        "LLM_PROVIDER_MODE": "direct",
        "LLM_DIRECT_PROVIDER": "anthropic",
        "ANTHROPIC_API_KEY": "anthropic-key",
        "ENVIRONMENT": "test",
        "RATE_LIMIT_ENABLED": True,
        "RATE_LIMIT_STORE_MODE": "memory",
        "RATE_LIMIT_ATHLETE_CHAT_MAX_REQUESTS": 1,
        "RATE_LIMIT_ATHLETE_CHAT_WINDOW_SECONDS": 60,
        "RATE_LIMIT_AUTH_MAX_REQUESTS": 1,
        "RATE_LIMIT_AUTH_WINDOW_SECONDS": 60,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def _request(host: str = "203.0.113.10") -> SimpleNamespace:
    return SimpleNamespace(
        client=SimpleNamespace(host=host),
        method="POST",
        url=SimpleNamespace(path="/api/v1/conversations"),
        state=SimpleNamespace(request_id="req-123"),
    )


@pytest.mark.asyncio
async def test_rate_limit_service_blocks_user_policy_after_window_budget() -> None:
    settings = _settings()
    store = InMemoryRateLimitStore(clock=lambda: 1000.0)
    service = RateLimitService(settings=settings, store=store)
    user = SimpleNamespace(id=uuid4(), organization_id=uuid4())

    await service.enforce(
        RateLimitPolicy.ATHLETE_CHAT,
        request=_request(),
        user=user,
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.enforce(
            RateLimitPolicy.ATHLETE_CHAT,
            request=_request(),
            user=user,
        )

    assert exc_info.value.status_code == 429
    assert exc_info.value.headers == {"Retry-After": "60"}
    assert "203.0.113.10" not in repr(store._hits)


@pytest.mark.asyncio
async def test_rate_limit_service_hashes_unauthenticated_ip_subjects() -> None:
    settings = _settings()
    store = InMemoryRateLimitStore(clock=lambda: 1000.0)
    service = RateLimitService(settings=settings, store=store)

    await service.enforce(RateLimitPolicy.AUTH, request=_request("198.51.100.3"))

    assert list(store._hits) == [
        "rate-limit:auth:ip:cd4347f512cfb64d338784e8bb96703a"
    ]
