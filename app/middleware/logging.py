import time

from fastapi import Request
import logging

logger = logging.getLogger("streamvault")


async def logging_middleware(request: Request, call_next):
    """Emit bounded request metadata without logging query strings or bodies."""
    started_at = time.monotonic()
    request_id = getattr(request.state, "request_id", None)
    try:
        response = await call_next(request)
    except Exception:
        _safe_log(
            logging.ERROR,
            "request_failed method=%s path=%s request_id=%s duration_ms=%d",
            request.method,
            request.url.path,
            request_id,
            int((time.monotonic() - started_at) * 1000),
        )
        raise
    _safe_log(
        logging.INFO,
        "request_completed method=%s path=%s status=%s request_id=%s duration_ms=%d",
        request.method,
        request.url.path,
        response.status_code,
        request_id,
        int((time.monotonic() - started_at) * 1000),
    )
    return response


def _safe_log(level: int, message: str, *args) -> None:
    """Logging must not turn a successfully handled request into a 500."""
    try:
        logger.log(level, message, *args)
    except Exception:
        return
