"""Bounded liveness, readiness and protected metrics endpoints."""

from __future__ import annotations

import asyncio
import secrets
from typing import Awaitable, Callable

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from sqlalchemy import text

from app.config.settings import settings
from app.database import SessionLocal
from app.observability import service_metrics

router = APIRouter(prefix="/api", tags=["health"])

_ReadinessCheck = Callable[[], Awaitable[bool]]


async def _check_database() -> bool:
    def probe() -> bool:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        return True

    try:
        return await asyncio.to_thread(probe)
    except Exception:
        return False


async def _check_command(command: str, version_flag: str = "--version") -> bool:
    process: asyncio.subprocess.Process | None = None
    try:
        process = await asyncio.create_subprocess_exec(
            command,
            version_flag,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        return await process.wait() == 0
    except asyncio.CancelledError:
        if process is not None and process.returncode is None:
            process.kill()
            await process.wait()
        raise
    except OSError:
        return False


async def _check_ffmpeg() -> bool:
    return await _check_command("ffmpeg", "-version")


async def _check_streamlink() -> bool:
    return await _check_command("streamlink")


def _readiness_checks() -> dict[str, _ReadinessCheck]:
    return {
        "database": _check_database,
        "ffmpeg": _check_ffmpeg,
        "streamlink": _check_streamlink,
    }


@router.get("/health")
async def health_check() -> dict[str, object]:
    """Compatibility endpoint reporting bounded database availability."""
    try:
        database_ok = await asyncio.wait_for(
            _check_database(), timeout=settings.READINESS_TIMEOUT_SECONDS
        )
    except Exception:
        database_ok = False
    return {
        "status": "healthy" if database_ok else "degraded",
        "checks": {
            "application": "healthy",
            "database": "healthy" if database_ok else "unavailable",
        },
    }


@router.get("/health/ready")
async def readiness_check() -> Response:
    """Return readiness for explicitly required dependencies only."""
    available_checks = _readiness_checks()
    required = tuple(settings.READINESS_REQUIRED_COMPONENTS)

    async def check_component(component: str) -> tuple[str, str]:
        check = available_checks.get(component)
        if check is None:
            return component, "unavailable"
        try:
            ready = await asyncio.wait_for(
                check(), timeout=settings.READINESS_TIMEOUT_SECONDS
            )
        except (asyncio.TimeoutError, Exception):
            ready = False
        return component, "ready" if ready else "unavailable"

    results = await asyncio.gather(
        *(check_component(component) for component in required)
    )
    checks = dict(results)
    payload = {
        "status": "ready"
        if all(value == "ready" for value in checks.values())
        else "not_ready",
        "checks": checks,
    }
    return JSONResponse(
        status_code=200 if payload["status"] == "ready" else 503, content=payload
    )


@router.get("/health/live")
async def liveness_check() -> dict[str, str]:
    """Liveness intentionally checks only that this ASGI event loop responds."""
    return {"status": "alive"}


@router.get("/metrics", include_in_schema=False)
async def metrics(request: Request) -> Response:
    """Expose metrics only when deployment policy explicitly enables them."""
    if not settings.METRICS_ENABLED:
        return Response(status_code=404)
    token = settings.METRICS_AUTH_TOKEN
    supplied = request.headers.get("Authorization", "").removeprefix("Bearer ")
    allow_without_token = (
        settings.environment_is_development and settings.METRICS_ALLOW_UNAUTHENTICATED
    )
    if not allow_without_token and (
        not token or not secrets.compare_digest(supplied, token)
    ):
        return Response(status_code=404)
    return PlainTextResponse(
        service_metrics.render_prometheus(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
