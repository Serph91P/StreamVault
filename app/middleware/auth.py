from fastapi import Request
from fastapi.responses import RedirectResponse, JSONResponse
from app.services.core.auth_service import AuthService
from app.database import SessionLocal
import logging

logger = logging.getLogger("streamvault")


class AuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            return await self.app(scope, receive, send)

        # Handle WebSocket connections directly
        if scope["type"] == "websocket":
            return await self.app(scope, receive, send)

        # Process HTTP requests
        request = Request(scope, receive=receive)
        is_json_request = request.headers.get(
            "X-Requested-With"
        ) == "XMLHttpRequest" or "application/json" in request.headers.get("accept", "")

        # Public paths that don't require authentication
        public_paths = [
            "/auth/login",
            "/auth/setup",
            "/auth/check",
            "/auth/logout",
            "/auth/keepalive",
            "/api/health",  # Health check endpoints for Docker/Kubernetes
            "/eventsub",
            "/api/twitch/callback",  # Twitch OAuth callback - must be public for Twitch redirect
            "/api/twitch/auth-url",  # Twitch OAuth URL generation - public for initial auth flow
            "/api/videos/public/",  # Public video streaming with share token (for VLC, etc.)
            "/static/",
            "/assets/",
            "/registerSW.js",
            "/sw.js",
            "/pwa",
            "/pwa-helper.js",
            "/workbox-",
            "/manifest.json",
            "/manifest.webmanifest",
            "/favicon",
            "/android-icon-",
            "/apple-icon",
            "/ms-icon-",
            "/recordings/.media/",
            "/api/media/",
            "/data/images/",
            "/data/",
        ]

        if any(request.url.path.startswith(path) for path in public_paths):
            return await self.app(scope, receive, send)

        # Create per-request services
        db = SessionLocal()
        try:
            auth_service = AuthService(db=db)

            admin_exists = await auth_service.admin_exists()

            if not admin_exists:
                if not request.url.path.startswith("/auth/setup"):
                    if is_json_request:
                        return await JSONResponse(
                            {"error": "Setup required", "redirect": "/auth/setup"}, status_code=307
                        )(scope, receive, send)
                    return await RedirectResponse(url="/auth/setup", status_code=307)(scope, receive, send)

            session_token = request.cookies.get("session")
            if not session_token:
                logger.debug(f"No session cookie found for {request.url.path}")
                if not request.url.path.startswith("/auth/login"):
                    if is_json_request:
                        return await JSONResponse(
                            {"error": "Authentication required", "redirect": "/auth/login"}, status_code=401
                        )(scope, receive, send)
                    return await RedirectResponse(url="/auth/login", status_code=307)(scope, receive, send)
            elif not await auth_service.validate_session(session_token):
                logger.debug(f"Invalid session token for {request.url.path}")
                if not request.url.path.startswith("/auth/login"):
                    if is_json_request:
                        return await JSONResponse(
                            {"error": "Authentication required", "redirect": "/auth/login"}, status_code=401
                        )(scope, receive, send)
                    return await RedirectResponse(url="/auth/login", status_code=307)(scope, receive, send)

            return await self.app(scope, receive, send)
        except Exception as e:
            logger.error(f"Auth middleware error for {request.url.path}: {e}")
            return await self.app(scope, receive, send)
        finally:
            db.close()
