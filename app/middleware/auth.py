from fastapi import Request
from fastapi.responses import RedirectResponse
from app.services.auth_service import AuthService
from app.dependencies import get_auth_service
from app.database import SessionLocal

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

            request = Request(scope, receive=receive)
            
            # Public paths that don't require authentication
            public_paths = [
                "/auth/login",
                "/auth/setup",
                "/eventsub/callback",
                "/static/",
                "/assets/"
            ]

            if any(request.url.path.startswith(path) for path in public_paths):
                return await self.app(scope, receive, send)

            # Check if admin exists
            admin_exists = await self.auth_service.admin_exists()
            if not admin_exists:
                response = RedirectResponse(url="/auth/setup", status_code=307)
                return await response(scope, receive, send)

            # Verify session token
            session_token = request.cookies.get("session")
            if not session_token or not await self.auth_service.validate_session(session_token):
                response = RedirectResponse(url="/auth/login", status_code=307)
                return await response(scope, receive, send)

            return await self.app(scope, receive, send)
        finally:
            if self._db:
                self._db.close()
                self._db = None