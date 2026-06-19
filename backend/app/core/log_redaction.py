"""Secret redaction helpers for structured logs and error messages."""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

REDACTION = "[REDACTED]"

_SENSITIVE_KEY_PARTS = (
    "api_key",
    "apikey",
    "secret",
    "token",
    "password",
    "passwd",
    "authorization",
    "signature",
    "database_url",
    "db_url",
    "access_key",
    "private_key",
    "source_uri",
    "presigned_url",
    "signed_url",
    "raw_text",
    "extracted_text",
    "file_contents",
    "model_input",
    "model_inputs",
)

_ASSIGNMENT_RE = re.compile(
    r"(?i)\b("
    r"[A-Z0-9_]*(?:API_KEY|APIKEY|SECRET|TOKEN|PASSWORD|PASSWD|DATABASE_URL|DB_URL|"
    r"AUTHORIZATION|SIGNATURE|ACCESS_KEY|PRIVATE_KEY)[A-Z0-9_]*"
    r"\s*[:=]\s*)"
    r"([^,&?\s;}]+)"
)
_BEARER_RE = re.compile(r"(?i)(Bearer\s+)[A-Za-z0-9._~+/=-]+")
_DATABASE_URL_RE = re.compile(r"(?i)\b(postgres(?:ql)?(?:\+\w+)?://)[^,\s;}]+")
_SECRET_TOKEN_RE = re.compile(r"\b(?:sk|pk|rk|key)-[A-Za-z0-9._-]+\b")
_SENSITIVE_QUERY_RE = re.compile(
    r"(?i)(^|[?&;])((?:"
    r"state|code|token|access_token|refresh_token|id_token|signature|"
    r"x-amz-signature|x-amz-security-token|x-amz-credential"
    r")=)([^&#\s\"'<>]+)"
)


def _is_sensitive_key(key: Any) -> bool:
    normalized = str(key).lower().replace("-", "_")
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)


def redact_string(value: str) -> str:
    """Mask secret-looking values in free-form text."""
    redacted = _BEARER_RE.sub(r"\1" + REDACTION, value)
    redacted = _SENSITIVE_QUERY_RE.sub(r"\1\2" + REDACTION, redacted)
    redacted = _ASSIGNMENT_RE.sub(r"\1" + REDACTION, redacted)
    redacted = _DATABASE_URL_RE.sub(r"\1" + REDACTION, redacted)
    return _SECRET_TOKEN_RE.sub(REDACTION, redacted)


def redact_secrets(value: Any) -> Any:
    """Recursively redact secret keys and secret-looking string values."""
    if isinstance(value, str):
        return redact_string(value)
    if isinstance(value, Mapping):
        return {
            key: REDACTION if _is_sensitive_key(key) else redact_secrets(item)
            for key, item in value.items()
        }
    if isinstance(value, tuple):
        return tuple(redact_secrets(item) for item in value)
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return [redact_secrets(item) for item in value]
    return value


def redact_event_dict(
    logger: Any,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Structlog processor that redacts event payloads before rendering."""
    return redact_secrets(event_dict)
