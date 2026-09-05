"""Regression contract for Phase 6 trust boundaries and observability."""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient


def test_request_id_is_generated_or_strictly_validated_at_the_edge() -> None:
    from app.middleware_all import add_request_id

    app = FastAPI()

    @app.get("/request-id")
    async def request_id(request: Request):
        return {"request_id": request.state.request_id}

    app.middleware("http")(add_request_id)

    with TestClient(app) as client:
        generated = client.get("/request-id")
        accepted = client.get(
            "/request-id",
            headers={"X-Request-ID": "123e4567-e89b-12d3-a456-426614174000"},
        )
        rejected = client.get(
            "/request-id", headers={"X-Request-ID": "client-controlled-cardinality"}
        )

    assert UUID(generated.headers["X-Request-ID"])
    assert generated.json()["request_id"] == generated.headers["X-Request-ID"]
    assert accepted.headers["X-Request-ID"] == "123e4567-e89b-12d3-a456-426614174000"
    assert rejected.headers["X-Request-ID"] != "client-controlled-cardinality"


def test_redaction_covers_header_query_and_structured_sensitive_values() -> None:
    from app.config.logging_config import RedactingFormatter

    record = logging.LogRecord(
        name="streamvault",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg=(
            "authorization=Bearer fixture-value-a cookie=session-value "
            "https_proxy=http://proxy-user:fixture-value-b@example.test "
            "TWITCH_APP_SECRET=fixture-value-c body={'password': 'fixture-value-d'}"
        ),
        args=(),
        exc_info=None,
    )

    payload = RedactingFormatter("%(message)s").format(record)

    for secret in (
        "fixture-value-a",
        "session-value",
        "fixture-value-b",
        "fixture-value-c",
        "fixture-value-d",
    ):
        assert secret not in payload


def test_redaction_covers_child_process_arguments_and_environment_values() -> None:
    from app.config.logging_config import RedactingFormatter

    child_token = "fixture-value-e"
    record = logging.LogRecord(
        name="streamvault",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg=(
            "streamlink --twitch-api-header=Authorization=OAuth "
            f"{child_token} --http-proxy=https://proxy-user:fixture-value-b@example.test "
            "env={'TWITCH_OAUTH_TOKEN': 'fixture-value-f'}"
        ),
        args=(),
        exc_info=None,
    )

    payload = RedactingFormatter("%(message)s").format(record)

    for secret in (child_token, "fixture-value-b", "fixture-value-f"):
        assert secret not in payload


def test_production_origin_and_host_policy_is_explicit_and_fail_closed() -> None:
    from app.config.settings import Settings

    settings = Settings(
        TWITCH_APP_ID="test-id",
        TWITCH_APP_SECRET="fixture-value",
        BASE_URL="https://streamvault.example.test",
        ENVIRONMENT="production",
    )

    assert settings.allowed_origins == ["https://streamvault.example.test"]
    assert settings.trusted_hosts == ["streamvault.example.test"]
    assert not settings.is_trusted_proxy("198.51.100.10")


def test_comma_separated_deployment_lists_are_accepted_from_the_environment(
    monkeypatch,
) -> None:
    from app.config.settings import Settings

    monkeypatch.setenv(
        "TRUSTED_HOSTS", "streamvault.example.test, metrics.example.test"
    )
    monkeypatch.setenv("TRUSTED_PROXY_CIDRS", "10.0.0.0/8, 192.168.0.0/16")
    monkeypatch.setenv("READINESS_REQUIRED_COMPONENTS", "database,ffmpeg")

    settings = Settings(
        TWITCH_APP_ID="test-id",
        TWITCH_APP_SECRET="fixture-value",
        BASE_URL="https://streamvault.example.test",
    )

    assert settings.TRUSTED_HOSTS == [
        "streamvault.example.test",
        "metrics.example.test",
    ]
    assert settings.TRUSTED_PROXY_CIDRS == ["10.0.0.0/8", "192.168.0.0/16"]
    assert settings.READINESS_REQUIRED_COMPONENTS == ["database", "ffmpeg"]


