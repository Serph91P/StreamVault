"""
Twitch API Service for StreamVault

Centralized service for making Twitch API calls. Provides methods for getting
user information, game data, category information, and other Twitch API interactions.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from contextvars import ContextVar
from functools import wraps
from time import monotonic

import aiohttp
from typing import Dict, Any, Optional, List
from app.config.settings import settings
from app.utils.retry_decorator import twitch_api_retry, NonRetryableError

logger = logging.getLogger("streamvault")


def _app_operation(func):
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        if self._app_replay_used.get() is not None:
            return await func(self, *args, **kwargs)
        # Scope the auth budget outside all transient retries, including nested calls.
        scope = self._app_replay_used.set(False)
        try:
            return await func(self, *args, **kwargs)
        finally:
            self._app_replay_used.reset(scope)

    return wrapper


class TwitchAPIService:
    """Centralized Twitch API service"""

    def __init__(self):
        self.client_id = settings.TWITCH_APP_ID
        self.client_secret = settings.TWITCH_APP_SECRET
        self.base_url = "https://api.twitch.tv/helix"
        self._access_token = None
        self._token_expires_at = 0.0
        self._token_refresh = None
        self._app_replay_used: ContextVar[Optional[bool]] = ContextVar(
            "app_replay_used", default=None
        )

    def _invalidate_token(self, rejected_token: str) -> None:
        # A late 401 must not invalidate another caller's replacement token.
        if self._access_token == rejected_token:
            self._access_token = None
            self._token_expires_at = 0.0

    async def get_access_token(self) -> str:
        """Reuse a valid app token, sharing in-flight refreshes and their failures."""
        if self._access_token and monotonic() < self._token_expires_at:
            return self._access_token
        if self._token_refresh is None or self._token_refresh.done():
            self._token_refresh = asyncio.create_task(self._fetch_access_token())
        return await asyncio.shield(self._token_refresh)

    @twitch_api_retry
    async def _fetch_access_token(self) -> str:
        if not self.client_id or not self.client_secret:
            raise NonRetryableError("Twitch app credentials are not configured")
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://id.twitch.tv/oauth2/token",
                params={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "client_credentials",
                },
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    if not isinstance(data, dict):
                        raise NonRetryableError("Invalid Twitch app token response")
                    token = data.get("access_token")
                    expires_in = data.get("expires_in")
                    if (
                        not isinstance(token, str)
                        or not token
                        or not isinstance(expires_in, int)
                        or isinstance(expires_in, bool)
                        or expires_in <= 0
                    ):
                        raise NonRetryableError("Invalid Twitch app token response")
                    self._access_token = token
                    self._token_expires_at = (
                        monotonic() + expires_in - min(60, expires_in / 10)
                    )
                    logger.debug("Successfully obtained Twitch access token")
                    return token
                if response.status in [400, 401, 403]:
                    raise NonRetryableError(f"Authentication failed: {response.status}")
                raise ConnectionError(f"Failed to get access token: {response.status}")

    @asynccontextmanager
    async def _app_get(self, url: str, params: Dict[str, Any]):
        token = await self.get_access_token()
        async with aiohttp.ClientSession() as session:
            for _ in range(2):
                async with session.get(
                    url,
                    params=params,
                    headers={
                        "Client-ID": self.client_id,
                        "Authorization": f"Bearer {token}",
                    },
                ) as response:
                    if response.status != 401 or self._app_replay_used.get():
                        if response.status == 401:
                            self._invalidate_token(token)
                        yield response
                        return
                    self._app_replay_used.set(True)
                    self._invalidate_token(token)
                token = await self.get_access_token()

    @_app_operation
    @twitch_api_retry
    async def get_users_by_login(self, usernames: List[str]) -> List[Dict[str, Any]]:
        """Get user data by username(s)"""
        if not usernames:
            return []

        async with self._app_get(
            f"{self.base_url}/users",
            params={"login": usernames},
        ) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("data", [])
            elif response.status in [401, 403, 404]:
                # Client errors should not be retried
                logger.error(f"Failed to get users by login. Status: {response.status}")
                raise NonRetryableError(f"Client error: {response.status}")
            else:
                # Server errors can be retried
                logger.error(f"Failed to get users by login. Status: {response.status}")
                raise ConnectionError(f"Server error: {response.status}")

    @_app_operation
    @twitch_api_retry
    async def get_users_by_id(self, user_ids: List[str]) -> List[Dict[str, Any]]:
        """Get user data by user ID(s)"""
        if not user_ids:
            return []

        async with self._app_get(
            f"{self.base_url}/users",
            params={"id": user_ids},
        ) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("data", [])
            elif response.status in [401, 403, 404]:
                logger.error(f"Failed to get users by ID. Status: {response.status}")
                raise NonRetryableError(f"Client error: {response.status}")
            else:
                logger.error(f"Failed to get users by ID. Status: {response.status}")
                raise ConnectionError(f"Server error: {response.status}")

    @_app_operation
    @twitch_api_retry
    async def get_games_by_name(self, game_names: List[str]) -> List[Dict[str, Any]]:
        """Get game/category data by name(s)"""
        if not game_names:
            return []

        async with self._app_get(
            f"{self.base_url}/games",
            params={"name": game_names},
        ) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("data", [])
            elif response.status in [401, 403, 404]:
                logger.error(f"Failed to get games by name. Status: {response.status}")
                raise NonRetryableError(f"Client error: {response.status}")
            else:
                logger.error(f"Failed to get games by name. Status: {response.status}")
                raise ConnectionError(f"Server error: {response.status}")

    @_app_operation
    async def get_games_by_id(self, game_ids: List[str]) -> List[Dict[str, Any]]:
        """Get game/category data by ID(s)"""
        if not game_ids:
            return []

        async with self._app_get(
            f"{self.base_url}/games",
            params={"id": game_ids},
        ) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("data", [])
            else:
                logger.error(f"Failed to get games by ID. Status: {response.status}")
                return []

    @_app_operation
    @twitch_api_retry
    async def get_streams(
        self,
        user_ids: List[str] = None,
        user_logins: List[str] = None,
        game_ids: List[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get stream data"""
        params = {}
        if user_ids:
            params["user_id"] = user_ids
        if user_logins:
            params["user_login"] = user_logins
        if game_ids:
            params["game_id"] = game_ids

        async with self._app_get(
            f"{self.base_url}/streams",
            params=params,
        ) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("data", [])
            elif response.status in [401, 403, 404]:
                logger.error(f"Failed to get streams. Status: {response.status}")
                raise NonRetryableError(f"Client error: {response.status}")
            else:
                logger.error(f"Failed to get streams. Status: {response.status}")
                raise ConnectionError(f"Server error: {response.status}")

    @_app_operation
    async def search_categories(self, query: str) -> List[Dict[str, Any]]:
        """Search for games/categories"""
        if not query:
            return []

        async with self._app_get(
            f"{self.base_url}/search/categories",
            params={"query": query},
        ) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("data", [])
            else:
                logger.error(f"Failed to search categories. Status: {response.status}")
                return []

    @_app_operation
    async def get_top_games(self, first: int = 20) -> List[Dict[str, Any]]:
        """Get top games on Twitch"""
        async with self._app_get(
            f"{self.base_url}/games/top",
            params={"first": first},
        ) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("data", [])
            else:
                logger.error(f"Failed to get top games. Status: {response.status}")
                return []

    async def get_user_followed_streamers(
        self, user_id: str, access_token: str
    ) -> List[Dict[str, Any]]:
        """Get followed streamers for a user (requires user access token)"""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/channels/followed",
                params={"user_id": user_id},
                headers={
                    "Client-ID": self.client_id,
                    "Authorization": f"Bearer {access_token}",
                },
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("data", [])
                else:
                    logger.error(
                        f"Failed to get followed streamers. Status: {response.status}"
                    )
                    return []

    @twitch_api_retry
    async def validate_token(self, access_token: str) -> Optional[Dict[str, Any]]:
        """Validate an access token and get user info"""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://id.twitch.tv/oauth2/validate",
                headers={"Authorization": f"OAuth {access_token}"},
            ) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status in [401, 403]:
                    logger.error(f"Failed to validate token. Status: {response.status}")
                    raise NonRetryableError(
                        f"Token validation failed: {response.status}"
                    )
                else:
                    logger.error(f"Failed to validate token. Status: {response.status}")
                    raise ConnectionError(f"Token validation error: {response.status}")

    @_app_operation
    @twitch_api_retry
    async def get_stream_by_user_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get single stream data by user ID"""
        if not user_id:
            return None

        streams = await self.get_streams(user_ids=[user_id])
        return streams[0] if streams else None


# Global instance
twitch_api = TwitchAPIService()
