"""CORS middleware configuration."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings


def setup_cors(app: FastAPI) -> None:
    """Configure CORS middleware.

    Origins come from environment config (CORS_ORIGINS). In production, ensure
    CORS_ORIGINS is explicitly set to allowed domains only (no wildcards).
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-New-Token"],
    )
