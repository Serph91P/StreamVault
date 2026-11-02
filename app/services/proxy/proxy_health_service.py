"""
Proxy Health Check Service

CRITICAL: This service prevents recording failures when proxies go down.
It automatically monitors proxy health, selects the best available proxy,
and provides graceful fallback to direct connection when all proxies fail.

Architecture:
- Background task runs health checks every 5 minutes (configurable)
- Tests connectivity with Twitch API endpoint (fast, reliable)
- Measures response time in milliseconds
- Auto-disables proxies after 3 consecutive failures (configurable)
- Broadcasts status updates via WebSocket to frontend

Proxy Selection Algorithm:
1. Filter: Only enabled=TRUE proxies from database
2. Prioritize: healthy > degraded > failed (by health_status)
3. Sort: By priority field (ascending, 0 = highest)
4. Sort: By average_response_time_ms (ascending, faster = better)
5. Return: First match or None
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import logging
from typing import Optional, Dict, Any, TYPE_CHECKING
from datetime import datetime, timezone

import aiohttp

from app.config.constants import ASYNC_DELAYS
from app.config.settings import settings
from app.database import SessionLocal
from app.models import ProxySettings
from app.services.proxy import proxy_catalog
from app.services.proxy.proxy_catalog import ProxySnapshot, ProxyPolicy, HealthResult
from app.utils.async_db_utils import run_in_thread_pool
from app.utils.security import sanitize_proxy_url_for_logging

logger = logging.getLogger("streamvault")

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from app.config.settings import Settings
    from app.services.communication.websocket_manager import ConnectionManager


class ProxyHealthService:
    """
    Service for monitoring proxy health and selecting best available proxy.

    This is a singleton service that runs a background task for periodic health checks.
    """

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session] | None = None,
        settings: Settings | None = None,
        websocket_manager: ConnectionManager | None = None,
    ):
        self._session_factory = session_factory
        self._settings = settings
        self._websocket_manager = websocket_manager
        self._background_task: Optional[asyncio.Task] = None
        self._running = False
        self._lock = asyncio.Lock()

        # Test endpoint - Twitch API streams endpoint (requires auth, most realistic test)
        # This tests the actual endpoint used for recording, ensuring proxy works for Streamlink
        self.test_endpoint = "https://api.twitch.tv/helix/streams"

        logger.info("🔧 ProxyHealthService initialized")

    async def start(self):
        """Start the background health check task"""
        if self._running:
            logger.warning("⚠️ ProxyHealthService already running")
            return

        self._running = True
        self._background_task = asyncio.create_task(self._run_health_checks_loop())
        logger.info("✅ ProxyHealthService background task started")

    async def stop(self):
        """Stop the background health check task gracefully"""
        if not self._running:
            return

        self._running = False

        if self._background_task:
            self._background_task.cancel()
            try:
                await self._background_task
            except asyncio.CancelledError:
                pass

        logger.info("✅ ProxyHealthService stopped")

    async def _run_health_checks_loop(self):
        """
        Background task that runs health checks periodically.

        This runs continuously in the background, checking all enabled proxies
        and updating their health status in the database.
        """
        logger.info("🏥 ProxyHealthService: Starting periodic health checks")

        while self._running:
            try:
                # Get check interval from database settings
                interval_seconds = await self._get_check_interval()

                # Check if health checks are enabled
                checks_enabled = await self._are_checks_enabled()

                if checks_enabled:
                    await self.run_health_checks()
                else:
                    logger.debug("⏸️ Proxy health checks disabled in settings")

                # Wait for next check interval
                await asyncio.sleep(interval_seconds)

            except asyncio.CancelledError:
                logger.info("🛑 Health check loop cancelled")
                break
            except Exception:
                logger.error("🚨 Error in health check loop")
                # Wait before retrying to avoid tight error loop
                await asyncio.sleep(ASYNC_DELAYS.PROXY_HEALTH_CHECK_ERROR_WAIT)

    async def _get_policy(self) -> ProxyPolicy:
        try:
            return await run_in_thread_pool(
                proxy_catalog.read_policy, self._session_factory or SessionLocal
            )
        except Exception:
            logger.error("Error reading proxy health policy")
            return ProxyPolicy()

    async def _get_check_interval(self) -> int:
        return (await self._get_policy()).interval_seconds

    async def _are_checks_enabled(self) -> bool:
        return (await self._get_policy()).enabled

    async def run_health_checks(self):
        """
        Run health checks on all enabled proxies and update database.

        This method is called by the background task periodically, but can also
        be called manually (e.g., from API endpoint for manual health check).
        """
        async with self._lock:
            factory = self._session_factory or SessionLocal
            targets = await run_in_thread_pool(proxy_catalog.read_targets, factory)
            if not targets:
                return
            access_token = await self._get_twitch_access_token()
            if not access_token:
                logger.error("Proxy health checks skipped: Twitch token unavailable")
                return
            for target in targets:
                try:
                    result = await self._check_proxy_health(target.url, access_token)
                    maximum = await self._get_max_failures()
                    published = await run_in_thread_pool(
                        proxy_catalog.apply_health,
                        factory,
                        target,
                        result,
                        max_failures=maximum,
                    )
                    if published is not None:
                        snapshot, disabled = published
                        level = (
                            logging.ERROR
                            if disabled
                            else logging.WARNING
                            if result["status"] == "failed"
                            else logging.INFO
                        )
                        logger.log(
                            level,
                            "Proxy health: id=%s status=%s failures=%s disabled=%s",
                            snapshot.id,
                            snapshot.health_status,
                            snapshot.consecutive_failures,
                            disabled,
                        )
                        await self._broadcast_proxy_status(
                            snapshot, auto_disabled=disabled
                        )
                except Exception:
                    logger.error("Error checking proxy %s", target.id)

    async def _get_max_failures(self) -> int:
        return (await self._get_policy()).max_failures

    async def _get_twitch_access_token(self) -> Optional[str]:
        """Fetch one ephemeral Twitch app token for a health-check operation."""
        try:
            async with aiohttp.ClientSession() as token_session:
                async with token_session.post(
                    "https://id.twitch.tv/oauth2/token",
                    params={
                        "client_id": settings.TWITCH_APP_ID,
                        "client_secret": settings.TWITCH_APP_SECRET,
                        "grant_type": "client_credentials",
                    },
                ) as token_response:
                    if token_response.status != 200:
                        logger.error(
                            "Failed to get Twitch access token for proxy health check "
                            f"(HTTP {token_response.status})"
                        )
                        return None

                    token_data = await token_response.json()
                    access_token = token_data.get("access_token")
                    if not isinstance(access_token, str) or not access_token:
                        logger.error(
                            "Twitch token response for proxy health check was invalid"
                        )
                        return None
                    return access_token
        except asyncio.CancelledError:
            logger.error("Twitch token request for proxy health check was cancelled")
            raise
        except Exception:
            logger.error("Error getting access token for proxy health check")
            return None

    async def _check_proxy_health(
        self, proxy_url: str, access_token: str
    ) -> HealthResult:
        """
        Check health of a single proxy by testing connectivity with Twitch API.

        Uses authenticated Twitch API request to test the actual endpoint used for
        recordings.
        This ensures the proxy works for Streamlink, not just general web traffic.

        Args:
            proxy_url: Full proxy URL (http://user:pass@host:port)

        Returns:
            Dictionary with health check results:
            {
                'status': 'healthy' | 'degraded' | 'failed',
                'response_time_ms': int or None,
                'error': str or None
            }
        """
        timeout = aiohttp.ClientTimeout(total=10.0, connect=5.0)

        try:
            start_time = asyncio.get_event_loop().time()

            # Create proxy connector for aiohttp
            connector = aiohttp.TCPConnector()

            async with aiohttp.ClientSession(
                connector=connector, timeout=timeout
            ) as client:
                # Test with Twitch API streams endpoint (authenticated)
                async with client.get(
                    self.test_endpoint,
                    headers={
                        "Client-ID": settings.TWITCH_APP_ID,
                        "Authorization": f"Bearer {access_token}",
                    },
                    proxy=proxy_url,  # Use proxy for this request
                    allow_redirects=False,
                ) as response:
                    end_time = asyncio.get_event_loop().time()
                    response_time_ms = int((end_time - start_time) * 1000)

                    # Categorize status based on HTTP status code and response time
                    if response.status == 200:
                        # Healthy if fast response
                        if response_time_ms < 2000:  # < 2s
                            return {
                                "status": "healthy",
                                "response_time_ms": response_time_ms,
                                "error": None,
                            }
                        else:
                            # Slow but working
                            return {
                                "status": "degraded",
                                "response_time_ms": response_time_ms,
                                "error": f"Slow response ({response_time_ms}ms)",
                            }
                    elif response.status in (301, 302, 303, 307, 308):
                        # Redirects are OK (proxy works)
                        return {
                            "status": "healthy",
                            "response_time_ms": response_time_ms,
                            "error": None,
                        }
                    elif 400 <= response.status < 500:
                        # 4xx = proxy works but might have auth issues
                        # Check if it's specifically auth (401/403) which might be token issue
                        if response.status in (401, 403):
                            logger.warning(
                                f"Proxy health check got HTTP {response.status}"
                            )
                            return {
                                "status": "degraded",
                                "response_time_ms": response_time_ms,
                                "error": f"Auth issue (HTTP {response.status})",
                            }
                        else:
                            return {
                                "status": "degraded",
                                "response_time_ms": response_time_ms,
                                "error": f"HTTP {response.status}",
                            }
                    else:
                        # 5xx = proxy or upstream error (failed)
                        return {
                            "status": "failed",
                            "response_time_ms": response_time_ms,
                            "error": f"HTTP {response.status}",
                        }

        except asyncio.TimeoutError:
            return {
                "status": "failed",
                "response_time_ms": None,
                "error": "Timeout after 10 seconds",
            }

        except asyncio.CancelledError:
            logger.warning("Proxy health request was cancelled")
            raise

        except aiohttp.ClientProxyConnectionError:
            logger.error("Proxy connection error during health check")
            return {
                "status": "failed",
                "response_time_ms": None,
                "error": "Proxy connection failed",
            }

        except aiohttp.ClientError:
            logger.error("Client error during proxy health check")
            return {
                "status": "failed",
                "response_time_ms": None,
                "error": "Connection error",
            }

        except Exception:
            logger.error("Unexpected error checking proxy health")
            return {
                "status": "failed",
                "response_time_ms": None,
                "error": "Unexpected error during proxy health check",
            }

    async def check_proxy_health_manual(self, proxy_id: int) -> Dict[str, Any]:
        """
        Manually trigger health check for a specific proxy.

        This is called from API endpoints for manual testing.

        Args:
            proxy_id: Database ID of proxy to check

        Returns:
            Health check result dictionary
        """
        async with self._lock:
            factory = self._session_factory or SessionLocal
            target = await run_in_thread_pool(
                proxy_catalog.read_target, factory, proxy_id
            )
            if target is None:
                return {"error": "Proxy not found"}
            access_token = await self._get_twitch_access_token()
            result: HealthResult
            if access_token:
                result = await self._check_proxy_health(target.url, access_token)
            else:
                result = {
                    "status": "failed",
                    "response_time_ms": None,
                    "error": "Health check unavailable",
                }
            published = await run_in_thread_pool(
                proxy_catalog.apply_health, factory, target, result, max_failures=None
            )
            if published is None:
                return {"error": "Proxy changed during health check"}
            snapshot, _ = published
            logger.info(
                "Manual proxy health: id=%s status=%s",
                snapshot.id,
                snapshot.health_status,
            )
            await self._broadcast_proxy_status(snapshot, auto_disabled=False)
            return {
                "proxy_id": snapshot.id,
                "health_status": snapshot.health_status,
                "response_time_ms": snapshot.response_time_ms,
                "consecutive_failures": snapshot.consecutive_failures,
                "enabled": snapshot.enabled,
                "error": result["error"],
            }

    async def get_best_proxy(self) -> Optional[str]:
        """
        Get the best available proxy URL for recording.

        Selection Algorithm:
        1. Filter: Only enabled=TRUE proxies
        2. Prioritize: healthy > degraded > failed
        3. Sort: By priority field (0 = highest)
        4. Sort: By response_time_ms (faster = better)
        5. Return: First match or None

        Returns:
            Proxy URL string or None if no healthy proxies available
        """
        targets = await run_in_thread_pool(
            proxy_catalog.read_targets, self._session_factory or SessionLocal
        )
        if not targets:
            return None
        order = {"healthy": 1, "degraded": 2, "failed": 3, "unknown": 4}
        best = min(
            targets,
            key=lambda proxy: (
                order.get(proxy.health_status, 999),
                proxy.priority,
                proxy.response_time_ms if proxy.response_time_ms else 9999,
            ),
        )
        logger.info(
            "Selected proxy: id=%s status=%s priority=%s",
            best.id,
            best.health_status,
            best.priority,
        )
        return best.url

    async def _broadcast_proxy_status(
        self, proxy: ProxySnapshot | ProxySettings, auto_disabled: bool = False
    ):
        """
        Broadcast proxy status update via WebSocket.

        Args:
            proxy: ProxySettings model instance
            auto_disabled: Whether proxy was auto-disabled due to failures
        """
        try:
            manager = self._websocket_manager
            if manager is None:
                from app.services.communication.websocket_manager import (
                    websocket_manager,
                )

                manager = websocket_manager

            if isinstance(proxy, ProxySnapshot):
                proxy_data = proxy.payload()
            else:
                proxy_data = proxy.to_dict(mask_password=True)
                safe_proxy_url = sanitize_proxy_url_for_logging(proxy.proxy_url)
                proxy_data["proxy_url"] = safe_proxy_url
                proxy_data["masked_url"] = safe_proxy_url
            message = {
                "type": "proxy_health_update",
                "proxy": proxy_data,
                "auto_disabled": auto_disabled,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            await manager.send_notification(message)

        except Exception:
            logger.error("Error broadcasting proxy status")

    async def increment_recording_stats(self, proxy_url: str, success: bool):
        """
        Update recording statistics for a proxy.

        Args:
            proxy_url: Full proxy URL used for recording
            success: Whether recording succeeded (True) or failed (False)
        """
        await run_in_thread_pool(
            proxy_catalog.increment_stats,
            self._session_factory or SessionLocal,
            proxy_url,
            success,
        )


# Singleton instance
proxy_health_service = ProxyHealthService()
