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

    async def __call__(self, request: Request, call_next):
        # Public paths that don't require authentication
        public_paths = [
            "/auth/login",
            "/auth/setup",
            "/eventsub/callback",
            "/static/",
            "/assets/"
        ]

        if any(request.url.path.startswith(path) for path in public_paths):
            return await call_next(request)

        # Check if admin exists
        admin_exists = await self.auth_service.admin_exists()
        if not admin_exists:
            return RedirectResponse(url="/auth/setup", status_code=307)

        # Verify session token
        session_token = request.cookies.get("session")
        if not session_token or not await self.auth_service.validate_session(session_token):
            return RedirectResponse(url="/auth/login", status_code=307)

        return await call_next(request)
        return await call_next(request)