from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import RedirectResponse
from app.services.twitch_auth_service import TwitchAuthService
from app.services.streamer_service import StreamerService
from app.dependencies import get_streamer_service
from typing import List, Dict, Any
import logging

logger = logging.getLogger("streamvault")

router = APIRouter(
    prefix="/api/twitch",
    tags=["twitch-auth"]
)

def get_twitch_auth_service(
    streamer_service: StreamerService = Depends(get_streamer_service)
) -> TwitchAuthService:
    return TwitchAuthService(streamer_service)

@router.get("/auth-url")
async def get_twitch_auth_url(
    auth_service: TwitchAuthService = Depends(get_twitch_auth_service)
):
    """Get Twitch OAuth authorization URL"""
    auth_url = auth_service.get_auth_url()
    return {"auth_url": auth_url}

@router.get("/callback")
async def twitch_callback(
    code: str = Query(...),
    auth_service: TwitchAuthService = Depends(get_twitch_auth_service)
):
    """Handle Twitch OAuth callback"""
    # Exchange code for access token
    token_data = await auth_service.exchange_code(code)
    
    if not token_data or "access_token" not in token_data:
        logger.error("Failed to get access token from Twitch")
        # Redirect to error page
        return RedirectResponse(url="/add-streamer?error=auth_failed")
    
    # Store token in query parameter (not ideal for security, but simplest for this demonstration)
    # In production, you would want to use a session or secure cookie
    access_token = token_data["access_token"]
    
    # Redirect back to the import page with the token
    return RedirectResponse(url=f"/add-streamer?token={access_token}")

@router.get("/followed-channels")
async def get_followed_channels(
    access_token: str = Query(...),
    auth_service: TwitchAuthService = Depends(get_twitch_auth_service)
):
    """Get channels that the authenticated user follows"""
    logger.debug(f"Fetching followed channels with access token: {access_token[:10]}...")
    
    followed_channels = await auth_service.get_user_followed_channels(access_token)
    
    if followed_channels is None:
        logger.error("Invalid access token or failed to fetch channels")
        raise HTTPException(status_code=401, detail="Invalid access token")
    
    logger.debug(f"Returning {len(followed_channels)} followed channels")
    return {"channels": followed_channels}
@router.post("/import-streamers")
async def import_streamers(
    streamers: List[Dict[str, Any]],
    auth_service: TwitchAuthService = Depends(get_twitch_auth_service)
):
    """Import selected streamers from followed channels"""
    if not streamers:
        raise HTTPException(status_code=400, detail="No streamers provided")
        
    results = await auth_service.import_followed_streamers(streamers)
    return results
