import inspect
import logging
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError


def test_settings_require_production_secrets_and_support_explicit_injection(
    monkeypatch,
):
    from app.config.settings import Settings

    for name in ("TWITCH_APP_ID", "TWITCH_APP_SECRET", "BASE_URL"):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)

    settings = Settings(
        TWITCH_APP_ID="test-id",
        TWITCH_APP_SECRET="test-secret",
        BASE_URL="http://localhost:8000",
        ENVIRONMENT="development",
    )

    assert settings.environment_is_development
    assert {
        "http://localhost:8000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    }.issubset(settings.allowed_origins)


def test_logging_redacts_secrets_and_keeps_request_correlation():
    from app.config.logging_config import (
        JSONFormatter,
        RedactingFormatter,
        request_context,
    )

    formatter = JSONFormatter()
    request_context.set("request-123")
    fixture_credentials = f"{'alice'}:{'super-secret'}"
    record = logging.LogRecord(
        name="streamvault",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=f"proxy=https://{fixture_credentials}@example.test?token=abc123",
        args=(),
        exc_info=None,
    )

    payload = formatter.format(record)

    assert "super-secret" not in payload
    assert "abc123" not in payload
    assert '"request_id": "request-123"' in payload

    text_payload = RedactingFormatter("%(message)s").format(record)
    assert "super-secret" not in text_payload

    try:
        raise RuntimeError("token=error-secret")
    except RuntimeError:
        exception_record = logging.LogRecord(
            name="streamvault",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="request failed",
            args=(),
            exc_info=sys.exc_info(),
        )

    assert "error-secret" not in formatter.format(exception_record)


def test_domain_and_unhandled_errors_use_safe_stable_envelopes():
    from app.core.exceptions import DomainError, install_exception_handlers

    app = FastAPI()
    install_exception_handlers(app)

    @app.get("/domain")
    async def domain_error():
        raise DomainError(
            code="stream_unavailable", message="Stream unavailable", status_code=409
        )

    @app.get("/unexpected")
    async def unexpected_error():
        raise RuntimeError("database password is super-secret")

    with TestClient(app, raise_server_exceptions=False) as client:
        domain_response = client.get("/domain")
        unexpected_response = client.get("/unexpected")

    assert domain_response.status_code == 409
    assert domain_response.json() == {
        "error": {"code": "stream_unavailable", "message": "Stream unavailable"}
    }
    assert unexpected_response.status_code == 500
    assert unexpected_response.json() == {
        "error": {"code": "internal_error", "message": "Internal server error"}
    }
    assert "super-secret" not in unexpected_response.text


def test_create_app_preserves_the_compatibility_asgi_export():
    from app.main import app, create_app, lifespan

    assert create_app() is app
    assert app.openapi_url == "/api/openapi.json"
    assert "/api/health/live" in app.openapi()["paths"]
    assert "/" in app.openapi()["paths"]

    lifespan_source = inspect.getsource(lifespan)
    assert lifespan_source.index("run_safe_migrations") < lifespan_source.index(
        "initialize_background_services"
    )
    assert (
        lifespan_source.index("yield")
        < lifespan_source.index("recording_manager.shutdown")
        < lifespan_source.index("database_lifecycle.adispose")
    )