def test_forwarded_client_identity_requires_a_configured_proxy(monkeypatch) -> None:
    from app.config.settings import settings
    from app.middleware_all import client_ip_for_request

    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/auth/login",
            "headers": [(b"x-forwarded-for", b"203.0.113.10")],
            "client": ("10.0.0.2", 1234),
            "scheme": "http",
            "server": ("testserver", 80),
        }
    )

    monkeypatch.setattr(settings, "TRUSTED_PROXY_CIDRS", [])
    assert client_ip_for_request(request) == "10.0.0.2"

    monkeypatch.setattr(settings, "TRUSTED_PROXY_CIDRS", ["10.0.0.0/8"])
    assert client_ip_for_request(request) == "203.0.113.10"


def test_rate_limiter_returns_retry_after_and_bounds_client_bucket_growth(
    monkeypatch,
) -> None:
    from app.config.settings import settings
    from app.middleware_all import AdaptiveLimiter

    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_CAPACITY", 1)
    monkeypatch.setattr(settings, "RATE_LIMIT_REFILL_PER_SEC", 0.01)
    monkeypatch.setattr(settings, "RATE_LIMIT_MAX_WAIT_MS", 0)
    monkeypatch.setattr(settings, "RATE_LIMIT_MAX_BUCKETS", 2)
    limiter = AdaptiveLimiter()
    monkeypatch.setattr(limiter, "_route_params", lambda path, method: (1, 0.01))

    async def exercise():
        first = await limiter.acquire(
            path="/api/auth/login",
            method="POST",
            client_ip="198.51.100.1",
            auth_header=None,
        )
        second = await limiter.acquire(
            path="/api/auth/login",
            method="POST",
            client_ip="198.51.100.1",
            auth_header=None,
        )
        for suffix in ("2", "3", "4"):
            await limiter.acquire(
                path="/api/auth/login",
                method="POST",
                client_ip=f"198.51.100.{suffix}",
                auth_header=None,
            )
        return first, second

    first, second = asyncio.run(exercise())

    assert first[0]
    assert not second[0]
    assert second[1] >= 1
    assert len(limiter._buckets) == 2


def test_rate_limited_response_has_a_truthful_retry_after_header(monkeypatch) -> None:
    from app.config.settings import settings
    from app.middleware import logging as logging_middleware_module
    from app.middleware_all import AdaptiveLimiter, rate_limit_middleware

    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_CAPACITY", 1)
    monkeypatch.setattr(settings, "RATE_LIMIT_REFILL_PER_SEC", 0.01)
    monkeypatch.setattr(settings, "RATE_LIMIT_MAX_WAIT_MS", 0)
    monkeypatch.setattr(
        logging_middleware_module.logger, "log", lambda *args, **kwargs: None
    )

    app = FastAPI()

    @app.get("/api/auth-sensitive")
    async def auth_sensitive():
        return {"ok": True}

    app.state.rate_limiter = AdaptiveLimiter()
    monkeypatch.setattr(
        app.state.rate_limiter, "_route_params", lambda path, method: (1, 0.01)
    )
    app.middleware("http")(rate_limit_middleware)

    with TestClient(app) as client:
        first = client.get("/api/auth-sensitive")
        limited = client.get("/api/auth-sensitive")

    assert first.status_code == 200
    assert limited.status_code == 429
    assert int(limited.headers["retry-after"]) >= 1
    assert limited.headers["x-ratelimit-limit"] == "1"


