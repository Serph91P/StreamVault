import logging
import aiohttp
from app.config.settings import settings
from app.services.streamer_service import StreamerService
from app.services.twitch_api import twitch_api
from typing import Dict, List, Any, Optional
from urllib.parse import urlencode

logger = logging.getLogger("streamvault")

class TwitchAuthService:
    def __init__(self, streamer_service: StreamerService):
        self.streamer_service = streamer_service
        self.client_id = settings.TWITCH_APP_ID
        self.client_secret = settings.TWITCH_APP_SECRET
        self.redirect_uri = f"{settings.BASE_URL}/api/twitch/callback"
        
    def get_auth_url(self) -> str:
        """Generate Twitch OAuth URL for user authentication"""
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "user:read:follows",
        }
        
        return f"https://id.twitch.tv/oauth2/authorize?{urlencode(params)}"
        
    async def exchange_code(self, code: str) -> Optional[Dict[str, Any]]:
        """Exchange authorization code for access token"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://id.twitch.tv/oauth2/token",
                    data={
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "code": code,
                        "grant_type": "authorization_code",
                        "redirect_uri": self.redirect_uri
                    }
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to exchange code: {response.status} - {error_text}")
                        return None
        except Exception as e:
            logger.error(f"Error exchanging code: {e}")
            return None
            
    async def get_user_followed_channels(self, access_token: str) -> List[Dict[str, Any]]:
        """Get channels followed by the user using the new API endpoint"""
        try:
            user_id = await self._get_authenticated_user_id(access_token)
            if not user_id:
                logger.error("Failed to get authenticated user ID")
                return []
                
            logger.debug(f"Got authenticated user ID: {user_id}")
                
            followed_channels = []
            pagination_cursor = None
            
            while True:
                channels_batch, pagination_cursor = await self._get_follows_page(
                    user_id, access_token, pagination_cursor
                )
                
                if channels_batch:
                    followed_channels.extend(channels_batch)
                
                if not pagination_cursor:
                    break
                    
            return followed_channels
        except Exception as e:
            logger.error(f"Error getting followed channels: {e}")
            return []
    
    async def _get_authenticated_user_id(self, access_token: str) -> Optional[str]:
        """Get the user ID of the authenticated user"""
        try:
            user_data = await twitch_api.validate_token(access_token)
            if user_data:
                return user_data.get("user_id")
            return None
        except Exception as e:
            logger.error(f"Error getting user ID: {e}")
            return None
    
    async def _get_follows_page(self, user_id: str, access_token: str, cursor: Optional[str] = None) -> tuple[List[Dict[str, Any]], Optional[str]]:
        """Get a page of followed channels using the new API endpoint"""
        try:
            follows = await twitch_api.get_user_followed_streamers(user_id, access_token)
            
            # Debug logging 
            logger.debug(f"Successfully fetched {len(follows)} followed channels")
            
            # Extract broadcaster info
            streamers = []
            for follow in follows:
                streamer = {
                    "id": follow["broadcaster_id"],
                    "login": follow["broadcaster_login"],
                    "display_name": follow["broadcaster_name"]
                }
                streamers.append(streamer)
                
            return streamers, None  # No pagination cursor since we get all at once
            
        except Exception as e:
            logger.error(f"Error getting follows page: {e}")
            return [], None
            
    async def import_followed_streamers(self, streamers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Import multiple streamers in batch"""
        results = {
            "total": len(streamers),
            "added": 0,
            "skipped": 0,
            "failed": 0,
            "failures": []
        }
        
        for streamer in streamers:
            try:
                username = streamer["login"]
                added_streamer = await self.streamer_service.add_streamer(username)
                
                if added_streamer:
                    if added_streamer.username == username:
                        results["added"] += 1
                    else:
                        # This was an existing streamer
                        results["skipped"] += 1
                else:
                    results["failed"] += 1
                    results["failures"].append({
                        "username": username,
                        "reason": "Could not add streamer"
                    })
            except Exception as e:
                logger.error(f"Error importing streamer {streamer.get('login')}: {e}")
                results["failed"] += 1
                results["failures"].append({
                    "username": streamer.get("login", "unknown"),
                    "reason": str(e)
                })
                
        return results