import logging
import time
from dataclasses import dataclass, field
from threading import Lock
from collections import defaultdict
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse, FileResponse
from sqlalchemy.orm import Session
from app.services.core.auth_service import (
    AuthService,
    AuthTokenError,
    RefreshTokenReplayError,
)
from app.dependencies import (
    AuthIdentity,
    get_auth_service,
    get_current_identity,
    get_current_user,
    get_db,
)
from app.schemas.auth import UserCreate

from app.models import SystemState, User

logger = logging.getLogger("streamvault")

router = APIRouter(tags=["auth"])


# SECURITY: Per-IP login rate limiting to prevent brute-force attacks (CWE-307)
@dataclass
class LoginThrottle:
    attempts: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))
    lock: Lock = field(default_factory=Lock)


_default_login_throttle = LoginThrottle()
_login_attempts = _default_login_throttle.attempts
_LOGIN_MAX_ATTEMPTS = 5  # Max attempts per window
_LOGIN_WINDOW_SECONDS = 300  # 5-minute sliding window
_LOGIN_LOCKOUT_SECONDS = 900  # 15-minute lockout after exceeding limit


def _check_login_rate_limit(
    client_ip: str, *, attempts_by_ip: dict[str, list[float]] | None = None
) -> None:
    """Check if the IP has exceeded the login rate limit."""
    now = time.monotonic()
    history = attempts_by_ip if attempts_by_ip is not None else _login_attempts
    attempts = history[client_ip]

    # Remove attempts outside the window
    history[client_ip] = [t for t in attempts if now - t < _LOGIN_WINDOW_SECONDS]
    attempts = history[client_ip]

    if len(attempts) >= _LOGIN_MAX_ATTEMPTS:
        # Check if still in lockout period from the last attempt
        oldest_in_window = min(attempts) if attempts else now
        lockout_remaining = _LOGIN_LOCKOUT_SECONDS - (now - oldest_in_window)
        if lockout_remaining > 0:
            logger.warning(f"🚨 SECURITY: Login rate limit exceeded for IP {client_ip}")
            raise HTTPException(
                status_code=429,
                detail="Too many login attempts. Please try again later.",
                headers={"Retry-After": str(int(lockout_remaining))},
            )
        # Lockout expired, clear old attempts
        history[client_ip] = []


def _record_login_attempt(
    client_ip: str, *, attempts_by_ip: dict[str, list[float]] | None = None
) -> None:
    """Record a failed login attempt."""
    history = attempts_by_ip if attempts_by_ip is not None else _login_attempts
    history[client_ip].append(time.monotonic())


def _auth_throttle(request: Request | None) -> LoginThrottle:
    if request is None:
        return _default_login_throttle
    throttle: LoginThrottle = getattr(
        request.app.state, "login_throttle", _default_login_throttle
    )
    return throttle


def _get_or_create_system_state(db: Session) -> SystemState:
    """Return the singleton SystemState row, creating it on first access."""
    state = db.query(SystemState).filter(SystemState.id == 1).first()
    if state is None:
        state = SystemState(id=1, welcome_completed=False)
        db.add(state)
        db.commit()
        db.refresh(state)
    return state


@router.api_route("/setup", methods=["GET", "HEAD"])
def setup_page(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
    db: Session = Depends(get_db, scope="function"),
):
    admin_exists = auth_service.admin_exists_sync()

    # Always return JSON for XHR/fetch requests
    if request.headers.get(
        "X-Requested-With"
    ) == "XMLHttpRequest" or "application/json" in request.headers.get("accept", ""):
        state = _get_or_create_system_state(db)
        return JSONResponse(
            content={
                "setup_required": not admin_exists,
                "welcome_completed": bool(state.welcome_completed),
            },
            headers={"Content-Type": "application/json"},
        )

    # Handle browser requests
    if admin_exists:
        return RedirectResponse(url="/auth/login", status_code=307)
    return FileResponse("app/frontend/dist/index.html")


@router.post("/setup")
def setup_admin(
    request: UserCreate,
    http_request: Request,
    auth_service: AuthService = Depends(get_auth_service),
):
    # Preserve first-admin admission when moving work off the event loop.
    with _auth_throttle(http_request).lock:
        return _setup_admin_in_worker(request, auth_service)


