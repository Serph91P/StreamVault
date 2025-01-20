from fastapi import Request, WebSocket
from fastapi.responses import RedirectResponse, JSONResponse
from app.services.auth_service import AuthService
from app.dependencies import get_auth_service
from app.database import SessionLocal
import logging

logger = logging.getLogger("streamvault")

class AuthMiddleware:
    def __init__(self, app):
        self.app = app
        self._auth_service = None
        self._db = None

    def get_db(self):
        if not self._db:
            self._db = SessionLocal()
        return self._db

    @property
    def auth_service(self):
        if self._auth_service is None:
            self._auth_service = AuthService(db=self.get_db())
        return self._auth_service

    async def __call__(self, scope, receive, send):
        try:
            if scope["type"] not in ("http", "websocket"):
                return await self.app(scope, receive, send)

            # Handle WebSocket connections directly
            if scope["type"] == "websocket":
                return await self.app(scope, receive, send)

            # Process HTTP requests
            request = Request(scope, receive=receive)
            is_json_request = request.headers.get("X-Requested-With") == "XMLHttpRequest" or "application/json" in request.headers.get("accept", "")

            # Public paths that don't require authentication
            public_paths = [
                "/auth/login",
                "/auth/setup",
                "/auth/check",
                "/eventsub/callback",
                "/eventsub",
                "/static/",
                "/assets/",
                "/api/streamers/test",
                "/api/admin/test-subscription"
            ]

            if any(request.url.path.startswith(path) for path in public_paths):
                return await self.app(scope, receive, send)

            admin_exists = await self.auth_service.admin_exists()

            if not admin_exists:
                if not request.url.path.startswith("/auth/setup"):
                    if is_json_request:
                        return await JSONResponse({"error": "Setup required", "redirect": "/auth/setup"}, status_code=307)(scope, receive, send)
                    return await RedirectResponse(url="/auth/setup", status_code=307)(scope, receive, send)

            session_token = request.cookies.get("session")
            if not session_token or not await self.auth_service.validate_session(session_token):
                if not request.url.path.startswith("/auth/login"):
                    if is_json_request:
                        return await JSONResponse({"error": "Authentication required", "redirect": "/auth/login"}, status_code=401)(scope, receive, send)
                    return await RedirectResponse(url="/auth/login", status_code=307)(scope, receive, send)

            return await self.app(scope, receive, send)
        finally:
            if self._db:
                self._db.close()
                self._db = None
