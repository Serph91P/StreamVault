from fastapi import Request
import logging

logger = logging.getLogger("streamvault")

async def logging_middleware(request: Request, call_next):
    logger.debug(f"Incoming request: {request.method} {request.url.path}")
    response = await call_next(request)
    logger.debug(f"Response status: {response.status_code}")
    return response
