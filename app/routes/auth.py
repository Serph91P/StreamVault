import logging
import time
from collections import defaultdict
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse, FileResponse
from sqlalchemy.orm import Session
from app.services.core.auth_service import AuthService
from app.dependencies import get_auth_service, get_current_user, get_db
from app.schemas.auth import UserCreate
from app.config.settings import get_settings
from app.models import SystemState, User

logger = logging.getLogger("streamvault")

router = APIRouter(tags=["auth"])

# SECURITY: Per-IP login rate limiting to prevent brute-force attacks (CWE-307)
_login_attempts: dict[str, list[float]] = defaultdict(list)
_LOGIN_MAX_ATTEMPTS = 5  # Max attempts per window
_LOGIN_WINDOW_SECONDS = 300  # 5-minute sliding window
_LOGIN_LOCKOUT_SECONDS = 900  # 15-minute lockout after exceeding limit


def _check_login_rate_limit(client_ip: str) -> None:
    """Check if the IP has exceeded the login rate limit."""
    now = time.monotonic()
    attempts = _login_attempts[client_ip]

    # Remove attempts outside the window
    _login_attempts[client_ip] = [
        t for t in attempts if now - t < _LOGIN_WINDOW_SECONDS
    ]
    attempts = _login_attempts[client_ip]

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
        _login_attempts[client_ip] = []


def _record_login_attempt(client_ip: str) -> None:
    """Record a failed login attempt."""
    _login_attempts[client_ip].append(time.monotonic())


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
async def setup_page(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
    db: Session = Depends(get_db),
):
    admin_exists = await auth_service.admin_exists()

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
async def setup_admin(
    request: UserCreate, auth_service: AuthService = Depends(get_auth_service)
):
    if await auth_service.admin_exists():
        raise HTTPException(status_code=400, detail="Admin already exists")

    admin = await auth_service.create_admin(request)
    token = await auth_service.create_session(admin.id)

    response = JSONResponse(
        content={"message": "Admin account created", "success": True}
    )
    settings = get_settings()
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
async def login(
    request: UserCreate,
    http_request: Request = None,
    auth_service: AuthService = Depends(get_auth_service),
):
    try:
        # SECURITY: Only trust X-Forwarded-For behind a reverse proxy.
        # Use request.client.host as primary; X-Forwarded-For only supplements.
        client_ip = "unknown"
        if http_request:
            client_ip = http_request.client.host if http_request.client else "unknown"
        _check_login_rate_limit(client_ip)

        # Validate input
        if not request.username or not request.password:
            logger.warning(
                f"Login attempt with missing credentials: username={bool(request.username)}, password={bool(request.password)}"
            )
            raise HTTPException(
                status_code=400, detail="Username and password are required"
            )

        user = await auth_service.validate_login(request.username, request.password)
        if not user:
            # Record failed attempt for rate limiting
            _record_login_attempt(client_ip)
            logger.warning(f"Failed login attempt for username: {request.username}")
            raise HTTPException(status_code=401, detail="Invalid credentials")

        token = await auth_service.create_session(user.id)
        response = JSONResponse(
            content={"message": "Login successful", "success": True}
        )
        # Set secure based on configuration, httponly=True for XSS protection
        settings = get_settings()
        # Siehe Kommentar oben: Pfad & max_age setzen
        response.set_cookie(
            key="session",
            value=token,
            httponly=True,
            secure=settings.USE_SECURE_COOKIES,
            samesite="lax",
            path="/",
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
async def login_page(
    request: Request, auth_service: AuthService = Depends(get_auth_service)
):
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
        admin_exists = await auth_service.admin_exists()

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
async def check_auth(
    request: Request, auth_service: AuthService = Depends(get_auth_service)
):
    admin_exists = await auth_service.admin_exists()
    if not admin_exists:
        return JSONResponse(content={"setup_required": True})

    session_token = request.cookies.get("session")
    if not session_token or not await auth_service.validate_session(session_token):
        return JSONResponse(content={"authenticated": False})
    return JSONResponse(content={"authenticated": True})


@router.post("/logout")
async def logout(
    request: Request, auth_service: AuthService = Depends(get_auth_service)
):
    try:
        session_token = request.cookies.get("session")
        if session_token:
            await auth_service.delete_session(session_token)
            logger.info("User logged out successfully")

        response = JSONResponse(
            content={"message": "Logout successful", "success": True}
        )
        response.delete_cookie(key="session", path="/")
        return response
    except Exception as e:
        logger.error(f"Logout error: {e}")
        response = JSONResponse(
            content={"message": "Logout completed", "success": True}
        )
        response.delete_cookie(key="session", path="/")
        return response


@router.post("/keepalive")
async def keepalive(
    request: Request, auth_service: AuthService = Depends(get_auth_service)
):
    """Refresh the current session to implement sliding expiration."""
    try:
        session_token = request.cookies.get("session")
        if not session_token:
            return JSONResponse(
                content={"ok": False, "reason": "no_session"}, status_code=401
            )

        refreshed = await auth_service.refresh_session(session_token)
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
async def get_onboarding_state(db: Session = Depends(get_db)):
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
async def complete_onboarding(
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
