"""Tests for core HTTP middleware and error responses."""

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exception_handlers import (
    http_exception_handler,
    validation_exception_handler,
)
from app.middleware import setup_cors, setup_request_context


class Payload(BaseModel):
    name: str


def _test_app() -> FastAPI:
    app = FastAPI()
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    setup_cors(app)
    setup_request_context(app)

    @app.get("/ok")
    async def ok() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/forbidden")
    async def forbidden() -> None:
        raise StarletteHTTPException(status_code=403, detail="Nope")

    @app.post("/payload")
    async def payload(data: Payload) -> dict[str, str]:
        return {"name": data.name}

    return app


def test_request_context_generates_and_preserves_request_id() -> None:
    with TestClient(_test_app()) as client:
        generated = client.get("/ok")
        preserved = client.get("/ok", headers={"X-Request-ID": "req-known"})

    assert generated.headers["X-Request-ID"]
    assert preserved.headers["X-Request-ID"] == "req-known"


def test_cors_allows_configured_origin_and_exposes_request_id() -> None:
    with TestClient(_test_app()) as client:
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


def test_http_errors_use_nested_error_contract_with_request_id() -> None:
    with TestClient(_test_app()) as client:
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


def test_validation_errors_use_nested_error_contract() -> None:
    with TestClient(_test_app()) as client:
        response = client.post("/payload", json={}, headers={"X-Request-ID": "req-val"})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["details"]["request_id"] == "req-val"
    assert error["details"]["validation_errors"][0]["loc"] == ["body", "name"]
