from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import RedirectResponse
from app.services.api.twitch_oauth_service import TwitchOAuthService
from app.services.streamer_service import StreamerService
from app.dependencies import get_streamer_service
from typing import List, Dict, Any
import logging

logger = logging.getLogger("streamvault")

router = APIRouter(
    prefix="/api/twitch",
    tags=["twitch-oauth"]
)

def get_twitch_oauth_service(
    streamer_service: StreamerService = Depends(get_streamer_service)
) -> TwitchOAuthService:
    return TwitchOAuthService(streamer_service)

@router.get("/auth-url")
async def get_twitch_auth_url(
    state: str = Query(None, description="Return URL after OAuth (e.g., '/settings' or '/add-streamer')"),
    oauth_service: TwitchOAuthService = Depends(get_twitch_oauth_service)
):
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
    response: Response = None
):
    """Handle Twitch OAuth callback
    
    Args:
        code: Authorization code from Twitch
        state: Return URL (e.g., '/settings' or '/add-streamer')
    """
    # Exchange code for access token
    token_data = await oauth_service.exchange_code(code)
    
    if not token_data or "access_token" not in token_data:
        logger.error("Failed to get access token from Twitch")
        # Redirect to error page with state-aware return URL
        error_url = state if state else "/add-streamer"
        return RedirectResponse(url=f"{error_url}?error=auth_failed")
    
    # Store refresh token in database for automatic token refresh
    access_token = token_data["access_token"]
    refresh_token = token_data.get("refresh_token")
    expires_in = token_data.get("expires_in", 14400)  # Default 4 hours
    
    if refresh_token:
        # Store refresh token in database for automatic renewal
        from app.database import SessionLocal
        from app.services.system.twitch_token_service import TwitchTokenService
        
        with SessionLocal() as db:
            try:
                token_service = TwitchTokenService(db)
                success = await token_service.store_oauth_tokens(
                    access_token=access_token,
                    refresh_token=refresh_token,
                    expires_in=expires_in
                )
                
                if success:
                    logger.info("✅ Twitch OAuth tokens stored - automatic refresh enabled")
                else:
                    logger.warning("Failed to store OAuth tokens in database")
            except Exception as e:
                logger.error(f"Error storing OAuth tokens: {e}")
    
    # Determine return URL based on state parameter or default
    if state == "/settings":
        # For settings page: Just redirect back without token in URL (stored in DB)
        logger.info("✅ Twitch OAuth completed - redirecting to /settings")
        return RedirectResponse(url="/settings?auth_success=true")
    else:
        # For add-streamer page: Include token in URL for importing followed channels
        return_url = state if state else "/add-streamer"
        logger.info(f"✅ Twitch OAuth completed - redirecting to {return_url}")
        redirect_url = f"{return_url}?token={access_token}&auth_success=true"
        return RedirectResponse(url=redirect_url)

@router.get("/followed-channels")
async def get_followed_channels(
    access_token: str = Query(...),
    oauth_service: TwitchOAuthService = Depends(get_twitch_oauth_service)
):
    """Get channels that the authenticated user follows"""
    logger.debug(f"Fetching followed channels with access token: {access_token[:10]}...")
    
    followed_channels = await oauth_service.get_user_followed_channels(access_token)
    
    if followed_channels is None:
        logger.error("Invalid access token or failed to fetch channels")
        raise HTTPException(status_code=401, detail="Invalid access token")
    
    logger.debug(f"Returning {len(followed_channels)} followed channels")
    return {"channels": followed_channels}
@router.post("/import-streamers")
async def import_streamers(
    streamers: List[Dict[str, Any]],
    oauth_service: TwitchOAuthService = Depends(get_twitch_oauth_service)
):
    """Import selected streamers from followed channels"""
    if not streamers:
        raise HTTPException(status_code=400, detail="No streamers provided")
        
    results = await oauth_service.import_followed_streamers(streamers)
    return results

@router.get("/callback-url")
async def get_callback_url():
    """Get the configured callback URL for Twitch OAuth"""
    from app.config.settings import settings
    callback_url = f"{settings.BASE_URL}/api/twitch/callback"
    return {"url": callback_url}

@router.get("/connection-status")
async def get_connection_status():
    """Check if Twitch OAuth is connected (has valid refresh token)"""
    from app.database import SessionLocal
    from app.models import GlobalSettings
    
    with SessionLocal() as db:
        try:
            global_settings = db.query(GlobalSettings).first()
            
            # Check if refresh token exists
            has_refresh_token = bool(
                global_settings and 
                global_settings.twitch_refresh_token and 
                global_settings.twitch_refresh_token.strip()
            )
            
            # Check if token is still valid (not expired)
            is_valid = False
            if has_refresh_token and global_settings.twitch_token_expires_at:
                from datetime import datetime, timezone
                is_valid = datetime.now(timezone.utc) < global_settings.twitch_token_expires_at
            
            return {
                "connected": has_refresh_token,
                "valid": is_valid,
                "expires_at": global_settings.twitch_token_expires_at.isoformat() if global_settings and global_settings.twitch_token_expires_at else None
            }
        except Exception as e:
            logger.error(f"Error checking connection status: {e}")
            return {"connected": False, "valid": False, "expires_at": None}

@router.post("/disconnect")
async def disconnect_twitch():
    """Disconnect Twitch OAuth (clear refresh token)"""
    from app.database import SessionLocal
    from app.services.system.twitch_token_service import TwitchTokenService
    
    with SessionLocal() as db:
        try:
            token_service = TwitchTokenService(db)
            success = token_service.clear_tokens()
            
            if success:
                logger.info("✅ Twitch OAuth disconnected")
                return {"success": True, "message": "Twitch account disconnected"}
            else:
                return {"success": False, "message": "Failed to disconnect"}
        except Exception as e:
            logger.error(f"Error disconnecting Twitch: {e}")
            raise HTTPException(status_code=500, detail=str(e))