def test_cors_uses_the_explicit_origin_policy(monkeypatch) -> None:
    from app.config.settings import settings
    from app.middleware_all import install_http_middleware

    monkeypatch.setattr(settings, "BASE_URL", "https://streamvault.example.test")
    monkeypatch.setattr(settings, "TRUSTED_HOSTS", ["testserver"])
    app = FastAPI()

    @app.get("/api/cors")
    async def cors_endpoint():
        return {"ok": True}

    install_http_middleware(app)

    with TestClient(app) as client:
        allowed = client.get(
            "/api/cors", headers={"Origin": "https://streamvault.example.test"}
        )
        rejected = client.get(
            "/api/cors", headers={"Origin": "https://not-allowed.example.test"}
        )

    assert (
        allowed.headers["access-control-allow-origin"]
        == "https://streamvault.example.test"
    )
    assert "access-control-allow-origin" not in rejected.headers


def test_metrics_are_low_cardinality_and_exclude_request_ids() -> None:
    from app.observability import ServiceMetrics

    metrics = ServiceMetrics()
    metrics.record_request(
        method="GET",
        route="/api/recording/42",
        status_code=200,
        duration_seconds=0.25,
    )
    metrics.record_request(
        method="GET",
        route="/api/recording/99",
        status_code=404,
        duration_seconds=0.5,
    )
    metrics.recording_started()
    metrics.recording_stopped(duration_seconds=3.0)
    metrics.record_lease_contention()
    metrics.record_lease_recovery(2)
    rendered = metrics.render_prometheus()

    assert (
        'streamvault_http_requests_total{method="GET",route="api_recording",status="2xx"} 1'
        in rendered
    )
    assert (
        'streamvault_http_requests_total{method="GET",route="api_recording",status="4xx"} 1'
        in rendered
    )
    assert "request_id" not in rendered
    assert "42" not in rendered
    assert "99" not in rendered
    assert "streamvault_recording_starts_total 1" in rendered
    assert "streamvault_lease_recovery_total 2" in rendered


def test_readiness_timeout_returns_sanitized_component_status(monkeypatch) -> None:
    from app.routes import health

    async def slow_database_check() -> bool:
        await asyncio.sleep(0.05)
        return True

    monkeypatch.setattr(health, "_check_database", slow_database_check)
    monkeypatch.setattr(health.settings, "READINESS_TIMEOUT_SECONDS", 0.001)
    monkeypatch.setattr(health.settings, "READINESS_REQUIRED_COMPONENTS", ["database"])

    app = FastAPI()
    app.include_router(health.router)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {"database": "unavailable"},
    }


def test_cancelled_readiness_command_terminates_its_child(monkeypatch) -> None:
    from app.routes import health

    class WaitingProcess:
        returncode = None

        def __init__(self) -> None:
            self.killed = False

        async def wait(self) -> int:
            if self.killed:
                return -9
            await asyncio.Event().wait()
            return 0

        def kill(self) -> None:
            self.killed = True
            self.returncode = -9

    process = WaitingProcess()

    async def create_process(*args, **kwargs):
        return process

    async def exercise() -> None:
        task = asyncio.create_task(health._check_command("ffmpeg"))
        await asyncio.sleep(0)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    monkeypatch.setattr(asyncio, "create_subprocess_exec", create_process)
    asyncio.run(exercise())

    assert process.killed


def test_ffmpeg_readiness_uses_its_supported_version_flag(monkeypatch) -> None:
    from app.routes import health

    invoked: list[tuple[str, ...]] = []

    class CompletedProcess:
        async def wait(self) -> int:
            return 0

    async def create_process(*args, **kwargs):
        invoked.append(args)
        return CompletedProcess()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", create_process)

    assert asyncio.run(health._check_ffmpeg()) is True
    assert invoked == [("ffmpeg", "-version")]


def test_liveness_stays_available_when_a_required_dependency_is_down(
    monkeypatch,
) -> None:
    from app.routes import health

    async def unavailable_database() -> bool:
        return False

    monkeypatch.setattr(health, "_check_database", unavailable_database)
    app = FastAPI()
    app.include_router(health.router)
    with TestClient(app) as client:
        live = client.get("/api/health/live")
        compatibility = client.get("/api/health")

    assert live.status_code == 200
    assert live.json() == {"status": "alive"}
    assert compatibility.status_code == 200
    assert compatibility.json()["status"] == "degraded"


