from fastapi import Request
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger("streamvault")


async def error_handler(request: Request, exc: Exception):
    # SECURITY: Log full error server-side but never expose exception details to client (CWE-209)
    logger.error(f"Error processing request: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"message": "Internal server error"})
