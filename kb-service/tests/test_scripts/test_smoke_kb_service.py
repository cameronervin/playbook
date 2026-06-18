from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import httpx

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "smoke_kb_service.py"


def _load_smoke_module():
    spec = importlib.util.spec_from_file_location("smoke_kb_service", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_auth_headers_use_bearer_secret_without_extra_fields() -> None:
    smoke = _load_smoke_module()

    assert smoke._auth_headers("secret-value") == {
        "Authorization": "Bearer secret-value"
    }


def test_build_source_uri_uses_path_style_endpoint_without_query_secrets() -> None:
    smoke = _load_smoke_module()
    settings = SimpleNamespace(
        S3_BUCKET_NAME="playbook-bucket",
        S3_ENDPOINT_URL="http://localhost:9000/",
        S3_REGION="us-east-1",
    )

    source_uri = smoke._build_source_uri(
        settings,
        "kb-smoke/test id/nil smoke.docx",
    )

    assert source_uri == (
        "http://localhost:9000/playbook-bucket/"
        "kb-smoke/test%20id/nil%20smoke.docx"
    )
    assert "X-Amz" not in source_uri


def test_build_source_uri_uses_virtual_hosted_aws_when_endpoint_is_empty() -> None:
    smoke = _load_smoke_module()
    settings = SimpleNamespace(
        S3_BUCKET_NAME="playbook-bucket",
        S3_ENDPOINT_URL="",
        S3_REGION="us-west-2",
    )

    source_uri = smoke._build_source_uri(settings, "kb-smoke/test.docx")

    assert source_uri == (
        "https://playbook-bucket.s3.us-west-2.amazonaws.com/kb-smoke/test.docx"
    )


def test_stage_summary_is_safe_and_compact() -> None:
    smoke = _load_smoke_module()

    summary = smoke._stage_summary(
        {
            "stages": [
                {"stage": "parse", "status": "success", "task_id": "secret-ish-id"},
                {"stage": "chunk", "status": None, "task_id": None},
            ]
        }
    )

    assert summary == "parse=success, chunk=pending"
    assert "secret-ish-id" not in summary


def test_extract_matching_results_finds_smoke_text_case_insensitively() -> None:
    smoke = _load_smoke_module()

    results = smoke._matching_results(
        {
            "results": [
                {"text": "Other content", "score": 0.9},
                {"text": "Athletes must DISCLOSE NIL deals.", "score": 0.8},
            ],
        }
    )

    assert results == [{"text": "Athletes must DISCLOSE NIL deals.", "score": 0.8}]


def test_extract_matching_results_accepts_private_terms() -> None:
    smoke = _load_smoke_module()

    results = smoke._matching_results(
        {
            "results": [
                {"text": "Shared NIL disclosure policy.", "score": 0.9},
                {
                    "text": "Private approval clause requires department review.",
                    "score": 0.8,
                },
            ],
        },
        terms=("private", "approval", "clause"),
    )

    assert results == [
        {
            "text": "Private approval clause requires department review.",
            "score": 0.8,
        }
    ]


def test_rerank_metadata_assertion_is_noop_when_rerank_disabled() -> None:
    smoke = _load_smoke_module()
    settings = SimpleNamespace(KB_SEARCH_STRATEGY="hybrid", KB_RERANK_ENABLED=False)

    smoke._assert_rerank_metadata_if_enabled(
        [{"metadata": {"ranking_strategy": "hybrid"}}],
        settings,
    )


def test_rerank_metadata_assertion_passes_when_hybrid_rerank_present() -> None:
    smoke = _load_smoke_module()
    settings = SimpleNamespace(KB_SEARCH_STRATEGY="hybrid", KB_RERANK_ENABLED=True)

    smoke._assert_rerank_metadata_if_enabled(
        [{"metadata": {"ranking_strategy": "hybrid_rerank"}}],
        settings,
    )


def test_rerank_metadata_assertion_fails_when_enabled_but_missing() -> None:
    smoke = _load_smoke_module()
    settings = SimpleNamespace(KB_SEARCH_STRATEGY="hybrid", KB_RERANK_ENABLED=True)

    try:
        smoke._assert_rerank_metadata_if_enabled(
            [{"metadata": {"ranking_strategy": "hybrid"}}],
            settings,
        )
    except smoke.SmokeTestError as exc:
        assert "ranking_strategy=hybrid_rerank" in str(exc)
    else:
        raise AssertionError("expected SmokeTestError")


def test_rerank_fail_open_assertion_requires_hybrid_metadata() -> None:
    smoke = _load_smoke_module()
    settings = SimpleNamespace(KB_SEARCH_STRATEGY="hybrid", KB_RERANK_ENABLED=True)

    smoke._assert_rerank_fail_open_metadata_if_expected(
        [{"metadata": {"ranking_strategy": "hybrid", "rerank_score": None}}],
        settings,
        expect_fail_open=True,
    )

    try:
        smoke._assert_rerank_fail_open_metadata_if_expected(
            [{"metadata": {"ranking_strategy": "hybrid_rerank", "rerank_score": 0.91}}],
            settings,
            expect_fail_open=True,
        )
    except smoke.SmokeTestError as exc:
        assert "fail-open" in str(exc)
    else:
        raise AssertionError("expected SmokeTestError")


def test_rerank_metadata_assertion_skips_success_requirement_for_fail_open() -> None:
    smoke = _load_smoke_module()
    settings = SimpleNamespace(KB_SEARCH_STRATEGY="hybrid", KB_RERANK_ENABLED=True)

    smoke._assert_rerank_metadata(
        [{"metadata": {"ranking_strategy": "hybrid", "rerank_score": None}}],
        settings,
        expect_fail_open=True,
    )


def test_litellm_rerank_payload_uses_alias_without_raw_source_metadata() -> None:
    smoke = _load_smoke_module()
    settings = SimpleNamespace(LITELLM_RERANK_MODEL="playbook-rerank")

    payload = smoke._litellm_rerank_payload(settings)

    assert payload["model"] == "playbook-rerank"
    assert payload["top_n"] == 2
    assert len(payload["documents"]) == 3
    assert "source_uri" not in repr(payload)
    assert "signature=" not in repr(payload)


def test_litellm_rerank_check_posts_to_proxy_and_validates_response(
    monkeypatch,
) -> None:
    smoke = _load_smoke_module()
    settings = SimpleNamespace(
        LITELLM_BASE_URL="http://litellm:4000/",
        LITELLM_API_KEY="litellm-key",
        LITELLM_RERANK_MODEL="playbook-rerank",
    )
    emitted: list[str] = []
    requests: list[dict] = []

    class FakeClient:
        def __init__(self, *, base_url: str, timeout: float) -> None:
            self.base_url = base_url
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

        def request(self, method, path, *, headers=None, json=None):
            requests.append(
                {"method": method, "path": path, "headers": headers, "json": json}
            )
            return httpx.Response(
                200,
                json={"results": [{"index": 0, "relevance_score": 0.99}]},
            )

    monkeypatch.setattr(smoke.httpx, "Client", FakeClient)
    monkeypatch.setattr(smoke, "_emit", emitted.append)

    smoke._check_litellm_rerank(settings)

    assert requests[0]["method"] == "POST"
    assert requests[0]["path"] == "/rerank"
    assert requests[0]["headers"] == {"Authorization": "Bearer litellm-key"}
    assert requests[0]["json"]["model"] == "playbook-rerank"
    assert emitted == ["  litellm_rerank=ok"]


def test_litellm_rerank_check_rejects_unranked_nil_document() -> None:
    smoke = _load_smoke_module()

    try:
        smoke._assert_litellm_rerank_response(
            {"results": [{"index": 2, "relevance_score": 0.99}]}
        )
    except smoke.SmokeTestError as exc:
        assert "expected NIL disclosure document" in str(exc)
    else:
        raise AssertionError("expected SmokeTestError")


def test_parse_args_supports_conversation_file_smoke_flag() -> None:
    smoke = _load_smoke_module()

    args = smoke._parse_args(
        [
            "--include-conversation-file",
            "--check-litellm-rerank",
            "--expect-rerank-fail-open",
        ]
    )

    assert args.include_conversation_file is True
    assert args.check_litellm_rerank is True
    assert args.expect_rerank_fail_open is True
