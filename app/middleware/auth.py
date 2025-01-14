from fastapi import Request
from fastapi.responses import RedirectResponse
from app.services.auth_service import AuthService
from app.dependencies import get_auth_service

class AuthMiddleware:
    def __init__(self, app):
        self.app = app
        self._auth_service = None

    @property
    def auth_service(self):
        if self._auth_service is None:
            self._auth_service = get_auth_service()
        return self._auth_service
 
    async def __call__(self, scope, receive, send):
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
        return await call_next(request)