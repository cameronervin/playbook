"""Privacy-safe Sentry initialization for KB API and worker processes."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import structlog

from app.core.config import Settings
from app.core.log_redaction import REDACTION, redact_secrets

logger = structlog.get_logger(__name__)

_initialized_services: set[str] = set()

_CONTENT_FIELD_NAMES = {
    "answer",
    "body",
    "chunk_text",
    "completion",
    "completions",
    "content",
    "contents",
    "document_text",
    "extracted_text",
    "file_contents",
    "input",
    "inputs",
    "model_input",
    "model_inputs",
    "model_output",
    "model_outputs",
    "output",
    "outputs",
    "prompt",
    "prompts",
    "raw_text",
    "response",
    "responses",
    "source_text",
    "source_texts",
    "summary_input",
    "text",
    "tool_input",
    "tool_inputs",
    "tool_output",
    "tool_outputs",
}

_LOCAL_VARIABLE_FIELD_NAMES = {"local_variables", "locals", "vars"}

_SENSITIVE_FIELD_PARTS = {
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "database_url",
    "db_url",
    "password",
    "passwd",
    "presigned_url",
    "private_key",
    "secret",
    "signature",
    "signed_url",
    "source_uri",
    "token",
}

_RAW_IP_FIELD_NAMES = {
    "cf_connecting_ip",
    "client_ip",
    "forwarded",
    "ip_address",
    "remote_addr",
    "remote_ip",
    "true_client_ip",
    "x_forwarded_for",
    "x_real_ip",
}

_SENSITIVE_HEADERS = {
    "authorization",
    "cookie",
    "forwarded",
    "set-cookie",
    "x-forwarded-for",
    "x-real-ip",
    "cf-connecting-ip",
    "true-client-ip",
}


def init_sentry(
    settings: Settings,
    *,
    service_name: str,
    include_fastapi: bool = False,
    include_celery: bool = False,
) -> bool:
    """Initialize Sentry once for a process/service."""
    if service_name in _initialized_services:
        return True
    if not settings.SENTRY_ENABLED:
        logger.info("sentry_disabled", service=service_name)
        return False
    if not settings.SENTRY_DSN:
        logger.warning("sentry_disabled_missing_dsn", service=service_name)
        return False

    sentry_sdk = _load_sentry_sdk()
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.SENTRY_ENVIRONMENT or settings.ENVIRONMENT,
        release=settings.SENTRY_RELEASE or None,
        send_default_pii=False,
        max_request_body_size="never",
        include_local_variables=False,
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
        profiles_sample_rate=settings.SENTRY_PROFILES_SAMPLE_RATE,
        integrations=_build_integrations(
            include_fastapi=include_fastapi,
            include_celery=include_celery,
        ),
        before_send=scrub_sentry_event,
        before_send_transaction=scrub_sentry_event,
    )
    sentry_sdk.set_tag("service", service_name)
    sentry_sdk.set_tag("app", "playbook-kb")
    _initialized_services.add(service_name)
    logger.info("sentry_initialized", service=service_name)
    return True


def capture_exception(exc: BaseException) -> None:
    """Capture an exception when Sentry is initialized, without affecting users."""
    if not _initialized_services:
        return
    try:
        _load_sentry_sdk().capture_exception(exc)
    except Exception as capture_error:  # noqa: BLE001
        logger.warning("sentry_capture_failed", error=str(capture_error))


def scrub_sentry_event(
    event: dict[str, Any],
    hint: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Remove secrets and user-authored content from Sentry events."""
    del hint
    scrubbed = _scrub_value(redact_secrets(event))
    if not isinstance(scrubbed, dict):
        return None

    scrubbed.pop("user", None)
    request = scrubbed.get("request")
    if isinstance(request, dict):
        _scrub_request(request)
    return scrubbed


def _scrub_request(request: dict[str, Any]) -> None:
    for key in ("cookies", "data", "env", "json"):
        request.pop(key, None)
    if "query_string" in request:
        request["query_string"] = REDACTION
    headers = request.get("headers")
    if isinstance(headers, dict):
        for key in list(headers.keys()):
            if str(key).lower() in _SENSITIVE_HEADERS:
                headers[key] = REDACTION


def _scrub_value(value: Any, key: str | None = None) -> Any:
    normalized_key = _normalize_key(key)
    if normalized_key and _should_redact_field(normalized_key):
        return REDACTION
    if isinstance(value, Mapping):
        return {item_key: _scrub_value(item, str(item_key)) for item_key, item in value.items()}
    if isinstance(value, tuple):
        return tuple(_scrub_value(item) for item in value)
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        return [_scrub_value(item) for item in value]
    return value


def _should_redact_field(normalized_key: str) -> bool:
    return (
        normalized_key in _CONTENT_FIELD_NAMES
        or normalized_key in _LOCAL_VARIABLE_FIELD_NAMES
        or normalized_key in _RAW_IP_FIELD_NAMES
        or normalized_key.endswith("_ip")
        or any(part in normalized_key for part in _SENSITIVE_FIELD_PARTS)
    )


def _normalize_key(key: str | None) -> str:
    return "" if key is None else key.lower().replace("-", "_")


def _build_integrations(
    *,
    include_fastapi: bool,
    include_celery: bool,
) -> list[object]:
    integrations: list[object] = []
    if include_fastapi:
        from sentry_sdk.integrations.fastapi import FastApiIntegration  # noqa: PLC0415
        from sentry_sdk.integrations.starlette import (  # noqa: PLC0415
            StarletteIntegration,
        )

        integrations.extend([StarletteIntegration(), FastApiIntegration()])
    if include_celery:
        from sentry_sdk.integrations.celery import CeleryIntegration  # noqa: PLC0415

        integrations.append(CeleryIntegration(propagate_traces=True))
    return integrations


def _load_sentry_sdk() -> Any:
    import sentry_sdk  # noqa: PLC0415

    return sentry_sdk


def _reset_sentry_state_for_tests() -> None:
    _initialized_services.clear()
