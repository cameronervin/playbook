from __future__ import annotations

import base64
import sys
import types
from types import SimpleNamespace

import pytest

from app.infrastructure.parsers.contracts.errors import (
    OCRTimeoutError,
    UnsupportedFileTypeError,
)
from app.infrastructure.parsers.providers.ocr import build_ocr_provider
from app.infrastructure.parsers.providers.vlm import (
    VLM_OCR_NO_TEXT_SENTINEL,
    VLMOCRProvider,
)


class _FakePixmap:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def tobytes(self, output: str = "png") -> bytes:
        assert output == "png"
        return self._payload


class _FakePage:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def get_pixmap(self, *, dpi: int) -> _FakePixmap:
        assert dpi == 150
        return _FakePixmap(self._payload)


class _FakeDocument:
    def __init__(self, pages: list[_FakePage]) -> None:
        self._pages = pages

    def __enter__(self) -> "_FakeDocument":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def __len__(self) -> int:
        return len(self._pages)

    def __iter__(self):
        return iter(self._pages)


class _FakeCompletions:
    def __init__(self, responses: list[str] | None = None, error: Exception | None = None) -> None:
        self.responses = responses or []
        self.error = error
        self.requests: list[dict] = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        if self.error is not None:
            raise self.error
        content = self.responses.pop(0)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=content),
                )
            ]
        )


class _FakeClient:
    def __init__(self, completions: _FakeCompletions) -> None:
        self.chat = SimpleNamespace(completions=completions)


def _install_fake_fitz(
    monkeypatch: pytest.MonkeyPatch,
    *,
    payloads: list[bytes],
) -> None:
    fake_fitz = types.ModuleType("fitz")
    fake_fitz.open = lambda filename: _FakeDocument(
        [_FakePage(payload) for payload in payloads]
    )
    monkeypatch.setitem(sys.modules, "fitz", fake_fitz)


def test_factory_returns_vlm_provider_and_rejects_textract() -> None:
    provider = build_ocr_provider("vlm")

    assert isinstance(provider, VLMOCRProvider)
    with pytest.raises(NotImplementedError):
        build_ocr_provider("textract")


@pytest.mark.asyncio
async def test_vlm_ocr_renders_pdf_pages_and_returns_extracted_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_fitz(monkeypatch, payloads=[b"page-one", b"page-two"])
    completions = _FakeCompletions(["Student Athlete Handbook", "NIL disclosure form"])
    provider = VLMOCRProvider(client_factory=lambda: _FakeClient(completions))

    outcome = await provider.parse_pdf_high_complexity(
        path="/tmp/scanned.pdf",
        filename="scanned.pdf",
        s3_bucket=None,
        s3_key=None,
    )

    assert outcome is not None
    assert outcome.text_segments == ["Student Athlete Handbook", "NIL disclosure form"]
    assert outcome.text_segment_locators == [
        {"type": "page", "page_index": 0, "page_number": 1},
        {"type": "page", "page_index": 1, "page_number": 2},
    ]
    assert outcome.selected_parser == "vlm_ocr_pdf"
    assert outcome.reason_codes == ["vlm_ocr_selected"]
    assert outcome.quality_signals["provider"] == "vlm"
    assert outcome.quality_signals["model"] == "playbook-ocr"
    assert outcome.quality_signals["page_count"] == 2
    assert outcome.quality_signals["extracted_page_count"] == 2
    assert len(completions.requests) == 2

    first_content = completions.requests[0]["messages"][0]["content"]
    image_url = first_content[1]["image_url"]["url"]
    assert first_content[1]["type"] == "image_url"
    assert image_url.startswith("data:image/png;base64,")
    encoded = image_url.removeprefix("data:image/png;base64,")
    assert base64.b64decode(encoded) == b"page-one"


@pytest.mark.asyncio
async def test_vlm_ocr_blank_or_sentinel_output_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_fitz(monkeypatch, payloads=[b"blank-page", b"image-only"])
    completions = _FakeCompletions(["   ", VLM_OCR_NO_TEXT_SENTINEL])
    provider = VLMOCRProvider(client_factory=lambda: _FakeClient(completions))

    outcome = await provider.parse_pdf_high_complexity(
        path="/tmp/blank.pdf",
        filename="blank.pdf",
        s3_bucket=None,
        s3_key=None,
    )

    assert outcome is None


@pytest.mark.asyncio
async def test_vlm_ocr_transient_gateway_error_is_retryable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _TransientGatewayError(Exception):
        status_code = 503

    _install_fake_fitz(monkeypatch, payloads=[b"page-one"])
    completions = _FakeCompletions(error=_TransientGatewayError("gateway unavailable"))
    provider = VLMOCRProvider(client_factory=lambda: _FakeClient(completions))

    with pytest.raises(OCRTimeoutError):
        await provider.parse_pdf_high_complexity(
            path="/tmp/scanned.pdf",
            filename="scanned.pdf",
            s3_bucket=None,
            s3_key=None,
        )


@pytest.mark.asyncio
async def test_vlm_ocr_image_route_stays_out_of_scope() -> None:
    provider = VLMOCRProvider(client_factory=lambda: _FakeClient(_FakeCompletions()))

    with pytest.raises(UnsupportedFileTypeError):
        await provider.parse_image_s3(s3_bucket="bucket", s3_key="image.png")
