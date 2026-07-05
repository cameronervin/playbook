"""Application-level rate limiting for release-readiness gates."""

from __future__ import annotations

import hashlib
import hmac
import math
import time
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

import structlog
from fastapi import HTTPException, Request, status

from app.core.config import Settings
from app.models.identity import User

logger = structlog.get_logger(__name__)

_KEY_PREFIX = "rate-limit"
_store_cache: dict[str, RateLimitStore] = {}


class RateLimitPolicy(StrEnum):
    """Named app-level limit buckets."""

    AUTH = "auth"
    ATHLETE_CHAT = "athlete_chat"
    ADMIN_CHAT = "admin_chat"
    INSIGHT_RUN = "insight_run"
    UPLOAD = "upload"
    LIST = "list"


@dataclass(frozen=True)
class RateLimitDecision:
    """Outcome for one policy hit."""

    allowed: bool
    remaining: int
    retry_after_seconds: int


class RateLimitStore(Protocol):
    """Storage backend for rate-limit counters."""

    async def hit(
        self,
        *,
        key: str,
        max_requests: int,
        window_seconds: int,
    ) -> RateLimitDecision:
        """Record a request and return whether it fits the active window."""


class InMemoryRateLimitStore:
    """Process-local sliding-window store for tests and single-process dev."""

    def __init__(self, *, clock: Callable[[], float] | None = None) -> None:
        self._clock = clock or time.monotonic
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    async def hit(
        self,
        *,
        key: str,
        max_requests: int,
        window_seconds: int,
    ) -> RateLimitDecision:
        now = self._clock()
        cutoff = now - window_seconds
        bucket = self._hits[key]
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if len(bucket) >= max_requests:
            retry_after = _retry_after(bucket[0], now, window_seconds)
            return RateLimitDecision(
                allowed=False,
                remaining=0,
                retry_after_seconds=retry_after,
            )
        bucket.append(now)
        return RateLimitDecision(
            allowed=True,
            remaining=max(0, max_requests - len(bucket)),
            retry_after_seconds=0,
        )


class ValkeyRateLimitStore:
    """Valkey-backed sliding-window store shared by API replicas."""

    def __init__(self, *, redis_url: str) -> None:
        self.redis_url = redis_url
        self._redis_client: object | None = None

    async def hit(
        self,
        *,
        key: str,
        max_requests: int,
        window_seconds: int,
    ) -> RateLimitDecision:
        client = self._get_client()
        now_ms = int(time.time() * 1000)
        cutoff_ms = now_ms - window_seconds * 1000
        member = f"{now_ms}:{time.monotonic_ns()}"

        pipe = client.pipeline()
        pipe.zremrangebyscore(key, 0, cutoff_ms)
        pipe.zadd(key, {member: now_ms})
        pipe.zcard(key)
        pipe.expire(key, window_seconds * 2)
        _, _, count, _ = await pipe.execute()

        count_int = int(count)
        if count_int <= max_requests:
            return RateLimitDecision(
                allowed=True,
                remaining=max(0, max_requests - count_int),
                retry_after_seconds=0,
            )

        await client.zrem(key, member)
        oldest = await client.zrange(key, 0, 0, withscores=True)
        retry_after = _retry_after_from_valkey(oldest, now_ms, window_seconds)
        return RateLimitDecision(
            allowed=False,
            remaining=0,
            retry_after_seconds=retry_after,
        )

    async def close(self) -> None:
        """Close the underlying Redis client when one has been created."""
        if self._redis_client is not None:
            await self._redis_client.aclose()
            self._redis_client = None

    def _get_client(self):
        if self._redis_client is None:
            import redis.asyncio as redis

            self._redis_client = redis.from_url(
                self.redis_url,
                decode_responses=True,
            )
        return self._redis_client


class RateLimitService:
    """Enforce named rate-limit policies without inspecting request bodies."""

    def __init__(self, *, settings: Settings, store: RateLimitStore) -> None:
        self.settings = settings
        self.store = store

    async def enforce(
        self,
        policy: RateLimitPolicy,
        *,
        request: Request,
        user: User | None = None,
    ) -> None:
        """Raise 429 if a request exceeds its configured policy window."""
        if not self.settings.RATE_LIMIT_ENABLED:
            return
        max_requests, window_seconds = self._policy_limits(policy)
        subject = self._subject(policy=policy, request=request, user=user)
        key = f"{_KEY_PREFIX}:{policy.value}:{subject}"
        decision = await self.store.hit(
            key=key,
            max_requests=max_requests,
            window_seconds=window_seconds,
        )
        if decision.allowed:
            return

        request_id = getattr(request.state, "request_id", None)
        organization_id = str(user.organization_id) if user is not None else None
        user_id = str(user.id) if user is not None else None
        logger.warning(
            "rate_limit_exceeded",
            policy=policy.value,
            request_id=request_id,
            organization_id=organization_id,
            user_id=user_id,
            subject_hash=_hash_subject(subject, self.settings.SECRET_KEY),
            retry_after_seconds=decision.retry_after_seconds,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(decision.retry_after_seconds)},
        )

    def _policy_limits(self, policy: RateLimitPolicy) -> tuple[int, int]:
        max_requests = getattr(
            self.settings,
            f"RATE_LIMIT_{policy.value.upper()}_MAX_REQUESTS",
        )
        window_seconds = getattr(
            self.settings,
            f"RATE_LIMIT_{policy.value.upper()}_WINDOW_SECONDS",
        )
        return int(max_requests), int(window_seconds)

    def _subject(
        self,
        *,
        policy: RateLimitPolicy,
        request: Request,
        user: User | None,
    ) -> str:
        if user is not None:
            return f"org:{user.organization_id}:user:{user.id}"
        client_host = request.client.host if request.client else "unknown"
        return f"ip:{_hash_subject(client_host, self.settings.SECRET_KEY)}"


def get_rate_limit_store(settings: Settings) -> RateLimitStore:
    """Return the configured rate-limit store singleton."""
    cache_key = f"{settings.RATE_LIMIT_STORE_MODE}:{settings.RATE_LIMIT_VALKEY_URL}"
    if cache_key not in _store_cache:
        if settings.RATE_LIMIT_STORE_MODE == "memory":
            _store_cache[cache_key] = InMemoryRateLimitStore()
        else:
            _store_cache[cache_key] = ValkeyRateLimitStore(
                redis_url=settings.RATE_LIMIT_VALKEY_URL
            )
    return _store_cache[cache_key]


async def cleanup_rate_limit_stores() -> None:
    """Close cached rate-limit stores that own external resources."""
    for store in _store_cache.values():
        close = getattr(store, "close", None)
        if close is not None:
            await close()
    clear_rate_limit_store_cache()


def clear_rate_limit_store_cache() -> None:
    """Clear cached stores for tests."""
    _store_cache.clear()


def _hash_subject(value: str, secret_key: str) -> str:
    return hmac.new(
        secret_key.encode(),
        value.encode(),
        hashlib.sha256,
    ).hexdigest()[:32]


def _retry_after(first_hit: float, now: float, window_seconds: int) -> int:
    return max(1, math.ceil((first_hit + window_seconds) - now))


def _retry_after_from_valkey(
    oldest: object,
    now_ms: int,
    window_seconds: int,
) -> int:
    if not oldest:
        return window_seconds
    try:
        oldest_ms = int(oldest[0][1])  # type: ignore[index]
    except (TypeError, ValueError, IndexError):
        return window_seconds
    wait_ms = (oldest_ms + window_seconds * 1000) - now_ms
    return max(1, math.ceil(wait_ms / 1000))
