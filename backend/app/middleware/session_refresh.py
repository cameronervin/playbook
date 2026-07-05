"""Apply app-session cookie refresh and clear actions after auth dependencies run."""

from __future__ import annotations

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.auth.session import clear_access_token_cookie, set_access_token_cookie
from app.core.config import Settings


class SessionRefreshMiddleware(BaseHTTPMiddleware):
    """Attach pending app-session cookie changes to the outgoing response."""

    def __init__(self, app, settings: Settings) -> None:
        super().__init__(app)
        self.settings = settings

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        response = await call_next(request)
        if getattr(request.state, "clear_access_token_cookie", False):
            clear_access_token_cookie(response, self.settings)
            return response
        refreshed_token = getattr(request.state, "refreshed_access_token", None)
        if isinstance(refreshed_token, str) and refreshed_token:
            set_access_token_cookie(response, refreshed_token, self.settings)
        return response


def setup_session_refresh(app: FastAPI, settings: Settings) -> None:
    """Register session refresh response middleware."""
    app.add_middleware(SessionRefreshMiddleware, settings=settings)
