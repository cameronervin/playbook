from __future__ import annotations

from playbook_load_tests.auth import BearerTokenPool, redact_sensitive_text


def test_bearer_pool_rotates_tokens_and_formats_auth_header() -> None:
    pool = BearerTokenPool(["token-one", "token-two"])

    assert pool.next_header() == {"Authorization": "Bearer token-one"}
    assert pool.next_header() == {"Authorization": "Bearer token-two"}
    assert pool.next_header() == {"Authorization": "Bearer token-one"}


def test_redaction_masks_bearer_tokens_cookies_and_signed_url_fields() -> None:
    text = (
        "Authorization: Bearer secret-token Cookie: access_token=session-value "
        "https://bucket/key?X-Amz-Signature=abc&token=xyz"
    )

    redacted = redact_sensitive_text(text)

    assert "secret-token" not in redacted
    assert "session-value" not in redacted
    assert "abc" not in redacted
    assert "xyz" not in redacted
    assert "Bearer [redacted]" in redacted
