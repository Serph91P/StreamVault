"""
Twitch API Service for StreamVault

Centralized service for making Twitch API calls. Provides methods for getting
user information, game data, category information, and other Twitch API interactions.
"""

import logging
import aiohttp
from typing import Dict, Any, Optional, List
from app.config.settings import settings

logger = logging.getLogger("streamvault")

class TwitchAPIService:
    """Centralized Twitch API service"""
    
    def __init__(self):
        self.client_id = settings.TWITCH_APP_ID
        self.client_secret = settings.TWITCH_APP_SECRET
        self.base_url = "https://api.twitch.tv/helix"
        self._access_token = None
    
    async def get_access_token(self) -> str:
        """Get or refresh Twitch access token"""
        if not self._access_token:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://id.twitch.tv/oauth2/token",
                    params={
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "grant_type": "client_credentials"
                    }
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        self._access_token = data["access_token"]
                        logger.debug("Successfully obtained Twitch access token")
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to get Twitch access token: {response.status} - {error_text}")
                        raise ValueError(f"Failed to get access token: {response.status}")
        return self._access_token
    
    async def get_users_by_login(self, usernames: List[str]) -> List[Dict[str, Any]]:
        """Get user data by username(s)"""
        if not usernames:
            return []
            
        token = await self.get_access_token()
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/users",
                params={"login": usernames},
                headers={
                    "Client-ID": self.client_id,
                    "Authorization": f"Bearer {token}"
                }
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("data", [])
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to get users by login. Status: {response.status} - {error_text}")
                    return []
    
    async def get_users_by_id(self, user_ids: List[str]) -> List[Dict[str, Any]]:
        """Get user data by user ID(s)"""
        if not user_ids:
            return []
            
        token = await self.get_access_token()
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/users",
                params={"id": user_ids},
                headers={
                    "Client-ID": self.client_id,
                    "Authorization": f"Bearer {token}"
                }
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("data", [])
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to get users by ID. Status: {response.status} - {error_text}")
                    return []
    
    async def get_games_by_name(self, game_names: List[str]) -> List[Dict[str, Any]]:
        """Get game/category data by name(s)"""
        if not game_names:
            return []
            
        token = await self.get_access_token()
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/games",
                params={"name": game_names},
                headers={
                    "Client-ID": self.client_id,
                    "Authorization": f"Bearer {token}"
                }
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("data", [])
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to get games by name. Status: {response.status} - {error_text}")
                    return []
    
    async def get_games_by_id(self, game_ids: List[str]) -> List[Dict[str, Any]]:
        """Get game/category data by ID(s)"""
        if not game_ids:
            return []
            
        token = await self.get_access_token()
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/games",
                params={"id": game_ids},
                headers={
                    "Client-ID": self.client_id,
                    "Authorization": f"Bearer {token}"
                }
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("data", [])
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to get games by ID. Status: {response.status} - {error_text}")
                    return []
    
    async def get_streams(self, user_ids: List[str] = None, user_logins: List[str] = None, 
                         game_ids: List[str] = None) -> List[Dict[str, Any]]:
        """Get stream data"""
        token = await self.get_access_token()
        
        params = {}
        if user_ids:
            params["user_id"] = user_ids
        if user_logins:
            params["user_login"] = user_logins
        if game_ids:
            params["game_id"] = game_ids
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/streams",
                params=params,
                headers={
                    "Client-ID": self.client_id,
                    "Authorization": f"Bearer {token}"
                }
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("data", [])
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to get streams. Status: {response.status} - {error_text}")
                    return []
    
    async def search_categories(self, query: str) -> List[Dict[str, Any]]:
        """Search for games/categories"""
        if not query:
            return []
            
        token = await self.get_access_token()
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/search/categories",
                params={"query": query},
                headers={
                    "Client-ID": self.client_id,
                    "Authorization": f"Bearer {token}"
                }
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("data", [])
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to search categories. Status: {response.status} - {error_text}")
                    return []
    
    async def get_top_games(self, first: int = 20) -> List[Dict[str, Any]]:
        """Get top games on Twitch"""
        token = await self.get_access_token()
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/games/top",
                params={"first": first},
                headers={
                    "Client-ID": self.client_id,
                    "Authorization": f"Bearer {token}"
                }
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("data", [])
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to get top games. Status: {response.status} - {error_text}")
                    return []
    
    async def get_user_followed_streamers(self, user_id: str, access_token: str) -> List[Dict[str, Any]]:
        """Get followed streamers for a user (requires user access token)"""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/channels/followed",
                params={"user_id": user_id},
                headers={
                    "Client-ID": self.client_id,
                    "Authorization": f"Bearer {access_token}"
                }
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("data", [])
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to get followed streamers. Status: {response.status} - {error_text}")
                    return []
    
    async def validate_token(self, access_token: str) -> Optional[Dict[str, Any]]:
        """Validate an access token and get user info"""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://id.twitch.tv/oauth2/validate",
                headers={"Authorization": f"OAuth {access_token}"}
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Failed to validate token. Status: {response.status}")
                    return None

# Global instance
twitch_api = TwitchAPIService()
