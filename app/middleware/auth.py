from fastapi import Request
from fastapi.responses import RedirectResponse, JSONResponse
from app.services.core.auth_service import AuthService
from app.database import SessionLocal
import logging

logger = logging.getLogger("streamvault")


def _extract_bearer_token(headers: list) -> str | None:
    """Extract Bearer token from Authorization header (PWA fallback).

    SECURITY: In PWA standalone mode, cookies may not persist across app restarts.
    The frontend stores the session token in localStorage and sends it as a Bearer token.
    This provides a fallback authentication method for PWA users.
    """
    for header_name, header_value in headers:
        if header_name == b"authorization":
            value = header_value.decode("utf-8", errors="ignore")
            if value.startswith("Bearer "):
                return value[7:]  # Strip "Bearer " prefix
    return None


class AuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            return await self.app(scope, receive, send)

        # SECURITY: Validate WebSocket connections with session cookie
        if scope["type"] == "websocket":
            from starlette.websockets import WebSocket as StarletteWebSocket

            ws = StarletteWebSocket(scope, receive, send)
            session_token = ws.cookies.get("session")

            # PWA fallback: check Authorization header if no cookie
            if not session_token:
                session_token = _extract_bearer_token(scope.get("headers", []))

            if not session_token:
                logger.warning(
                    "WebSocket connection rejected: no session cookie or Bearer token"
                )
                await ws.close(code=4001, reason="Authentication required")
                return
            db = SessionLocal()
            try:
                auth_service = AuthService(db=db)
                if not await auth_service.validate_session(session_token):
                    logger.warning("WebSocket connection rejected: invalid session")
                    await ws.close(code=4001, reason="Invalid session")
                    return
            except Exception as e:
                logger.error(f"WebSocket auth error: {e}")
                await ws.close(code=4003, reason="Authentication service unavailable")
                return
            finally:
                db.close()
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
                            {"error": "Setup required", "redirect": "/auth/setup"},
                            status_code=307,
                        )(scope, receive, send)
                    return await RedirectResponse(url="/auth/setup", status_code=307)(
                        scope, receive, send
                    )

            session_token = request.cookies.get("session")

            # PWA fallback: check Authorization header if no cookie
            if not session_token:
                auth_header = request.headers.get("authorization", "")
                if auth_header.startswith("Bearer "):
                    session_token = auth_header[7:]

            if not session_token:
                logger.debug(
                    f"No session cookie or Bearer token for {request.url.path}"
                )
                if not request.url.path.startswith("/auth/login"):
                    if is_json_request:
                        return await JSONResponse(
                            {
                                "error": "Authentication required",
                                "redirect": "/auth/login",
                            },
                            status_code=401,
                        )(scope, receive, send)
                    return await RedirectResponse(url="/auth/login", status_code=307)(
                        scope, receive, send
                    )
            elif not await auth_service.validate_session(session_token):
                logger.debug(f"Invalid session token for {request.url.path}")
                if not request.url.path.startswith("/auth/login"):
                    if is_json_request:
                        return await JSONResponse(
                            {
                                "error": "Authentication required",
                                "redirect": "/auth/login",
                            },
                            status_code=401,
                        )(scope, receive, send)
                    return await RedirectResponse(url="/auth/login", status_code=307)(
                        scope, receive, send
                    )

            return await self.app(scope, receive, send)
        except Exception as e:
            logger.error(f"Auth middleware error for {request.url.path}: {e}")
            # SECURITY: Fail closed — deny access when auth cannot be verified (CWE-280)
            if is_json_request:
                return await JSONResponse(
                    {"error": "Authentication service unavailable"}, status_code=503
                )(scope, receive, send)
            return await JSONResponse(
                {"error": "Authentication service unavailable"}, status_code=503
            )(scope, receive, send)
        finally:
            db.close()
