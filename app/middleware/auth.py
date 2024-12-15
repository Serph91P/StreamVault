from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.services.auth_service import AuthService
from typing import Optional
import logging

logger = logging.getLogger("streamvault")

class AuthMiddleware:
    def __init__(self, auth_service: AuthService):
        self.auth_service = auth_service
        self.security = HTTPBearer()

    async def __call__(self, request: Request, call_next):
        # Skip auth for API and EventSub routes
        if request.url.path.startswith(("/api/", "/eventsub/", "/static/", "/setup")):
            return await call_next(request)

        # Check if admin exists
        if not await self.auth_service.admin_exists():
            return RedirectResponse(url="/setup")

        # Check session token
        session_token = request.cookies.get("session")
        if not session_token or not await self.auth_service.validate_session(session_token):
            return RedirectResponse(url="/login")

        return await call_next(request)