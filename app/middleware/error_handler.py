from fastapi import Request
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger('streamvault')

async def error_handler(request: Request, exc: Exception):
    logger.error(f"Error processing request: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"message": "Internal server error", "detail": str(exc)}
    )
