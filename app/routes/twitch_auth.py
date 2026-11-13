import aiohttp
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from starlette.requests import HTTPConnection
from pydantic import BaseModel, Field
from app.services.api.twitch_oauth_service import TwitchOAuthService
from app.services.streamer_service import StreamerService
from app.dependencies import get_streamer_service, get_application_twitch_token_service
from app.dependencies import get_application_twitch_oauth_service
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


@router.get("/auth-url", response_model=None)
async def get_twitch_auth_url(
    state: str = Query(
        None,
        description="Return URL after OAuth (e.g., '/settings' or '/add-streamer')",
    ),
    oauth_service: TwitchOAuthService = Depends(get_twitch_oauth_service),
) -> dict[str, str]:
    """Get Twitch OAuth authorization URL

    Args:
        state: Optional return URL to redirect to after OAuth completes
    """
    auth_url = oauth_service.get_auth_url(state=state)
    return {"auth_url": auth_url}


@router.get("/callback")
async def twitch_callback(
    code: str = Query(...),
    state: str = Query(None, description="Return URL passed from OAuth initiation"),
    oauth_service: TwitchOAuthService = Depends(get_twitch_oauth_service),
    token_service: TwitchTokenService = Depends(get_application_twitch_token_service),
) -> RedirectResponse:
    """Handle Twitch OAuth callback

    Args:
        code: Authorization code from Twitch
        state: Return URL (e.g., '/settings' or '/add-streamer')
    """
    # Exchange code for access token
    token_data = await oauth_service.exchange_code(code)

    if not token_data or "access_token" not in token_data:
        logger.error("Failed to get access token from Twitch")
        # SECURITY: Use constant redirect URL to prevent open redirect attacks (CWE-601)
        # Always redirect to /add-streamer on auth failure (safe, no user input)
        return RedirectResponse(url="/add-streamer?error=auth_failed")

    # Store refresh token in database for automatic token refresh
    access_token = token_data["access_token"]
    refresh_token = token_data.get("refresh_token")
    expires_in = token_data.get("expires_in", 14400)  # Default 4 hours

    if refresh_token:
        # Store refresh token in database for automatic renewal
        try:
            assert isinstance(access_token, str)
            assert isinstance(refresh_token, str)
            assert isinstance(expires_in, (int, float))
            success = await token_service.store_oauth_tokens(
                access_token=access_token,
                refresh_token=refresh_token,
                expires_in=expires_in,
            )

            if success:
                logger.info("✅ Twitch OAuth tokens stored - automatic refresh enabled")
            else:
                logger.warning("Failed to store OAuth tokens in database")
        except Exception:
            logger.error("Error storing OAuth tokens")

    # SECURITY: Use whitelisted constant redirects to prevent open redirect attacks (CWE-601)
    # Only allow two safe destinations: /settings or /add-streamer
    # SECURITY: Never pass tokens in URLs — they leak via browser history, logs, and Referer headers
    # The token is already stored in the database via store_oauth_tokens() above

    # Validate state parameter against whitelist
    if state and state.strip() == "/add-streamer":
        logger.info("✅ Twitch OAuth completed - redirecting to /add-streamer")
        return RedirectResponse(url="/add-streamer?auth_success=true")
    else:
        # Default: For settings page, redirect without token in URL (stored in DB)
        logger.info("✅ Twitch OAuth completed - redirecting to /settings")
        return RedirectResponse(url="/settings?auth_success=true")


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
        access_token = await token_service.get_valid_access_token()

        if not access_token:
            raise HTTPException(
                status_code=401,
                detail="No Twitch access token available. Please connect your Twitch account first.",
            )

    try:
        followed_channels = await oauth_service.get_user_followed_channels(access_token)
    except TimeoutError:
        raise HTTPException(
            status_code=504, detail="Twitch follow request timed out"
        ) from None
    except (ConnectionError, ValueError, aiohttp.ClientError):
        raise HTTPException(
            status_code=502, detail="Could not load complete Twitch follows"
        ) from None

    if followed_channels is None:
        logger.error("Invalid access token or failed to fetch channels")
        raise HTTPException(status_code=401, detail="Invalid access token")

    logger.debug(f"Returning {len(followed_channels)} followed channels")
    return {"channels": followed_channels}


@router.post("/import-streamers", response_model=None)
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


@router.post("/manual-token", response_model=None)
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


@router.post("/disconnect", response_model=None)
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
