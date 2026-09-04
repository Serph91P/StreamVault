from fastapi import Request
from fastapi.responses import RedirectResponse, JSONResponse
from app.services.core.auth_service import AuthService
from app.services.core.api_key_service import ApiKeyService
from app.database import SessionLocal
import logging

logger = logging.getLogger("streamvault")

_EXACT_PUBLIC_PATHS = frozenset({"/api/openapi.json"})
_PUBLIC_PATH_PREFIXES = (
    "/auth/login",
    "/auth/setup",
    "/auth/check",
    "/auth/refresh",
    "/auth/logout",
    "/auth/keepalive",
    "/api/health",
    "/api/metrics",
    "/eventsub",
    "/api/twitch/callback",
    "/api/twitch/auth-url",
    "/api/videos/public/",
    "/api/live/stream/",
    "/assets/",
    "/registerSW.js",
    "/sw.js",
    "/pwa",
    "/workbox-",
    "/manifest.json",
    "/manifest.webmanifest",
    "/favicon",
    "/android-icon-",
    "/apple-icon",
    "/ms-icon-",
)


def _is_public_path(path: str) -> bool:
    return path in _EXACT_PUBLIC_PATHS or path.startswith(_PUBLIC_PATH_PREFIXES)


def _is_admin_path(path: str) -> bool:
    return path == "/api/admin" or path.startswith("/api/admin/")


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


def _extract_api_key(request_or_headers) -> str | None:
    """Extract a long-lived API key from the request.

    Accepts either:
      - X-API-Key: ***
      - Authorization: ApiKey ***

    Cookies/Bearer session tokens are handled separately and take precedence.
    """
    # Accept both a Request object and the raw scope headers list
    if isinstance(request_or_headers, list):
        for header_name, header_value in request_or_headers:
            name = header_name.decode("ascii", errors="ignore").lower()
            value = header_value.decode("utf-8", errors="ignore")
            if name == "x-api-key" and value:
                return value.strip()
            if name == "authorization" and value.startswith("ApiKey "):
                return value[7:].strip()
        return None

    api_key = request_or_headers.headers.get("x-api-key")
    if api_key:
        return api_key.strip()
    auth = request_or_headers.headers.get("authorization", "")
    if auth.startswith("ApiKey "):
        return auth[7:].strip()
    return None


def _is_valid_access_token(auth_service: AuthService, token: str | None) -> bool:
    if not token:
        return False
    try:
        auth_service.resolve_access_token(token)
        return True
    except Exception:
        return False


class AuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            return await self.app(scope, receive, send)

        # SECURITY: Validate WebSocket connections with access JWT or legacy session.
        if scope["type"] == "websocket":
            from starlette.websockets import WebSocket as StarletteWebSocket

            ws = StarletteWebSocket(scope, receive, send)
            bearer_token = _extract_bearer_token(scope.get("headers", []))
            access_token = ws.cookies.get("access_token") or bearer_token
            # A Bearer credential may be either a current JWT or a legacy opaque
            # session token. Validate it as JWT first, then use the established
            # legacy-session fallback when no JWT can be resolved.
            session_token = ws.cookies.get("session") or bearer_token

            if not access_token and not session_token:
                logger.warning(
                    "WebSocket connection rejected: no session cookie or Bearer token"
                )
                # Accept first, then close with code so the browser receives the close code
                await ws.accept()
                await ws.close(code=4001, reason="Authentication required")
                return
            db = SessionLocal()
            try:
                auth_service = AuthService(db=db)
                if not _is_valid_access_token(auth_service, access_token) and not (
                    session_token and await auth_service.validate_session(session_token)
                ):
                    logger.warning(
                        "WebSocket connection rejected: invalid authentication"
                    )
                    await ws.accept()
                    await ws.close(code=4001, reason="Invalid session")
                    return
            except Exception as e:
                logger.error(f"WebSocket auth error: {e}")
                await ws.accept()
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
        # SECURITY: Only paths that MUST work without a session belong here.
        # All data/media paths require auth to prevent unauthenticated access
        # to images, sync/cleanup POST endpoints, and system info.
        if _is_public_path(request.url.path):
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

            bearer_token = _extract_bearer_token(scope.get("headers", []))
            access_token = request.cookies.get("access_token") or bearer_token
            # Keep the same JWT-first, legacy-session fallback as dependencies.
            session_token = request.cookies.get("session") or bearer_token

            # API-key fallback (X-API-Key or "Authorization: ApiKey ***").
            # Sessions/cookies always take precedence. The /api/api-keys
            # management endpoints intentionally REJECT API-key auth because those
            # routes re-validate that an interactive session exists, so a
            # stolen key cannot be used to mint or revoke more keys.
            if not access_token and not session_token:
                api_key = _extract_api_key(request)
                if api_key:
                    # SECURITY: Never allow API-key auth on the management
                    # endpoints. Minting/revoking keys must require an
                    # interactive session.
                    if request.url.path.startswith("/api/api-keys"):
                        logger.warning(
                            f"Blocked API-key auth attempt on management endpoint {request.url.path}"
                        )
                    else:
                        api_key_service = ApiKeyService(db=db)
                        resolved = api_key_service.resolve_active_owner(api_key)
                        if resolved:
                            from app.dependencies import AuthIdentity

                            owner = resolved.owner
                            identity = AuthIdentity(
                                subject=str(owner.id),
                                roles=frozenset({"admin"})
                                if owner.is_admin
                                else frozenset({"user"}),
                                scopes=auth_service._user_scopes(owner),
                                auth_method="api-key",
                                interactive=False,
                            )
                            scope.setdefault("state", {})["auth_identity"] = identity
                            if _is_admin_path(request.url.path) and not (
                                "admin" in identity.roles and "admin" in identity.scopes
                            ):
                                return await JSONResponse(
                                    {"error": "Admin access required"}, status_code=403
                                )(scope, receive, send)
                            logger.debug(
                                f"Authenticated API key id={resolved.record.id} for {request.url.path}"
                            )
                            return await self.app(scope, receive, send)
                        else:
                            logger.warning(
                                f"Rejected invalid API key for {request.url.path}"
                            )

            if not access_token and not session_token:
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
            elif not _is_valid_access_token(auth_service, access_token) and not (
                session_token and await auth_service.validate_session(session_token)
            ):
                logger.debug(f"Invalid authentication for {request.url.path}")
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
            # SECURITY: Fail closed when auth cannot be verified (CWE-280)
            if is_json_request:
                return await JSONResponse(
                    {"error": "Authentication service unavailable"}, status_code=503
                )(scope, receive, send)
            return await JSONResponse(
                {"error": "Authentication service unavailable"}, status_code=503
            )(scope, receive, send)
        finally:
            db.close()
