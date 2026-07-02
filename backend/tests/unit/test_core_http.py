"""Tests for core HTTP middleware and error responses."""

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException
from structlog.testing import capture_logs

from app.core.config import Settings
from app.core.exception_handlers import (
    generic_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from app.middleware import setup_cors, setup_request_context


class Payload(BaseModel):
    name: str


def _test_app(settings: Settings) -> FastAPI:
    app = FastAPI()
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
    setup_cors(app, settings)
    setup_request_context(app)

    @app.get("/ok")
    async def ok() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/forbidden")
    async def forbidden() -> None:
        raise StarletteHTTPException(status_code=403, detail="Nope")

    @app.get("/server-error")
    async def server_error() -> None:
        raise StarletteHTTPException(status_code=500, detail="Server exploded")

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("boom")

    @app.post("/payload")
    async def payload(data: Payload) -> dict[str, str]:
        return {"name": data.name}

    return app


def test_request_context_generates_and_preserves_request_id(test_settings) -> None:
    with TestClient(_test_app(test_settings)) as client:
        generated = client.get("/ok")
        preserved = client.get("/ok", headers={"X-Request-ID": "req-known"})

    assert generated.headers["X-Request-ID"]
    assert preserved.headers["X-Request-ID"] == "req-known"


def test_cors_allows_configured_origin_and_exposes_request_id(test_settings) -> None:
    with TestClient(_test_app(test_settings)) as client:
        preflight = client.options(
            "/ok",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Authorization, X-Request-ID",
            },
        )
        response = client.get("/ok", headers={"Origin": "http://localhost:3000"})

    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert preflight.headers["access-control-allow-credentials"] == "true"
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "X-Request-ID" in response.headers["access-control-expose-headers"]


def test_http_errors_use_nested_error_contract_with_request_id(test_settings) -> None:
    with TestClient(_test_app(test_settings)) as client:
        response = client.get("/forbidden", headers={"X-Request-ID": "req-error"})

    assert response.status_code == 403
    body = response.json()
    assert body == {
        "error": {
            "code": "FORBIDDEN",
            "message": "Nope",
            "retryable": False,
            "details": {"request_id": "req-error"},
        }
    }


def test_http_4xx_errors_are_not_captured_by_sentry(test_settings, monkeypatch) -> None:
    captured: list[BaseException] = []
    monkeypatch.setattr(
        "app.core.exception_handlers.capture_exception",
        lambda exc: captured.append(exc),
    )

    with TestClient(_test_app(test_settings)) as client:
        response = client.get("/forbidden")

    assert response.status_code == 403
    assert captured == []


def test_http_5xx_errors_are_captured_by_sentry(test_settings, monkeypatch) -> None:
    captured: list[BaseException] = []
    monkeypatch.setattr(
        "app.core.exception_handlers.capture_exception",
        lambda exc: captured.append(exc),
    )

    with TestClient(_test_app(test_settings)) as client:
        response = client.get("/server-error")

    assert response.status_code == 500
    assert len(captured) == 1


def test_unexpected_500_errors_are_captured_by_sentry(test_settings, monkeypatch) -> None:
    captured: list[BaseException] = []
    monkeypatch.setattr(
        "app.core.exception_handlers.capture_exception",
        lambda exc: captured.append(exc),
    )

    with TestClient(_test_app(test_settings), raise_server_exceptions=False) as client:
        response = client.get("/boom", headers={"X-Request-ID": "req-boom"})

    assert response.status_code == 500
    assert response.json()["error"]["details"]["request_id"] == "req-boom"
    assert len(captured) == 1


def test_validation_errors_use_nested_error_contract(test_settings) -> None:
    with TestClient(_test_app(test_settings)) as client:
        response = client.post("/payload", json={}, headers={"X-Request-ID": "req-val"})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["details"]["request_id"] == "req-val"
    assert error["details"]["validation_errors"][0]["loc"] == ["body", "name"]


def test_validation_error_logs_omit_raw_input_values(test_settings, capsys) -> None:
    secret_like_value = "token-secret-value@example.com"

    with TestClient(_test_app(test_settings)) as client, capture_logs() as captured_logs:
        response = client.post(
            "/payload",
            json={"name": {"secret": secret_like_value}},
            headers={"X-Request-ID": "req-val-redacted"},
        )

    assert response.status_code == 422
    captured_output = capsys.readouterr()
    rendered_logs = repr(captured_logs) + captured_output.out + captured_output.err
    assert secret_like_value not in rendered_logs
    assert "input" not in rendered_logs
    assert "body" in rendered_logs
    assert "name" in rendered_logs
