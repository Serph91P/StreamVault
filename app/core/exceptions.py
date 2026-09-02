"""Typed domain errors and FastAPI error-envelope handlers."""

import logging
from collections.abc import Mapping
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("streamvault")


class DomainError(Exception):
    """An expected domain failure safe to expose to an API client."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        status_code: int = 400,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = dict(details) if details else None


def _error_payload(
    *, code: str, message: str, details: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if details:
        error["details"] = dict(details)
    return {"error": error}


async def domain_error_handler(_: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_payload(
            code=exc.code,
            message=exc.message,
            details=exc.details,
        ),
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    try:
        logger.exception("Unhandled request error", extra={"request_id": request_id})
    except Exception:  # nosec B110
        # Error reporting must not suppress the stable API error envelope.
        pass
    return JSONResponse(
        status_code=500,
        content=_error_payload(
            code="internal_error",
            message="Internal server error",
        ),
    )


def install_exception_handlers(app: FastAPI) -> None:
    """Install safe handlers without replacing FastAPI HTTP error contracts."""

    app.add_exception_handler(DomainError, domain_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
