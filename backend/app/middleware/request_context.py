"""Request context middleware."""

from __future__ import annotations

from time import perf_counter
from uuid import uuid4

import structlog
from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

logger = structlog.get_logger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Bind request-scoped structured logging context."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid4())
        request.state.request_id = request_id
        start = perf_counter()
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        try:
            response = await call_next(request)
        finally:
            duration_ms = round((perf_counter() - start) * 1000, 2)
            structlog.contextvars.unbind_contextvars("method", "path")

        response.headers[REQUEST_ID_HEADER] = request_id
        logger.info(
            "http_request_completed",
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        structlog.contextvars.clear_contextvars()
        return response


def setup_request_context(app: FastAPI) -> None:
    """Register request context middleware."""
    app.add_middleware(RequestContextMiddleware)