def test_compatibility_health_timeout_degrades_without_exposing_an_exception(
    monkeypatch,
) -> None:
    from app.routes import health

    async def slow_database_check() -> bool:
        await asyncio.sleep(0.05)
        return True

    monkeypatch.setattr(health, "_check_database", slow_database_check)
    monkeypatch.setattr(health.settings, "READINESS_TIMEOUT_SECONDS", 0.001)
    app = FastAPI()
    app.include_router(health.router)

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "degraded",
        "checks": {"application": "healthy", "database": "unavailable"},
    }


def test_metrics_endpoint_is_opt_in_and_requires_its_deployment_token(
    monkeypatch,
) -> None:
    from app.routes import health

    monkeypatch.setattr(health.settings, "METRICS_ENABLED", True)
    monkeypatch.setattr(health.settings, "METRICS_AUTH_TOKEN", "metrics-fixture-value")
    monkeypatch.setattr(health.settings, "METRICS_ALLOW_UNAUTHENTICATED", False)
    app = FastAPI()
    app.include_router(health.router)
    with TestClient(app) as client:
        rejected = client.get("/api/metrics")
        accepted = client.get(
            "/api/metrics", headers={"Authorization": "Bearer metrics-fixture-value"}
        )

    assert rejected.status_code == 404
    assert accepted.status_code == 200
    assert "streamvault_http_requests_total" in accepted.text
    assert accepted.headers["content-type"].startswith("text/plain; version=0.0.4")


def test_metrics_token_policy_is_reachable_through_auth_middleware(monkeypatch) -> None:
    from app.middleware.auth import AuthMiddleware
    import app.middleware.auth as auth_middleware
    from app.routes import health

    def database_must_not_be_opened():
        raise AssertionError("metrics policy must run before session authentication")

    monkeypatch.setattr(auth_middleware, "SessionLocal", database_must_not_be_opened)
    monkeypatch.setattr(health.settings, "METRICS_ENABLED", True)
    monkeypatch.setattr(health.settings, "METRICS_AUTH_TOKEN", "metrics-fixture-value")
    monkeypatch.setattr(health.settings, "METRICS_ALLOW_UNAUTHENTICATED", False)
    app = FastAPI()
    app.include_router(health.router)
    app.add_middleware(AuthMiddleware)

    with TestClient(app) as client:
        rejected = client.get("/api/metrics", follow_redirects=False)
        accepted = client.get(
            "/api/metrics",
            headers={"Authorization": "Bearer metrics-fixture-value"},
            follow_redirects=False,
        )

    assert rejected.status_code == 404
    assert accepted.status_code == 200


def test_request_logging_failure_never_breaks_the_response(monkeypatch) -> None:
    from app.middleware.logging import logging_middleware
    import app.middleware.logging as logging_module

    app = FastAPI()

    @app.get("/ok")
    async def ok():
        return {"ok": True}

    monkeypatch.setattr(
        logging_module.logger,
        "log",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("logger unavailable")
        ),
    )
    app.middleware("http")(logging_middleware)

    with TestClient(app) as client:
        response = client.get("/ok?token=do-not-log")

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_global_error_envelope_survives_a_logging_backend_failure(monkeypatch) -> None:
    from app.core import exceptions

    app = FastAPI()

    @app.get("/boom")
    async def boom():
        raise RuntimeError("do-not-expose")

    exceptions.install_exception_handlers(app)
    monkeypatch.setattr(
        exceptions.logger,
        "exception",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("logger unavailable")
        ),
    )

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/boom")

    assert response.status_code == 500
    assert response.json() == {
        "error": {"code": "internal_error", "message": "Internal server error"}
    }
