from fastapi import Request
from fastapi.responses import RedirectResponse, JSONResponse
from app.services.core.auth_service import AuthService
from app.services.core.api_key_service import ApiKeyService
from app.database import DatabaseLifecycle, SessionLocal
from app.config.settings import Settings
from sqlalchemy.orm import Session
import logging
from urllib.parse import urlsplit
from collections.abc import Callable
from typing import Literal, TYPE_CHECKING
from app.utils.async_db_utils import run_in_thread_pool

if TYPE_CHECKING:
    from app.dependencies import AuthIdentity

logger = logging.getLogger("streamvault")

_EXACT_PUBLIC_PATHS = frozenset(
    {
        "/api/openapi.json",
        "/icon-512x512.png",
        "/maskable-icon-192x192.png",
        "/maskable-icon-512x512.png",
    }
)
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


def _cookie_mutation_has_csrf_violation(request: Request) -> bool:
    """Reject cross-site browser mutations authenticated by ambient cookies."""
    if request.method.upper() in {"GET", "HEAD", "OPTIONS", "TRACE"}:
        return False
    if not (request.cookies.get("access_token") or request.cookies.get("session")):
        return False

    # HTTP authentication gives ambient session cookies precedence over Bearer
    # and API-key headers. Therefore a request carrying a session cookie remains
    # cookie-authenticated and must pass CSRF checks even when an unrelated or
    # invalid explicit credential is also present.

    fetch_site = request.headers.get("sec-fetch-site", "").lower()
    if fetch_site == "cross-site":
        return True

    origin = request.headers.get("origin")
    if not origin:
        # Preserve non-browser clients that do not send browser security headers.
        return False
    if origin == "null":
        return True
    parsed = urlsplit(origin)
    return (
        not parsed.scheme
        or parsed.netloc.lower() != request.headers.get("host", "").lower()
    )


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
    def __init__(
        self,
        app,
        *,
        database: DatabaseLifecycle | None = None,
        settings_provider: Callable[[], Settings] | None = None,
    ):
        self.app = app
        self._database = database
        self._settings_provider = settings_provider

    def _open_session(self) -> Session:
        if self._database is None:
            return SessionLocal()
        return self._database.sync_session_factory()

    def _auth_service(self, db: Session) -> AuthService:
        if self._settings_provider is None:
            return AuthService(db=db)
        return AuthService(db=db, settings=self._settings_provider())

    def _authorize_websocket(
        self, access_token: str | None, session_token: str | None
    ) -> bool:
        db = self._open_session()
        try:
            service = self._auth_service(db)
            return _is_valid_access_token(service, access_token) or bool(
                session_token
                and service.resolve_legacy_session(session_token) is not None
            )
        finally:
            db.close()

    def _authorize_http(
        self,
        path: str,
        access_token: str | None,
        session_token: str | None,
        api_key: str | None,
    ) -> tuple[Literal["allow", "setup", "login", "admin"], "AuthIdentity | None"]:
        db = self._open_session()
        try:
            service = self._auth_service(db)
            if not service.admin_exists_sync():
                return "setup", None
            if not access_token and not session_token and api_key:
                if path.startswith("/api/api-keys"):
                    logger.warning(
                        "Blocked API-key auth attempt on management endpoint %s", path
                    )
                else:
                    resolved = ApiKeyService(db=db).resolve_active_owner(api_key)
                    if resolved:
                        from app.dependencies import AuthIdentity

                        owner = resolved.owner
                        identity = AuthIdentity(
                            subject=str(owner.id),
                            roles=frozenset({"admin"})
                            if owner.is_admin
                            else frozenset({"user"}),
                            scopes=service._user_scopes(owner),
                            auth_method="api-key",
                            interactive=False,
                        )
                        if _is_admin_path(path) and not (
                            "admin" in identity.roles and "admin" in identity.scopes
                        ):
                            return "admin", identity
                        logger.debug(
                            "Authenticated API key id=%s for %s",
                            resolved.record.id,
                            path,
                        )
                        return "allow", identity
                    logger.warning("Rejected invalid API key for %s", path)
            if not access_token and not session_token:
                return "login", None
            if not _is_valid_access_token(service, access_token) and not (
                session_token
                and service.resolve_legacy_session(session_token) is not None
            ):
                return "login", None
            return "allow", None
        finally:
            db.close()

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
            try:
                valid = await run_in_thread_pool(
                    self._authorize_websocket, access_token, session_token
                )
                if not valid:
                    logger.warning(
                        "WebSocket connection rejected: invalid authentication"
                    )
                    await ws.accept()
                    await ws.close(code=4001, reason="Invalid session")
                    return
            except Exception as error:
                logger.error("WebSocket auth error (%s)", type(error).__name__)
                await ws.accept()
                await ws.close(code=4003, reason="Authentication service unavailable")
                return
            return await self.app(scope, receive, send)

        # Process HTTP requests
        request = Request(scope, receive=receive)
        is_json_request = request.headers.get(
            "X-Requested-With"
        ) == "XMLHttpRequest" or "application/json" in request.headers.get("accept", "")

        if _cookie_mutation_has_csrf_violation(request):
            logger.warning(
                "Blocked cross-site cookie mutation for %s", request.url.path
            )
            return await JSONResponse(
                {"error": "CSRF validation failed"}, status_code=403
            )(scope, receive, send)

        # Public paths that don't require authentication
        # SECURITY: Only paths that MUST work without a session belong here.
        # All data/media paths require auth to prevent unauthenticated access
        # to images, sync/cleanup POST endpoints, and system info.
        if _is_public_path(request.url.path):
            return await self.app(scope, receive, send)

        bearer_token = _extract_bearer_token(scope.get("headers", []))
        access_token = request.cookies.get("access_token") or bearer_token
        session_token = request.cookies.get("session") or bearer_token
        try:
            decision, identity = await run_in_thread_pool(
                self._authorize_http,
                request.url.path,
                access_token,
                session_token,
                _extract_api_key(request),
            )
            if identity is not None:
                scope.setdefault("state", {})["auth_identity"] = identity
            if decision == "setup":
                if is_json_request:
                    return await JSONResponse(
                        {"error": "Setup required", "redirect": "/auth/setup"},
                        status_code=307,
                    )(scope, receive, send)
                return await RedirectResponse(url="/auth/setup", status_code=307)(
                    scope, receive, send
                )
            if decision == "admin":
                return await JSONResponse(
                    {"error": "Admin access required"}, status_code=403
                )(scope, receive, send)
            if decision == "login":
                if is_json_request:
                    return await JSONResponse(
                        {"error": "Authentication required", "redirect": "/auth/login"},
                        status_code=401,
                    )(scope, receive, send)
                return await RedirectResponse(url="/auth/login", status_code=307)(
                    scope, receive, send
                )
            return await self.app(scope, receive, send)
        except Exception as error:
            logger.error(
                "Auth middleware error for %s (%s)",
                request.url.path,
                type(error).__name__,
            )
            # SECURITY: Fail closed when auth cannot be verified (CWE-280)
            return await JSONResponse(
                {"error": "Authentication service unavailable"}, status_code=503
            )(scope, receive, send)
