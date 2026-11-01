"""
Twitch API Service for StreamVault

Centralized service for making Twitch API calls. Provides methods for getting
user information, game data, category information, and other Twitch API interactions.
"""

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from contextvars import ContextVar
from functools import wraps
from time import monotonic

from typing import Optional, List
from app.config.settings import Settings, settings as default_settings
from app.services.http_client import (
    HTTPClientError,
    HTTPPolicy,
    HTTPReply,
    ManagedHTTPClient,
)
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

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        http_client: ManagedHTTPClient | None = None,
    ):
        configuration = settings if settings is not None else default_settings
        self.client_id = configuration.TWITCH_APP_ID
        self.client_secret = configuration.TWITCH_APP_SECRET
        self.base_url = "https://api.twitch.tv/helix"
        self._http_client = (
            http_client if http_client is not None else ManagedHTTPClient(HTTPPolicy())
        )
        self._closed = False
        self._close_task: asyncio.Task[None] | None = None
        self._access_token: str | None = None
        self._token_expires_at = 0.0
        self._token_refresh: asyncio.Task[str] | None = None
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
        if self._closed:
            raise NonRetryableError("Twitch HTTP client is closed")
        if self._access_token and monotonic() < self._token_expires_at:
            return self._access_token
        if self._token_refresh is None or self._token_refresh.done():
            self._token_refresh = asyncio.create_task(
                self._fetch_access_token(), name="streamvault:twitch-token-refresh"
            )
        return await asyncio.shield(self._token_refresh)

    async def _close_resources(self) -> None:
        if self._token_refresh is not None and not self._token_refresh.done():
            self._token_refresh.cancel()
        try:
            if self._token_refresh is not None:
                await asyncio.gather(self._token_refresh, return_exceptions=True)
        finally:
            await self._http_client.close()

    async def close(self) -> None:
        self._closed = True
        if self._close_task is None:
            self._close_task = asyncio.create_task(
                self._close_resources(), name="streamvault:twitch-client-close"
            )
        try:
            await asyncio.shield(self._close_task)
        except asyncio.CancelledError:
            while not self._close_task.done():
                try:
                    await asyncio.shield(self._close_task)
                except asyncio.CancelledError:
                    continue
                except Exception:
                    break
            if not self._close_task.cancelled():
                self._close_task.exception()
            raise

    async def _request(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, str | Sequence[str]] | None = None,
        data: Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
        json_body: Mapping[str, object] | None = None,
    ) -> HTTPReply:
        if self._closed:
            raise NonRetryableError("Twitch HTTP client is closed")
        try:
            return await self._http_client.request(
                method, url, params=params, data=data, headers=headers, json=json_body
            )
        except HTTPClientError as error:
            if error.code == "status" and error.status_code is not None:
                # Endpoint adapters retain their existing fallback/auth/retry policy.
                return HTTPReply(error.status_code, {}, b"")
            if error.code in {"timeout", "network"}:
                raise ConnectionError(
                    f"Twitch HTTP request failed: {error.code}"
                ) from None
            raise NonRetryableError(
                f"Twitch HTTP request failed: {error.code}"
            ) from None

    async def _eventsub_request(
        self,
        method: str,
        *,
        subscription_id: str | None = None,
        payload: Mapping[str, object] | None = None,
    ) -> HTTPReply:
        token = await self.get_access_token()
        return await self._request(
            method,
            f"{self.base_url}/eventsub/subscriptions",
            params={"id": subscription_id} if subscription_id is not None else None,
            json_body=payload,
            headers={"Client-ID": self.client_id, "Authorization": f"Bearer {token}"},
        )

    async def list_eventsub_subscriptions(self) -> dict[str, object]:
        response = await self._eventsub_request("GET")
        return self._json(response) if response.status_code == 200 else {"data": []}

    async def create_eventsub_subscription(self, payload: Mapping[str, object]) -> int:
        response = await self._eventsub_request("POST", payload=payload)
        return response.status_code

    async def delete_eventsub_subscription(self, subscription_id: str) -> int:
        response = await self._eventsub_request(
            "DELETE", subscription_id=subscription_id
        )
        return response.status_code

    @staticmethod
    def _json(response: HTTPReply) -> dict[str, object]:
        try:
            value: object = json.loads(response.body)
        except (ValueError, UnicodeError):
            raise NonRetryableError("Invalid Twitch JSON response") from None
        if not isinstance(value, dict):
            raise NonRetryableError("Invalid Twitch JSON response")
        return value

    @classmethod
    def _data(cls, response: HTTPReply) -> list[dict[str, object]]:
        values = cls._json(response).get("data", [])
        if not isinstance(values, list):
            raise NonRetryableError("Invalid Twitch data response")
        result: list[dict[str, object]] = []
        for item in values:
            if not isinstance(item, dict):
                raise NonRetryableError("Invalid Twitch data response")
            result.append(item)
        return result

    @twitch_api_retry
    async def _fetch_access_token(self) -> str:
        if not self.client_id or not self.client_secret:
            raise NonRetryableError("Twitch app credentials are not configured")
        response = await self._request(
            "POST",
            "https://id.twitch.tv/oauth2/token",
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "client_credentials",
            },
        )
        if response.status_code == 200:
            data = self._json(response)
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
            self._token_expires_at = monotonic() + expires_in - min(60, expires_in / 10)
            logger.debug("Successfully obtained Twitch access token")
            return token
        if response.status_code in [400, 401, 403]:
            raise NonRetryableError(f"Authentication failed: {response.status_code}")
        raise ConnectionError(f"Failed to get access token: {response.status_code}")

    @asynccontextmanager
    async def _app_get(
        self, url: str, params: Mapping[str, str | Sequence[str]]
    ) -> AsyncIterator[HTTPReply]:
        token = await self.get_access_token()
        for _ in range(2):
            response = await self._request(
                "GET",
                url,
                params=params,
                headers={
                    "Client-ID": self.client_id,
                    "Authorization": f"Bearer {token}",
                },
            )
            if response.status_code != 401 or self._app_replay_used.get():
                if response.status_code == 401:
                    self._invalidate_token(token)
                yield response
                return
            self._app_replay_used.set(True)
            self._invalidate_token(token)
            token = await self.get_access_token()

    @_app_operation
    @twitch_api_retry
    async def get_users_by_login(self, usernames: List[str]) -> List[dict[str, object]]:
        """Get user data by username(s)"""
        if not usernames:
            return []

        async with self._app_get(
            f"{self.base_url}/users",
            params={"login": usernames},
        ) as response:
            if response.status_code == 200:
                return self._data(response)
            elif response.status_code in [401, 403, 404]:
                # Client errors should not be retried
                logger.error(
                    f"Failed to get users by login. Status: {response.status_code}"
                )
                raise NonRetryableError(f"Client error: {response.status_code}")
            else:
                # Server errors can be retried
                logger.error(
                    f"Failed to get users by login. Status: {response.status_code}"
                )
                raise ConnectionError(f"Server error: {response.status_code}")

    @_app_operation
    @twitch_api_retry
    async def get_users_by_id(self, user_ids: List[str]) -> List[dict[str, object]]:
        """Get user data by user ID(s)"""
        if not user_ids:
            return []

        async with self._app_get(
            f"{self.base_url}/users",
            params={"id": user_ids},
        ) as response:
            if response.status_code == 200:
                return self._data(response)
            elif response.status_code in [401, 403, 404]:
                logger.error(
                    f"Failed to get users by ID. Status: {response.status_code}"
                )
                raise NonRetryableError(f"Client error: {response.status_code}")
            else:
                logger.error(
                    f"Failed to get users by ID. Status: {response.status_code}"
                )
                raise ConnectionError(f"Server error: {response.status_code}")

    @_app_operation
    @twitch_api_retry
    async def get_games_by_name(self, game_names: List[str]) -> List[dict[str, object]]:
        """Get game/category data by name(s)"""
        if not game_names:
            return []

        async with self._app_get(
            f"{self.base_url}/games",
            params={"name": game_names},
        ) as response:
            if response.status_code == 200:
                return self._data(response)
            elif response.status_code in [401, 403, 404]:
                logger.error(
                    f"Failed to get games by name. Status: {response.status_code}"
                )
                raise NonRetryableError(f"Client error: {response.status_code}")
            else:
                logger.error(
                    f"Failed to get games by name. Status: {response.status_code}"
                )
                raise ConnectionError(f"Server error: {response.status_code}")

    @_app_operation
    async def get_games_by_id(self, game_ids: List[str]) -> List[dict[str, object]]:
        """Get game/category data by ID(s)"""
        if not game_ids:
            return []

        async with self._app_get(
            f"{self.base_url}/games",
            params={"id": game_ids},
        ) as response:
            if response.status_code == 200:
                return self._data(response)
            else:
                logger.error(
                    f"Failed to get games by ID. Status: {response.status_code}"
                )
                return []

    @_app_operation
    @twitch_api_retry
    async def get_streams(
        self,
        user_ids: list[str] | None = None,
        user_logins: list[str] | None = None,
        game_ids: list[str] | None = None,
    ) -> List[dict[str, object]]:
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
            if response.status_code == 200:
                return self._data(response)
            elif response.status_code in [401, 403, 404]:
                logger.error(f"Failed to get streams. Status: {response.status_code}")
                raise NonRetryableError(f"Client error: {response.status_code}")
            else:
                logger.error(f"Failed to get streams. Status: {response.status_code}")
                raise ConnectionError(f"Server error: {response.status_code}")

    @_app_operation
    async def search_categories(self, query: str) -> List[dict[str, object]]:
        """Search for games/categories"""
        if not query:
            return []

        async with self._app_get(
            f"{self.base_url}/search/categories",
            params={"query": query},
        ) as response:
            if response.status_code == 200:
                return self._data(response)
            else:
                logger.error(
                    f"Failed to search categories. Status: {response.status_code}"
                )
                return []

    @_app_operation
    async def get_top_games(self, first: int = 20) -> List[dict[str, object]]:
        """Get top games on Twitch"""
        async with self._app_get(
            f"{self.base_url}/games/top",
            params={"first": str(first)},
        ) as response:
            if response.status_code == 200:
                return self._data(response)
            else:
                logger.error(f"Failed to get top games. Status: {response.status_code}")
                return []

    async def get_user_followed_streamers(
        self, user_id: str, access_token: str
    ) -> List[dict[str, object]]:
        """Get followed streamers for a user (requires user access token)"""
        response = await self._request(
            "GET",
            f"{self.base_url}/channels/followed",
            params={"user_id": user_id},
            headers={
                "Client-ID": self.client_id,
                "Authorization": f"Bearer {access_token}",
            },
        )
        if response.status_code == 200:
            return self._data(response)
        logger.error(
            f"Failed to get followed streamers. Status: {response.status_code}"
        )
        return []

    @twitch_api_retry
    async def validate_token(self, access_token: str) -> Optional[dict[str, object]]:
        """Validate an access token and get user info"""
        response = await self._request(
            "GET",
            "https://id.twitch.tv/oauth2/validate",
            headers={"Authorization": f"OAuth {access_token}"},
        )
        if response.status_code == 200:
            return self._json(response)
        logger.error(f"Failed to validate token. Status: {response.status_code}")
        if response.status_code in [401, 403]:
            raise NonRetryableError(f"Token validation failed: {response.status_code}")
        raise ConnectionError(f"Token validation error: {response.status_code}")

    @_app_operation
    @twitch_api_retry
    async def get_stream_by_user_id(self, user_id: str) -> Optional[dict[str, object]]:
        """Get single stream data by user ID"""
        if not user_id:
            return None

        streams = await self.get_streams(user_ids=[user_id])
        return streams[0] if streams else None


# Global instance
twitch_api = TwitchAPIService()
