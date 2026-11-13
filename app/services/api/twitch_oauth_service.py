"""
Twitch OAuth Service for StreamVault

Handles OAuth user authentication for importing followed channels.
This service is specifically for user authentication flows, NOT general API calls.
Use twitch_api.py for general Twitch API interactions.
"""

import asyncio
import json
import logging
from collections.abc import Coroutine
from itertools import count
from typing import TypeVar
from app.config.settings import Settings, get_settings
from app.services.http_client import HTTPClientError, HTTPPolicy, ManagedHTTPClient
from app.services.api.twitch_api import TwitchAPIService
from app.services.streamer_service import StreamerService
from app.services.system.supervisor import TaskSupervisor
from app.services.api.twitch_api import FOLLOW_FETCH_TIMEOUT, twitch_api

from urllib.parse import urlencode

logger = logging.getLogger("streamvault")
T = TypeVar("T")


class TwitchOAuthService:
    """Service for handling Twitch OAuth flows and follower imports"""

    def __init__(
        self,
        streamer_service: StreamerService | None = None,
        *,
        settings: Settings | None = None,
        twitch_api: TwitchAPIService | None = None,
        http_client: ManagedHTTPClient | None = None,
    ) -> None:
        self.streamer_service = streamer_service
        self.settings = settings if settings is not None else get_settings()
        self.client_id = self.settings.TWITCH_APP_ID
        self.client_secret = self.settings.TWITCH_APP_SECRET
        self.redirect_uri = f"{self.settings.BASE_URL}/api/twitch/callback"
        self._twitch_api = twitch_api
        self._supervisor = TaskSupervisor("twitch-oauth")
        self._operation_ids = count()
        self._close_task: asyncio.Task[None] | None = None
        self._owns_http = http_client is None
        self._http = (
            http_client
            if http_client is not None
            else ManagedHTTPClient(
                HTTPPolicy(
                    total_timeout=300.0,
                    connect_timeout=30.0,
                    read_timeout=300.0,
                    write_timeout=300.0,
                )
            )
        )

    async def _operation(self, name: str, work: Coroutine[object, object, T]) -> T:
        if self._close_task is not None:
            work.close()
            raise RuntimeError("Twitch OAuth service is closed")
        owned_name = f"{name}:{next(self._operation_ids)}"
        task = self._supervisor.create_task(owned_name, work)
        try:
            return await task
        finally:
            await self._supervisor.cancel_task(owned_name)

    async def close(self) -> None:
        if self._close_task is None:
            self._close_task = asyncio.create_task(
                self._close_resources(), name="streamvault:twitch-oauth:close"
            )
        cancelled = False
        while not self._close_task.done():
            try:
                await asyncio.shield(self._close_task)
            except asyncio.CancelledError:
                cancelled = True
        self._close_task.result()
        if cancelled:
            raise asyncio.CancelledError

    async def _close_resources(self) -> None:
        try:
            await self._supervisor.shutdown()
        finally:
            if self._owns_http:
                await self._http.close()

    def get_auth_url(self, state: str | None = None) -> str:
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

    async def exchange_code(self, code: str) -> dict[str, object] | None:
        """Exchange authorization code for access token without retrying the grant."""
        return await self._operation("exchange", self._exchange_code(code))

    async def _exchange_code(self, code: str) -> dict[str, object] | None:
        try:
            response = await self._http.request(
                "POST",
                "https://id.twitch.tv/oauth2/token",
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": self.redirect_uri,
                },
            )
            if response.status_code != 200:
                logger.warning(
                    "OAuth code exchange rejected: status=%s", response.status_code
                )
                return None
            value: object = json.loads(response.body)
            if (
                not isinstance(value, dict)
                or not isinstance(value.get("access_token"), str)
                or not value["access_token"]
            ):
                raise ValueError("Invalid OAuth exchange response")
            return value
        except (HTTPClientError, ValueError):
            logger.warning("OAuth code exchange failed")
            return None

    async def get_user_followed_channels(
        self, access_token: str
    ) -> list[dict[str, object]] | None:
        """Project the complete follow list; provider failures must reach the route."""
        return await self._operation(
            "follows", self._get_user_followed_channels(access_token)
        )

    async def _get_user_followed_channels(
        self, access_token: str
    ) -> list[dict[str, object]] | None:
        async with asyncio.timeout(FOLLOW_FETCH_TIMEOUT):
            user_id = await self._get_authenticated_user_id(access_token)
            if not user_id:
                return None
            follows = await (
                self._twitch_api or twitch_api
            ).get_user_followed_streamers(user_id, access_token)
            return [
                {
                    "id": follow["broadcaster_id"],
                    "login": follow["broadcaster_login"],
                    "display_name": follow.get("broadcaster_name"),
                    "followed_at": follow.get("followed_at"),
                }
                for follow in follows
            ]

    async def _get_authenticated_user_id(self, access_token: str) -> str | None:
        """Get the user ID of the authenticated user"""
        try:
            user_data = await (self._twitch_api or twitch_api).validate_token(
                access_token
            )
            if user_data:
                user_id = user_data.get("user_id")
                return user_id if isinstance(user_id, str) else None
            return None
        except Exception:
            logger.warning("Could not validate OAuth user identity")
            return None

    async def import_followed_streamers(
        self,
        streamers: list[dict[str, object]],
        *,
        streamer_service: StreamerService | None = None,
    ) -> dict[str, list[dict[str, object]]]:
        """Import selected streamers from followed channels"""
        service = (
            streamer_service if streamer_service is not None else self.streamer_service
        )
        if service is None:
            raise RuntimeError("Streamer importer is required")
        results: dict[str, list[dict[str, object]]] = {
            "imported": [],
            "failed": [],
            "already_exists": [],
        }

        for streamer_info in streamers:
            try:
                username = streamer_info.get("login") or streamer_info.get(
                    "display_name"
                )
                display_name = streamer_info.get("display_name") or streamer_info.get(
                    "login"
                )

                if not isinstance(username, str) or not username:
                    logger.warning("Skipping streamer with missing username")
                    results["failed"].append(
                        {"streamer": streamer_info, "reason": "Missing username"}
                    )
                    continue

                # Use StreamerService to add the streamer
                added_streamer = await service.add_streamer(
                    username,
                    display_name if isinstance(display_name, str) else username,
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

            except Exception:
                logger.warning("Could not import selected streamer")
                results["failed"].append(
                    {"streamer": streamer_info, "reason": "Failed to add streamer"}
                )

        logger.info(
            f"Import complete: {len(results['imported'])} imported, {len(results['already_exists'])} already existed, {len(results['failed'])} failed"
        )
        return results
