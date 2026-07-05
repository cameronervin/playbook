"""Authentication helpers for Playbook Locust scenarios."""

from __future__ import annotations

import itertools
import re
from collections.abc import Iterable
from dataclasses import dataclass
from urllib.parse import urlparse

_SENSITIVE_QUERY_KEYS = (
    "X-Amz-Credential",
    "X-Amz-Security-Token",
    "X-Amz-Signature",
    "AWSAccessKeyId",
    "Signature",
    "token",
    "access_token",
    "authorization",
    "credential",
    "signature",
)


@dataclass(frozen=True)
class BearerTokenPool:
    """Round-robin bearer-token source that never exposes values in repr output."""

    values: tuple[str, ...]

    def __init__(self, values: Iterable[str]) -> None:
        clean_values = tuple(value.strip() for value in values if value.strip())
        object.__setattr__(self, "values", clean_values)
        iterator = itertools.cycle(clean_values) if clean_values else None
        object.__setattr__(self, "_iterator", iterator)

    def __bool__(self) -> bool:
        return bool(self.values)

    def __repr__(self) -> str:
        return f"BearerTokenPool(count={len(self.values)})"

    def next_header(self) -> dict[str, str]:
        """Return an Authorization header for the next token."""
        if self._iterator is None:
            return {}
        token = next(self._iterator)
        return {"Authorization": f"Bearer {token}"}


def callback_path_from_authorization_url(authorization_url: str) -> str:
    """Convert a dev-auth callback URL to a path safe for the Locust client."""
    parsed = urlparse(authorization_url)
    if not parsed.path:
        return authorization_url
    suffix = f"?{parsed.query}" if parsed.query else ""
    return f"{parsed.path}{suffix}"


def redact_sensitive_text(value: str) -> str:
    """Mask bearer tokens, cookies, and signed-URL style query fields."""
    redacted = re.sub(
        r"Bearer\s+[A-Za-z0-9._~+/=-]+",
        "Bearer [redacted]",
        value,
        flags=re.IGNORECASE,
    )
    redacted = re.sub(
        r"(Cookie:\s*[^=\s;]+)=([^;\s]+)",
        r"\1=[redacted]",
        redacted,
        flags=re.IGNORECASE,
    )
    redacted = re.sub(
        r"((?:^|[;\s])access_token=)[^;\s]+",
        r"\1[redacted]",
        redacted,
        flags=re.IGNORECASE,
    )
    for key in _SENSITIVE_QUERY_KEYS:
        redacted = re.sub(
            rf"({re.escape(key)}=)[^&\s\"']+",
            r"\1[redacted]",
            redacted,
            flags=re.IGNORECASE,
        )
    return redacted