def _setup_admin_in_worker(request: UserCreate, auth_service: AuthService):
    if auth_service.admin_exists_sync():
        raise HTTPException(status_code=400, detail="Admin already exists")

    admin = auth_service.create_admin_sync(request)
    token = auth_service.create_session_sync(admin.id)

    response = JSONResponse(
        content={"message": "Admin account created", "success": True}
    )
    settings = auth_service.settings
    # FIX: Cookie-Pfad explizit auf Root setzen + max_age, damit es für alle Routen (/api/..., /videos, PWA) gesendet wird.
    # Vorheriger Zustand: Standard-Pfad "/auth" -> Cookie wurde bei anderen Pfaden nicht mitgesendet -> ständiges Ausloggen.
    response.set_cookie(
        key="session",
        value=token,
        httponly=True,
        secure=settings.USE_SECURE_COOKIES,  # Auto-configured for reverse proxy
        samesite="lax",
        path="/",
        max_age=60 * 60 * 24,  # Entspricht 24h (AuthService.session_timeout_hours)
    )
    return response


@router.post("/login")
def login(
    request: UserCreate,
    http_request: Request = None,
    auth_service: AuthService = Depends(get_auth_service),
):
    throttle = _auth_throttle(http_request)
    # Keep failure admission atomic across workers with unchanged budgets.
    with throttle.lock:
        return _login_in_worker(request, http_request, auth_service, throttle.attempts)


def _login_in_worker(
    request: UserCreate,
    http_request: Request | None,
    auth_service: AuthService,
    attempts: dict[str, list[float]],
):
    try:
        # SECURITY: Only trust X-Forwarded-For behind a reverse proxy.
        # Use request.client.host as primary; X-Forwarded-For only supplements.
        client_ip = "unknown"
        if http_request:
            client_ip = http_request.client.host if http_request.client else "unknown"
        _check_login_rate_limit(client_ip, attempts_by_ip=attempts)

        # Validate input
        if not request.username or not request.password:
            logger.warning(
                f"Login attempt with missing credentials: username={bool(request.username)}, password={bool(request.password)}"
            )
            raise HTTPException(
                status_code=400, detail="Username and password are required"
            )

        user = auth_service.validate_login_sync(request.username, request.password)
        if not user:
            # Record failed attempt for rate limiting
            _record_login_attempt(client_ip, attempts_by_ip=attempts)
            logger.warning(f"Failed login attempt for username: {request.username}")
            raise HTTPException(status_code=401, detail="Invalid credentials")

        tokens = auth_service.issue_token_pair(user)
        response = JSONResponse(
            content={"message": "Login successful", "success": True}
        )
        # Set secure based on configuration, httponly=True for XSS protection
        settings = auth_service.settings
        # Siehe Kommentar oben: Pfad & max_age setzen
        response.set_cookie(
            key="access_token",
            value=tokens.access_token,
            httponly=True,
            secure=settings.USE_SECURE_COOKIES,
            samesite="lax",
            path="/",
            max_age=15 * 60,
        )
        response.set_cookie(
            key="refresh_token",
            value=tokens.refresh_token,
            httponly=True,
            secure=settings.USE_SECURE_COOKIES,
            samesite="lax",
            path="/auth",
            max_age=60 * 60 * 24,
        )
        logger.info(f"Successful login for user: {request.username}")
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during login: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.api_route("/login", methods=["GET", "HEAD"])
def login_page(request: Request, auth_service: AuthService = Depends(get_auth_service)):
    def is_api_request() -> bool:
        """Check if this is an API request that expects JSON response"""
        return request.headers.get(
            "X-Requested-With"
        ) == "XMLHttpRequest" or "application/json" in request.headers.get("accept", "")

    def serve_spa_or_error():
        """Serve SPA or return appropriate error response"""
        try:
            return FileResponse("app/frontend/dist/index.html")
        except Exception as file_error:
            logger.error(f"Error serving index.html: {file_error}")
            if is_api_request():
                return JSONResponse(
                    content={"error": "Internal server error"}, status_code=500
                )
            raise HTTPException(status_code=500, detail="Unable to serve login page")

    try:
        admin_exists = auth_service.admin_exists_sync()

        # Handle API requests
        if is_api_request():
            if not admin_exists:
                return JSONResponse(content={"redirect": "/auth/setup"})
            return JSONResponse(content={"login_required": True})

        # Handle browser requests - serve SPA (frontend handles routing)
        return serve_spa_or_error()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in login_page: {e}")
        return serve_spa_or_error()


