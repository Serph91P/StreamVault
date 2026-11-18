import aiohttp
from datetime import datetime
from hashlib import sha256
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse
from starlette.requests import HTTPConnection
from pydantic import BaseModel, Field
from app.services.api.twitch_oauth_service import (
    OAuthBrowserSession,
    TwitchOAuthService,
)
from app.services.streamer_service import StreamerService
from app.dependencies import get_streamer_service, get_application_twitch_token_service
from app.dependencies import (
    get_application_session_factory,
    get_application_twitch_oauth_service,
    get_current_identity,
    get_current_user,
    require_admin_user,
)
from app.services.system.twitch_token_service import (
    TwitchTokenService,
    TwitchTokenState,
)
from app.utils.async_db_utils import run_in_thread_pool
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger("streamvault")

router = APIRouter(prefix="/api/twitch", tags=["twitch-oauth"])


class ManualTokenRequest(BaseModel):
    token: str = Field(..., min_length=1, description="Twitch browser OAuth token")


class ConnectionStatusResponse(BaseModel):
    connected: bool
    valid: bool
    expires_at: Optional[str]
    source: Optional[str] = None
    has_env_token: bool = False


def _normalize_expires_at(expires_at: datetime | None) -> tuple[str | None, bool]:
    if not expires_at:
        return None, False

    from datetime import datetime, timezone

    expires_at_utc = expires_at
    if expires_at_utc.tzinfo is None:
        expires_at_utc = expires_at_utc.replace(tzinfo=timezone.utc)

    return expires_at.isoformat(), datetime.now(timezone.utc) < expires_at_utc


def _build_connection_status(
    global_settings: TwitchTokenState | None, env_token: Optional[str]
) -> dict[str, str | bool | None]:
    """Return status for the token source StreamVault will actually use."""
    has_env_token = bool(env_token and env_token.strip())
    has_db_token = bool(
        global_settings
        and global_settings.twitch_access_token
        and global_settings.twitch_access_token.strip()
    )
    has_refresh_token = bool(
        global_settings
        and global_settings.twitch_refresh_token
        and global_settings.twitch_refresh_token.strip()
    )

    expires_at_value = None
    is_db_token_valid = False
    if global_settings:
        expires_at_value, is_db_token_valid = _normalize_expires_at(
            global_settings.twitch_token_expires_at
        )

    source = None
    is_valid = False
    effective_expires_at = None

    # Manual browser tokens in the DB are preferred only while they are still
    # valid. If the saved browser token expired, status should reflect the env
    # fallback (when present) rather than stale expired database state.
    if has_db_token and not has_refresh_token and is_db_token_valid:
        source = "database_manual"
        is_valid = True
        effective_expires_at = expires_at_value
    elif has_env_token:
        source = "environment"
        is_valid = True
    elif has_db_token and has_refresh_token:
        source = "database_oauth"
        is_valid = is_db_token_valid
        effective_expires_at = expires_at_value
    elif has_refresh_token:
        source = "oauth_refresh"
    elif has_db_token:
        source = "database_manual"
        effective_expires_at = expires_at_value

    return {
        "connected": has_db_token or has_refresh_token or has_env_token,
        "valid": is_valid,
        "expires_at": effective_expires_at,
        "source": source,
        "has_env_token": has_env_token,
    }


def get_twitch_oauth_service(
    connection: HTTPConnection,
) -> TwitchOAuthService:
    return get_application_twitch_oauth_service(connection)


def _authorized_browser(request: Request) -> OAuthBrowserSession:
    factory = get_application_session_factory(request)
    identity = get_current_identity(request, factory)
    cookie_name = {"jwt": "access_token", "legacy-session": "session"}.get(
        identity.auth_method
    )
    if (
        not identity.interactive
        or cookie_name is None
        or not (token := request.cookies.get(cookie_name))
    ):
        raise HTTPException(status_code=403, detail="Browser session required")
    user = require_admin_user(get_current_user(identity, factory), identity)
    return user.id, cookie_name, sha256(token.encode()).digest()


