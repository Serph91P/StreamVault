"""
TwitchIntegrationService - Twitch API calls and EventSub management

Extracted from streamer_service.py God Class
Handles all Twitch API interactions and EventSub subscriptions.
"""

import logging
from typing import Dict, Any, Optional, List
from app.services.twitch_api import twitch_api
from app.events.handler_registry import EventHandlerRegistry

logger = logging.getLogger("streamvault")


class TwitchIntegrationService:
    """Handles Twitch API calls and EventSub management"""
    
    def __init__(self, event_registry: EventHandlerRegistry):
        self.twitch_api = twitch_api
        self.event_registry = event_registry

    async def get_users_by_login(self, usernames: List[str]) -> List[Dict[str, Any]]:
        """Get user data by login names from Twitch API"""
        return await self.twitch_api.get_users_by_login(usernames)

    async def get_streamer_info(self, streamer_id: str) -> Optional[Dict[str, Any]]:
        """Get streamer info by Twitch ID"""
        users = await self.twitch_api.get_users_by_id([streamer_id])
        return users[0] if users else None

    async def get_user_data(self, username: str) -> Optional[Dict[str, Any]]:
        """Fetch user data from Twitch API by username"""
        try:
            users = await self.get_users_by_login([username])
            if users and len(users) > 0:
                return users[0]
            return None
        except Exception as e:
            logger.error(f"Error fetching user data for {username}: {e}")
            return None

    async def get_stream_info(self, twitch_id: str) -> Optional[Dict[str, Any]]:
        """Get current stream information for a Twitch user to check if they're live"""
        try:
            streams = await self.twitch_api.get_streams(user_ids=[twitch_id])
            return streams[0] if streams else None
        except Exception as e:
            logger.error(f"Error fetching stream info for {twitch_id}: {e}")
            return None

    async def get_game_data(self, game_id: str) -> Optional[Dict[str, Any]]:
        """Fetch game data from Twitch API including box art URL"""
        try:
            games = await self.twitch_api.get_games_by_id([game_id])
            if games:
                game_data = games[0]
                # Replace template placeholders in box art URL
                box_art_url = game_data.get("box_art_url", "")
                if box_art_url:
                    # Standard size for box art
                    box_art_url = box_art_url.replace("{width}", "285").replace("{height}", "380")
                    game_data["box_art_url"] = box_art_url
                return game_data
            return None
        except Exception as e:
            logger.error(f"Error fetching game data for {game_id}: {e}")
            return None

    async def get_multiple_stream_info(self, twitch_ids: List[str]) -> List[Dict[str, Any]]:
        """Get stream information for multiple users"""
        try:
            streams = await self.twitch_api.get_streams(user_ids=twitch_ids)
            return streams or []
        except Exception as e:
            logger.error(f"Error fetching stream info for multiple users: {e}")
            return []

    async def get_multiple_user_info(self, twitch_ids: List[str]) -> List[Dict[str, Any]]:
        """Get user information for multiple Twitch IDs"""
        try:
            users = await self.twitch_api.get_users_by_id(twitch_ids)
            return users or []
        except Exception as e:
            logger.error(f"Error fetching user info for multiple users: {e}")
            return []

    async def subscribe_to_events(self, twitch_id: str):
        """Subscribe to EventSub events for a streamer"""
        try:
            await self.event_registry.subscribe_to_events(twitch_id)
            logger.info(f"Successfully subscribed to EventSub events for {twitch_id}")
        except Exception as e:
            logger.error(f"Failed to subscribe to EventSub events for {twitch_id}: {e}")
            raise

    async def unsubscribe_from_events(self, twitch_id: str):
        """Unsubscribe from EventSub events for a streamer"""
        try:
            await self.event_registry.unsubscribe_from_events(twitch_id)
            logger.info(f"Successfully unsubscribed from EventSub events for {twitch_id}")
        except Exception as e:
            logger.error(f"Failed to unsubscribe from EventSub events for {twitch_id}: {e}")
            raise

    async def get_categories(self, category_names: List[str] = None, category_ids: List[str] = None) -> List[Dict[str, Any]]:
        """Get category/game information from Twitch API"""
        try:
            if category_names:
                return await self.twitch_api.get_games_by_name(category_names)
            elif category_ids:
                return await self.twitch_api.get_games_by_id(category_ids)
            return []
        except Exception as e:
            logger.error(f"Error fetching categories: {e}")
            return []

    async def get_top_games(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get top games from Twitch API"""
        try:
            games = await self.twitch_api.get_top_games(first=limit)
            # Process box art URLs
            for game in games:
                box_art_url = game.get("box_art_url", "")
                if box_art_url:
                    game["box_art_url"] = box_art_url.replace("{width}", "285").replace("{height}", "380")
            return games
        except Exception as e:
            logger.error(f"Error fetching top games: {e}")
            return []

    async def search_categories(self, query: str) -> List[Dict[str, Any]]:
        """Search for categories/games by name"""
        try:
            games = await self.twitch_api.search_categories(query)
            # Process box art URLs
            for game in games:
                box_art_url = game.get("box_art_url", "")
                if box_art_url:
                    game["box_art_url"] = box_art_url.replace("{width}", "285").replace("{height}", "380")
            return games
        except Exception as e:
            logger.error(f"Error searching categories for '{query}': {e}")
            return []

    async def validate_streamer_exists(self, username: str) -> bool:
        """Validate that a streamer exists on Twitch"""
        try:
            user_data = await self.get_user_data(username)
            return user_data is not None
        except Exception as e:
            logger.error(f"Error validating streamer {username}: {e}")
            return False

    async def get_streamer_followers(self, twitch_id: str) -> Optional[int]:
        """Get follower count for a streamer (if available)"""
        try:
            # Note: Twitch API has limited follower data access
            # This might require special permissions or OAuth scopes
            # For now, return None as follower counts are restricted
            logger.debug(f"Follower count requested for {twitch_id}, but not available via current API")
            return None
        except Exception as e:
            logger.error(f"Error fetching follower count for {twitch_id}: {e}")
            return None

    async def check_stream_status_bulk(self, twitch_ids: List[str]) -> Dict[str, bool]:
        """Check live status for multiple streamers efficiently"""
        try:
            streams = await self.get_multiple_stream_info(twitch_ids)
            live_streamers = {stream['user_id'] for stream in streams}
            
            # Return dict mapping twitch_id to live status
            return {twitch_id: twitch_id in live_streamers for twitch_id in twitch_ids}
        except Exception as e:
            logger.error(f"Error checking bulk stream status: {e}")
            return {twitch_id: False for twitch_id in twitch_ids}

    async def refresh_user_data(self, twitch_id: str) -> Optional[Dict[str, Any]]:
        """Refresh user data from Twitch API (profile image, display name, etc.)"""
        try:
            return await self.get_streamer_info(twitch_id)
        except Exception as e:
            logger.error(f"Error refreshing user data for {twitch_id}: {e}")
            return None

    def get_twitch_profile_url(self, username: str) -> str:
        """Get Twitch profile URL for a username"""
        return f"https://twitch.tv/{username}"

    def get_twitch_video_url(self, video_id: str) -> str:
        """Get Twitch video URL for a video ID"""
        return f"https://twitch.tv/videos/{video_id}"
