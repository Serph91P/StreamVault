"""
Twitch OAuth Service for StreamVault

Handles OAuth user authentication for importing followed channels.
This service is specifically for user authentication flows, NOT general API calls.
Use twitch_api.py for general Twitch API interactions.
"""

import asyncio
import logging
import aiohttp
from app.config.settings import settings
from app.services.streamer_service import StreamerService
from app.services.api.twitch_api import FOLLOW_FETCH_TIMEOUT, twitch_api
from typing import Dict, List, Any, Optional
from urllib.parse import urlencode

logger = logging.getLogger("streamvault")


class TwitchOAuthService:
    """Service for handling Twitch OAuth flows and follower imports"""

    def __init__(self, streamer_service: StreamerService):
        self.streamer_service = streamer_service
        self.client_id = settings.TWITCH_APP_ID
        self.client_secret = settings.TWITCH_APP_SECRET
        self.redirect_uri = f"{settings.BASE_URL}/api/twitch/callback"

    def get_auth_url(self, state: Optional[str] = None) -> str:
        """Generate Twitch OAuth URL for user authentication

        Args:
            state: Optional state parameter (e.g., return URL like '/settings' or '/add-streamer')
        """
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "user:read:follows",  # Required for reading followed channels
            "force_verify": "true",  # Force re-authentication to ensure fresh refresh_token
        }

        if state:
            params["state"] = state

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
                        "redirect_uri": self.redirect_uri,
                    },
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        error_text = await response.text()
                        logger.error(
                            f"Failed to exchange code: {response.status} - {error_text}"
                        )
                        return None
        except Exception as e:
            logger.error(f"Error exchanging code: {e}")
            return None

    async def get_user_followed_channels(
        self, access_token: str
    ) -> Optional[List[Dict[str, Any]]]:
        """Project the complete follow list; provider failures must reach the route."""
        async with asyncio.timeout(FOLLOW_FETCH_TIMEOUT):
            user_id = await self._get_authenticated_user_id(access_token)
            if not user_id:
                return None
            follows = await twitch_api.get_user_followed_streamers(
                user_id, access_token
            )
            return [
                {
                    "id": follow["broadcaster_id"],
                    "login": follow["broadcaster_login"],
                    "display_name": follow.get("broadcaster_name"),
                    "followed_at": follow.get("followed_at"),
                }
                for follow in follows
            ]

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

    async def import_followed_streamers(
        self, streamers: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Import selected streamers from followed channels"""
        results = {"imported": [], "failed": [], "already_exists": []}

        for streamer_info in streamers:
            try:
                username = streamer_info.get("login") or streamer_info.get(
                    "display_name"
                )
                display_name = streamer_info.get("display_name") or streamer_info.get(
                    "login"
                )

                if not username:
                    logger.warning(
                        f"Skipping streamer with missing username: {streamer_info}"
                    )
                    results["failed"].append(
                        {"streamer": streamer_info, "reason": "Missing username"}
                    )
                    continue

                # Use StreamerService to add the streamer
                added_streamer = await self.streamer_service.add_streamer(
                    username, display_name
                )

                if added_streamer:
                    if added_streamer.id:  # New streamer added
                        results["imported"].append(
                            {
                                "username": username,
                                "display_name": display_name,
                                "id": added_streamer.id,
                            }
                        )
                        logger.info(f"Successfully imported streamer: {username}")
                    else:  # Streamer already exists
                        results["already_exists"].append(
                            {"username": username, "display_name": display_name}
                        )
                        logger.debug(f"Streamer already exists: {username}")
                else:
                    results["failed"].append(
                        {"streamer": streamer_info, "reason": "Failed to add streamer"}
                    )
                    logger.error(f"Failed to import streamer: {username}")

            except Exception as e:
                logger.error(f"Error importing streamer {streamer_info}: {e}")
                results["failed"].append({"streamer": streamer_info, "reason": str(e)})

        logger.info(
            f"Import complete: {len(results['imported'])} imported, {len(results['already_exists'])} already existed, {len(results['failed'])} failed"
        )
        return results