@router.get("/check")
def check_auth(request: Request, auth_service: AuthService = Depends(get_auth_service)):
    admin_exists = auth_service.admin_exists_sync()
    if not admin_exists:
        return JSONResponse(content={"setup_required": True})

    token = request.cookies.get("access_token")
    if token:
        try:
            auth_service.resolve_access_token(token)
            return JSONResponse(content={"authenticated": True})
        except AuthTokenError:
            pass
    session_token = request.cookies.get("session")
    if not session_token or auth_service.resolve_legacy_session(session_token) is None:
        return JSONResponse(content={"authenticated": False})
    return JSONResponse(content={"authenticated": True})


@router.post("/refresh")
def refresh_access_token(
    request: Request, auth_service: AuthService = Depends(get_auth_service)
):
    raw_token = request.cookies.get("refresh_token")
    if not raw_token:
        raise HTTPException(status_code=401, detail="Refresh token required")
    try:
        tokens = auth_service.rotate_refresh_token(raw_token)
    except RefreshTokenReplayError:
        raise HTTPException(status_code=401, detail="Refresh token replay detected")
    except AuthTokenError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    settings = auth_service.settings
    response = JSONResponse(content={"success": True})
    response.set_cookie(
        key="access_token",
        value=tokens.access_token,
        httponly=True,
        secure=settings.USE_SECURE_COOKIES,
        samesite="lax",
        path="/",
        max_age=15 * 60,
    )
    response.set_cookie(
        key="refresh_token",
        value=tokens.refresh_token,
        httponly=True,
        secure=settings.USE_SECURE_COOKIES,
        samesite="lax",
        path="/auth",
        max_age=60 * 60 * 24,
    )
    return response


@router.post("/logout")
def logout(request: Request, auth_service: AuthService = Depends(get_auth_service)):
    try:
        refresh_token = request.cookies.get("refresh_token")
        if refresh_token:
            auth_service.revoke_refresh_token(refresh_token)
        session_token = request.cookies.get("session")
        if session_token:
            auth_service.delete_session_sync(session_token)
            logger.info("User logged out successfully")

        response = JSONResponse(
            content={"message": "Logout successful", "success": True}
        )
        response.delete_cookie(key="access_token", path="/")
        response.delete_cookie(key="refresh_token", path="/auth")
        response.delete_cookie(key="session", path="/")
        return response
    except Exception as e:
        logger.error(f"Logout error: {e}")
        response = JSONResponse(
            content={"message": "Logout completed", "success": True}
        )
        response.delete_cookie(key="access_token", path="/")
        response.delete_cookie(key="refresh_token", path="/auth")
        response.delete_cookie(key="session", path="/")
        return response


@router.post("/keepalive")
def keepalive(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
    identity: AuthIdentity = Depends(get_current_identity),
):
    """Refresh legacy sessions while accepting the stateless JWT auth contract."""
    try:
        if identity.auth_method == "jwt":
            return JSONResponse(content={"ok": True})

        session_token = request.cookies.get("session")
        if not session_token:
            return JSONResponse(
                content={"ok": False, "reason": "no_session"}, status_code=401
            )

        refreshed = auth_service.resolve_legacy_session(session_token) is not None
        if not refreshed:
            return JSONResponse(
                content={"ok": False, "reason": "invalid_or_expired"}, status_code=401
            )

        # Optionally update cookie to extend browser-side expiration if we use max-age in the future
        return JSONResponse(content={"ok": True})
    except Exception as e:
        logger.error(f"Keepalive error: {e}")
        return JSONResponse(content={"ok": False}, status_code=500)


@router.get("/onboarding-state")
def get_onboarding_state(db: Session = Depends(get_db)):
    """Return persistent onboarding flags so the frontend router can decide
    whether to show the welcome screen without relying on browser localStorage.
    """
    state = _get_or_create_system_state(db)
    return JSONResponse(
        content={
            "welcome_completed": bool(state.welcome_completed),
            "welcome_completed_at": state.welcome_completed_at.isoformat()
            if state.welcome_completed_at
            else None,
        }
    )


@router.post("/onboarding/complete")
def complete_onboarding(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark the welcome screen as completed for the whole installation.

    Authenticated only: anonymous callers must not be able to flip the flag.
    Idempotent: repeated calls do not change `welcome_completed_at`.
    """
    state = _get_or_create_system_state(db)
    if not state.welcome_completed:
        state.welcome_completed = True
        state.welcome_completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(state)
        logger.info(
            f"Onboarding completed by user {current_user.username} (id={current_user.id})"
        )
    return JSONResponse(
        content={
            "welcome_completed": bool(state.welcome_completed),
            "welcome_completed_at": state.welcome_completed_at.isoformat()
            if state.welcome_completed_at
            else None,
        }
    )