@router.get("/auth-url", response_model=None)
async def get_twitch_auth_url(
    request: Request,
    response: Response,
    state: str | None = Query(
        None,
        description="Return URL after OAuth (e.g., '/settings' or '/add-streamer')",
    ),
    oauth_service: TwitchOAuthService = Depends(get_twitch_oauth_service),
) -> dict[str, str]:
    """Start a browser link. The legacy `state` input is only a return hint."""
    if request.headers.get("sec-fetch-site") not in (None, "none", "same-origin"):
        raise HTTPException(status_code=403, detail="Same-origin initiation required")
    browser = await run_in_thread_pool(_authorized_browser, request)
    response.headers["Cache-Control"] = "no-store"
    return {"auth_url": oauth_service.begin_link(browser, state)}


def _link_redirect(location: str) -> RedirectResponse:
    return RedirectResponse(
        url=location,
        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
    )


@router.get("/callback")
async def twitch_callback(
    request: Request,
    oauth_service: TwitchOAuthService = Depends(get_twitch_oauth_service),
    token_service: TwitchTokenService = Depends(get_application_twitch_token_service),
) -> RedirectResponse:
    """Consume the current browser's link grant before any provider or storage effect."""
    invalid = "/add-streamer?error=auth_failed"
    states = request.query_params.getlist("state")
    if len(states) != 1:
        return _link_redirect(invalid)
    try:
        browser = await run_in_thread_pool(_authorized_browser, request)
    except HTTPException:
        return _link_redirect(invalid)
    destination = oauth_service.consume_link(browser, states[0])
    if destination is None:
        return _link_redirect(invalid)

    failed = f"{destination}?error=auth_failed"
    codes = request.query_params.getlist("code")
    if "error" in request.query_params or len(codes) != 1 or not codes[0]:
        return _link_redirect(failed)
    token_data = await oauth_service.exchange_code(codes[0])
    if not token_data:
        return _link_redirect(failed)

    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    expires_in = token_data.get("expires_in", 14400)  # Default 4 hours
    if not (
        isinstance(access_token, str)
        and access_token
        and isinstance(refresh_token, str)
        and refresh_token
        and isinstance(expires_in, (int, float))
        and not isinstance(expires_in, bool)
        and 0 < expires_in < float("inf")
    ):
        return _link_redirect(failed)
    try:
        if await run_in_thread_pool(_authorized_browser, request) != browser:
            return _link_redirect(failed)
    except HTTPException:
        return _link_redirect(failed)
    try:
        success = await token_service.store_oauth_tokens(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
        )
    except Exception:
        logger.error("Error storing OAuth tokens")
        return _link_redirect(failed)
    if not success:
        logger.warning("Failed to store OAuth tokens in database")
        return _link_redirect(failed)
    logger.info("Twitch OAuth link completed")
    return _link_redirect(f"{destination}?auth_success=true")


@router.get("/followed-channels", response_model=None)
async def get_followed_channels(
    connection: HTTPConnection,
    access_token: str = Query(
        None, description="Optional access token (retrieved from DB if not provided)"
    ),
    oauth_service: TwitchOAuthService = Depends(get_twitch_oauth_service),
) -> dict[str, list[dict[str, object]]]:
    """Get channels that the authenticated user follows.

    SECURITY: Token is retrieved from database if not provided,
    avoiding the need to pass tokens via URL parameters.
    """
    # SECURITY: Do not log access tokens (even partial) - CWE-532
    logger.debug("Fetching followed channels with OAuth token")

    # If no token provided, retrieve from database
    if not access_token:
        token_service = await run_in_thread_pool(
            get_application_twitch_token_service, connection
        )
        stored_access_token = await token_service.get_valid_access_token()

        if not stored_access_token:
            raise HTTPException(
                status_code=401,
                detail="No Twitch access token available. Please connect your Twitch account first.",
            )
        access_token = stored_access_token

    try:
        followed_channels = await oauth_service.get_user_followed_channels(access_token)
    except TimeoutError:
        raise HTTPException(
            status_code=504, detail="Twitch follow request timed out"
        ) from None
    except ConnectionError, ValueError, aiohttp.ClientError:
        raise HTTPException(
            status_code=502, detail="Could not load complete Twitch follows"
        ) from None

    if followed_channels is None:
        logger.error("Invalid access token or failed to fetch channels")
        raise HTTPException(status_code=401, detail="Invalid access token")

    logger.debug(f"Returning {len(followed_channels)} followed channels")
    return {"channels": followed_channels}


