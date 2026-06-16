from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

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


def test_parse_args_supports_conversation_file_smoke_flag() -> None:
    smoke = _load_smoke_module()

    args = smoke._parse_args(["--include-conversation-file"])

    assert args.include_conversation_file is True
