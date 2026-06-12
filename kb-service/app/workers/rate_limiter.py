"""Distributed embedding upstream rate limiter — sliding-window RPM + concurrent cap.

Embedding upstreams (LiteLLM proxy, OpenAI direct, etc.) enforce per-key caps:
  • an RPM ceiling on the embedding endpoint
  • a small number of concurrent requests per API key
Exceeding either triggers 429s, which cascade into retries → reissues → queue
explosions. Celery's built-in ``rate_limit`` is per-worker-instance and uses a
token bucket that starts full, so it does not prevent the initial burst when
``group(...).apply_async()`` fans out many batches simultaneously.

This module enforces both caps in Valkey/Redis so all worker threads (and any
future multi-worker deployment) share the same limit globally.

``redis`` is imported lazily (via the Celery result-backend client) so this
module compiles without redis installed and opens no connection at import time.

Usage::

    acquire_embed_slot()
    try:
        embeddings = client.embed(texts)  # sync OpenAI client
    finally:
        release_embed_slot()
"""

from __future__ import annotations

import time
import uuid

import structlog

logger = structlog.get_logger(__name__)

# --- Config ---------------------------------------------------------------
# Conservative throughput defaults — tune to your upstream's confirmed caps.
#
# Three gates layered together (all must pass before an embed call):
#   1. Min-spacing tick   — 1 sec between successive call STARTS (anti-burst)
#   2. RPM sliding window — N calls per rolling 60s
#   3. Concurrent counter — M in-flight at a time
#
# Throughput is usually latency-bound; the RPM cap is rarely the bottleneck on
# the hot path — but still enforced as a hard ceiling for safety.
_TICK_SECONDS = 1                  # 1-sec min spacing between call starts
_MAX_RPM = 70                      # rolling-window ceiling (set under upstream cap)
_MAX_CONCURRENT = 3                # matches kb-io worker concurrency
_WINDOW_SECONDS = 60
_INFLIGHT_TTL_SECONDS = 60         # crashed-worker recovery
_MAX_WAIT_SECONDS = 300            # 5 min wait timeout
_POLL_MIN_SECONDS = 0.1
_POLL_MAX_SECONDS = 2.0

# --- Valkey/Redis keys (neutral kb: namespace) ----------------------------
_TICK_KEY = "kb:embed:tick"             # STRING set with 1s TTL (anti-burst)
_RPM_KEY = "kb:embed:rpm_window"        # ZSET of "ts_ms:uuid" → ts_ms
_INFLIGHT_KEY = "kb:embed:inflight"     # INT counter


def _redis_client():
    """Reuse Celery's result-backend redis pool (lazy — no import-time connection)."""
    from celery import current_app

    return current_app.backend.client


def _wait_for_rpm_slot(client) -> bool:
    """Check rolling window. Return True if a slot is available, else sleep+False."""
    now_ms = int(time.time() * 1000)
    cutoff_ms = now_ms - _WINDOW_SECONDS * 1000

    pipe = client.pipeline()
    pipe.zremrangebyscore(_RPM_KEY, 0, cutoff_ms)
    pipe.zcard(_RPM_KEY)
    _, rpm_count = pipe.execute()

    if int(rpm_count) < _MAX_RPM:
        return True

    # Window full — sleep until the oldest entry ages out.
    oldest = client.zrange(_RPM_KEY, 0, 0, withscores=True)
    if oldest:
        oldest_ms = int(oldest[0][1])
        wait_ms = (oldest_ms + _WINDOW_SECONDS * 1000) - now_ms
        wait_s = max(_POLL_MIN_SECONDS, min(_POLL_MAX_SECONDS, wait_ms / 1000.0))
    else:
        wait_s = 0.5
    time.sleep(wait_s)
    return False


def _try_acquire_tick(client) -> bool:
    """Atomic min-spacing gate: claim the 1-second tick slot if free.

    Uses Redis ``SET key value EX 1 NX`` — first caller in a second wins, others
    get None back and must sleep until the TTL expires. This gives a strict
    1-call-per-second ceiling globally across all worker threads.
    """
    # ``set`` with nx=True returns True if set, None if key already exists.
    return client.set(_TICK_KEY, "1", ex=_TICK_SECONDS, nx=True) is True


def _try_acquire_concurrent_slot(client) -> bool:
    """Atomically INCR the in-flight counter; rollback if over cap."""
    inflight = client.incr(_INFLIGHT_KEY)
    client.expire(_INFLIGHT_KEY, _INFLIGHT_TTL_SECONDS)
    if int(inflight) > _MAX_CONCURRENT:
        client.decr(_INFLIGHT_KEY)
        return False
    return True


def acquire_embed_slot() -> None:
    """Block until both RPM and concurrent gates allow a request.

    Records the call in the RPM sliding window on success. Caller MUST pair
    with ``release_embed_slot()`` (use try/finally) to decrement the in-flight
    counter, otherwise the concurrency budget will leak until the safety TTL
    expires.

    Raises RuntimeError if no slot becomes available within _MAX_WAIT_SECONDS.
    """
    client = _redis_client()
    deadline = time.monotonic() + _MAX_WAIT_SECONDS

    while time.monotonic() < deadline:
        # Gate 1: strict 1-call-per-second tick (anti-burst).
        if not _try_acquire_tick(client):
            time.sleep(0.1)
            continue

        # Gate 2: rolling 60s window (smooths sustained rate).
        if not _wait_for_rpm_slot(client):
            continue

        # Gate 3: in-flight concurrent cap (matches upstream hard limit).
        if not _try_acquire_concurrent_slot(client):
            time.sleep(0.2)
            continue

        # All gates passed — stamp the RPM window and proceed.
        now_ms = int(time.time() * 1000)
        marker = f"{now_ms}:{uuid.uuid4().hex[:8]}"
        client.zadd(_RPM_KEY, {marker: now_ms})
        client.expire(_RPM_KEY, _WINDOW_SECONDS * 2)
        return

    raise RuntimeError(
        f"Timed out after {_MAX_WAIT_SECONDS}s waiting for embedding rate-limit slot"
    )


def release_embed_slot() -> None:
    """Decrement the in-flight counter. Idempotent and safe on Redis failure."""
    try:
        client = _redis_client()
        current = client.decr(_INFLIGHT_KEY)
        if current is not None and int(current) < 0:
            # Floor at 0 — double-release or TTL race recovery.
            client.set(_INFLIGHT_KEY, 0, ex=_INFLIGHT_TTL_SECONDS)
    except Exception as exc:
        logger.warning("kb_embed_slot_release_failed", error=str(exc))
