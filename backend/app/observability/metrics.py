"""Metrics collection via structured logging.

Tracks LLM request metrics through structlog so they can be parsed by log
aggregators (Datadog, CloudWatch, ELK). For Prometheus, add prometheus_client
counters/histograms here and increment them alongside the log calls.
"""
import structlog

logger = structlog.get_logger()


def track_llm_request(
    model: str,
    provider: str,
    status: str,
    tokens: int,
    cost_usd: float,
    response_time_ms: int,
) -> None:
    """Track LLM request metrics via structured logging.

    Args:
        model: Model name/identifier.
        provider: Provider name (e.g. 'direct', 'gateway').
        status: Outcome status (e.g. 'success', 'error').
        tokens: Total tokens consumed.
        cost_usd: Estimated cost in USD.
        response_time_ms: Round-trip latency in milliseconds.
    """
    logger.info(
        "llm_request",
        model=model,
        provider=provider,
        status=status,
        tokens=tokens,
        cost_usd=cost_usd,
        response_time_ms=response_time_ms,
    )


def track_request(method: str, path: str, status_code: int, duration_ms: int) -> None:
    """Track an HTTP request's outcome via structured logging."""
    logger.info(
        "http_request",
        method=method,
        path=path,
        status_code=status_code,
        duration_ms=duration_ms,
    )
