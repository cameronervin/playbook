"""Rate limiting middleware for LLM endpoints.

Placeholder middleware. Enforce real per-user rate limits in the service layer
(reading counters from the DB or Redis); this hook is for cross-cutting concerns
like adding X-RateLimit-* response headers and logging.
"""
import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

logger = structlog.get_logger()


class LLMRateLimitMiddleware(BaseHTTPMiddleware):
    """Observe LLM-related requests; reserved for future rate-limit headers."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        is_llm_endpoint = (
            "/api/v1/llm" in request.url.path
            or "/api/v1/chat" in request.url.path
        )

        if is_llm_endpoint:
            logger.debug("llm_request_received", path=request.url.path, method=request.method)

        # Actual rate limiting is enforced in the service layer, not here.
        return await call_next(request)
