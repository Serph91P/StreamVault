"""Bounded liveness, readiness and protected metrics endpoints."""

from __future__ import annotations

import asyncio
import secrets
from functools import partial
from typing import Awaitable, Callable

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from sqlalchemy import text
from sqlalchemy.orm import Session


from app.database import SessionLocal
from app.bootstrap.settings import resolve_app_settings
from app.dependencies import get_application_session_factory
from app.observability import service_metrics
from app.utils.async_db_utils import run_in_thread_pool

router = APIRouter(prefix="/api", tags=["health"])

_ReadinessCheck = Callable[[], Awaitable[bool]]


async def _check_database(session_factory: Callable[[], Session] | None = None) -> bool:
    def probe() -> bool:
        factory = session_factory if session_factory is not None else SessionLocal
        with factory() as db:
            db.execute(text("SELECT 1"))
        return True

    try:
        return await run_in_thread_pool(probe)
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
            while True:
                try:
                    await process.wait()
                    break
                except asyncio.CancelledError:
                    continue
        raise
    except OSError:
        return False


async def _check_ffmpeg() -> bool:
    return await _check_command("ffmpeg", "-version")


async def _check_streamlink() -> bool:
    return await _check_command("streamlink")


def _readiness_checks(
    session_factory: Callable[[], Session] | None = None,
) -> dict[str, _ReadinessCheck]:
    return {
        "database": partial(_check_database, session_factory)
        if session_factory is not None
        else _check_database,
        "ffmpeg": _check_ffmpeg,
        "streamlink": _check_streamlink,
    }


@router.get("/health")
async def health_check(
    request: Request,
    session_factory: Callable[[], Session] = Depends(get_application_session_factory),
) -> dict[str, object]:
    """Compatibility endpoint reporting bounded database availability."""
    runtime_settings = resolve_app_settings(request.app)
    try:
        database_ok = await asyncio.wait_for(
            _check_database(session_factory),
            timeout=runtime_settings.READINESS_TIMEOUT_SECONDS,
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
async def readiness_check(
    request: Request,
    session_factory: Callable[[], Session] = Depends(get_application_session_factory),
) -> Response:
    """Return readiness for explicitly required dependencies only."""
    runtime_settings = resolve_app_settings(request.app)
    available_checks = _readiness_checks(session_factory)
    required = tuple(runtime_settings.READINESS_REQUIRED_COMPONENTS)

    async def check_component(component: str) -> tuple[str, str]:
        check = available_checks.get(component)
        if check is None:
            return component, "unavailable"
        try:
            ready = await asyncio.wait_for(
                check(), timeout=runtime_settings.READINESS_TIMEOUT_SECONDS
            )
        except (asyncio.TimeoutError, Exception):
            ready = False
        return component, "ready" if ready else "unavailable"

    async with asyncio.TaskGroup() as group:
        tasks = [
            group.create_task(
                check_component(component), name=f"streamvault:readiness:{component}"
            )
            for component in required
        ]
    checks = dict(task.result() for task in tasks)
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
    runtime_settings = resolve_app_settings(request.app)
    if not runtime_settings.METRICS_ENABLED:
        return Response(status_code=404)
    token = runtime_settings.METRICS_AUTH_TOKEN
    supplied = request.headers.get("Authorization", "").removeprefix("Bearer ")
    allow_without_token = (
        runtime_settings.environment_is_development
        and runtime_settings.METRICS_ALLOW_UNAUTHENTICATED
    )
    if not allow_without_token and (
        not token or not secrets.compare_digest(supplied, token)
    ):
        return Response(status_code=404)
    return PlainTextResponse(
        service_metrics.render_prometheus(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