@router.post(
    "/import-streamers", response_model=None, dependencies=[Depends(require_admin_user)]
)
async def import_streamers(
    streamers: List[Dict[str, Any]],
    oauth_service: TwitchOAuthService = Depends(get_twitch_oauth_service),
    streamer_service: StreamerService = Depends(get_streamer_service),
) -> dict[str, list[dict[str, object]]]:
    """Import selected streamers from followed channels"""
    if not streamers:
        raise HTTPException(status_code=400, detail="No streamers provided")

    results = await oauth_service.import_followed_streamers(
        streamers, streamer_service=streamer_service
    )
    return results


@router.get("/callback-url", response_model=None)
async def get_callback_url(
    oauth_service: TwitchOAuthService = Depends(get_twitch_oauth_service),
) -> dict[str, str]:
    """Get the configured callback URL for Twitch OAuth"""
    callback_url = oauth_service.redirect_uri
    return {"url": callback_url}


@router.get("/connection-status", response_model=ConnectionStatusResponse)
async def get_connection_status(
    token_service: TwitchTokenService = Depends(get_application_twitch_token_service),
) -> dict[str, str | bool | None]:
    """Check if a Twitch token is available in DB or env fallback."""
    try:
        state = await token_service.get_state()
        if state and state.twitch_access_token and not state.twitch_refresh_token:
            _, current = _normalize_expires_at(state.twitch_token_expires_at)
            if not current:
                await token_service.revalidate_stored_manual_token(state)
                state = await token_service.get_state()
        return _build_connection_status(
            state, token_service.settings.TWITCH_OAUTH_TOKEN
        )
    except Exception:
        logger.error("Error checking Twitch connection status")
        return {
            "connected": False,
            "valid": False,
            "expires_at": None,
            "source": None,
            "has_env_token": False,
        }


@router.post(
    "/manual-token", response_model=None, dependencies=[Depends(require_admin_user)]
)
async def save_manual_token(
    payload: ManualTokenRequest,
    token_service: TwitchTokenService = Depends(get_application_twitch_token_service),
) -> dict[str, object]:
    """Validate and store a manually supplied Twitch browser token encrypted in DB."""
    try:
        success, validation = await token_service.store_manual_access_token(
            payload.token
        )
        if not success:
            raise HTTPException(status_code=400, detail="Invalid Twitch OAuth token")
        expires_in = validation.get("expires_in") if validation else None
        logger.info("✅ Manual Twitch OAuth token saved")
        return {
            "success": True,
            "message": "Twitch OAuth token saved",
            "expires_in": expires_in,
        }
    except HTTPException:
        raise
    except Exception:
        logger.error("Error saving manual Twitch OAuth token")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/disconnect", response_model=None, dependencies=[Depends(require_admin_user)]
)
async def disconnect_twitch(
    token_service: TwitchTokenService = Depends(get_application_twitch_token_service),
) -> dict[str, str | bool]:
    """Disconnect Twitch OAuth (clear refresh token)"""
    try:
        success = await token_service.clear_tokens()
        if success:
            logger.info("✅ Twitch OAuth disconnected")
            return {"success": True, "message": "Twitch account disconnected"}
        return {"success": False, "message": "Failed to disconnect"}
    except Exception:
        logger.error("Error disconnecting Twitch")
        raise HTTPException(status_code=500, detail="Internal server error")
