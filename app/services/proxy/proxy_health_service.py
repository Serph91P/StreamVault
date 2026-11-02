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
import json
from collections import OrderedDict
from collections.abc import Callable
import logging
from typing import Optional, TYPE_CHECKING
from datetime import datetime, timezone

from uuid import uuid4

from app.config.constants import ASYNC_DELAYS
from app.config.settings import settings
from app.database import SessionLocal
from app.models import ProxySettings
from app.services.proxy import proxy_catalog
from app.services.proxy.proxy_catalog import ProxySnapshot, ProxyPolicy, HealthResult
from app.utils.async_db_utils import run_in_thread_pool
from app.services.http_client import ManagedHTTPClient, HTTPPolicy, HTTPClientError
from app.services.system.supervisor import TaskSupervisor
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
        self._supervisor = TaskSupervisor("proxy-health")
        self._stop_task: asyncio.Task[None] | None = None
        self._token_http = ManagedHTTPClient(
            HTTPPolicy(
                connect_timeout=30,
                read_timeout=300,
                write_timeout=300,
                total_timeout=300,
                max_connections=1,
                max_keepalive_connections=1,
            )
        )
        self._proxy_clients: OrderedDict[str, ManagedHTTPClient] = OrderedDict()
        self._proxy_capacity = HTTPPolicy().max_connections

        # Test endpoint - Twitch API streams endpoint (requires auth, most realistic test)
        # This tests the actual endpoint used for recording, ensuring proxy works for Streamlink
        self.test_endpoint = "https://api.twitch.tv/helix/streams"
        self.token_endpoint = "https://id.twitch.tv/oauth2/token"

        logger.info("🔧 ProxyHealthService initialized")

    async def start(self):
        """Start the background health check task"""
        if self._running:
            logger.warning("⚠️ ProxyHealthService already running")
            return

        if self._stop_task is not None and not self._stop_task.done():
            raise RuntimeError("Proxy health service is stopping")
        if self._supervisor.closed:
            if self._stop_task is not None:
                self._stop_task.result()
            self._supervisor = TaskSupervisor("proxy-health")
            self._token_http = ManagedHTTPClient(self._token_http.policy)
            self._stop_task = None
        self._running = True
        self._background_task = self._supervisor.create_task(
            "periodic-health", self._run_health_checks_loop()
        )
        logger.info("✅ ProxyHealthService background task started")

    async def stop(self):
        """Stop the background health check task gracefully"""
        if self._stop_task is None:
            self._stop_task = asyncio.create_task(
                self._stop_resources(), name="streamvault:proxy-health:shutdown"
            )
        task = self._stop_task
        cancelled = False
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                cancelled = True
        task.result()
        if cancelled:
            raise asyncio.CancelledError

    async def _stop_resources(self) -> None:
        self._running = False
        try:
            await self._supervisor.shutdown()
        finally:
            clients = [self._token_http, *self._proxy_clients.values()]
            self._proxy_clients.clear()
            async with asyncio.TaskGroup() as group:
                for client in clients:
                    group.create_task(client.close())
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

    async def run_health_checks(self) -> None:
        name = f"health-cycle:{uuid4().hex}"
        task = self._supervisor.create_task(name, self._run_health_checks())
        try:
            await task
        finally:
            await self._supervisor.cancel_task(name)

    async def _run_health_checks(self):
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
        """Fetch one fresh token per operation through the owning direct pool."""
        try:
            runtime_settings = self._settings or settings
            client_id = runtime_settings.TWITCH_APP_ID
            client_secret = runtime_settings.TWITCH_APP_SECRET
            if not client_id or not client_secret:
                return None
            response = await self._token_http.request(
                "POST",
                self.token_endpoint,
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "grant_type": "client_credentials",
                },
            )
            if response.status_code != 200:
                logger.error(
                    "Failed to get Twitch access token for proxy health check (HTTP %s)",
                    response.status_code,
                )
                return None
            payload = json.loads(response.body)
            access_token = (
                payload.get("access_token") if isinstance(payload, dict) else None
            )
            if not isinstance(access_token, str) or not access_token:
                logger.error("Twitch token response for proxy health check was invalid")
                return None
            return access_token
        except asyncio.CancelledError:
            logger.error("Twitch token request for proxy health check was cancelled")
            raise
        except Exception:
            logger.error("Error getting access token for proxy health check")
            return None

    async def _proxy_transport(self, proxy_url: str) -> ManagedHTTPClient:
        if self._supervisor.closed:
            raise HTTPClientError("closed")
        if proxy_url in self._proxy_clients:
            self._proxy_clients.move_to_end(proxy_url)
            return self._proxy_clients[proxy_url]
        if len(self._proxy_clients) >= self._proxy_capacity:
            _, expired = self._proxy_clients.popitem(last=False)
            await expired.close()
        client = ManagedHTTPClient(
            HTTPPolicy(
                total_timeout=10,
                connect_timeout=5,
                read_timeout=10,
                write_timeout=10,
                max_connections=1,
                max_keepalive_connections=1,
            ),
            proxy=proxy_url,
        )
        self._proxy_clients[proxy_url] = client
        return client

    async def _check_proxy_health(
        self, proxy_url: str, access_token: str
    ) -> HealthResult:
        """One non-following request; retain the existing health classification."""
        if not proxy_url:
            return {
                "status": "failed",
                "response_time_ms": None,
                "error": "Proxy connection failed",
            }
        start = asyncio.get_running_loop().time()
        try:
            runtime_settings = self._settings or settings
            client = await self._proxy_transport(proxy_url)
            try:
                response = await client.request(
                    "GET",
                    self.test_endpoint,
                    headers={
                        "Client-ID": runtime_settings.TWITCH_APP_ID,
                        "Authorization": f"Bearer {access_token}",
                    },
                    follow_redirects=False,
                )
                status = response.status_code
            except HTTPClientError as error:
                if error.code != "status" or error.status_code is None:
                    raise
                status = error.status_code
            elapsed = int((asyncio.get_running_loop().time() - start) * 1000)
            if status == 200:
                if elapsed < 2000:
                    return {
                        "status": "healthy",
                        "response_time_ms": elapsed,
                        "error": None,
                    }
                return {
                    "status": "degraded",
                    "response_time_ms": elapsed,
                    "error": f"Slow response ({elapsed}ms)",
                }
            if status in (301, 302, 303, 307, 308):
                return {"status": "healthy", "response_time_ms": elapsed, "error": None}
            if 400 <= status < 500:
                message = (
                    f"Auth issue (HTTP {status})"
                    if status in (401, 403)
                    else f"HTTP {status}"
                )
                return {
                    "status": "degraded",
                    "response_time_ms": elapsed,
                    "error": message,
                }
            return {
                "status": "failed",
                "response_time_ms": elapsed,
                "error": f"HTTP {status}",
            }
        except asyncio.CancelledError:
            logger.warning("Proxy health request was cancelled")
            raise
        except HTTPClientError as error:
            message = (
                "Timeout after 10 seconds"
                if error.code == "timeout"
                else "Connection error"
            )
            logger.error("Proxy health transport failed: %s", error.code)
            return {"status": "failed", "response_time_ms": None, "error": message}
        except Exception:
            logger.error("Unexpected error checking proxy health")
            return {
                "status": "failed",
                "response_time_ms": None,
                "error": "Unexpected error during proxy health check",
            }

    async def check_proxy_health_manual(self, proxy_id: int) -> dict[str, object]:
        name = f"manual-health:{uuid4().hex}"
        task = self._supervisor.create_task(
            name, self._check_proxy_health_manual(proxy_id)
        )
        try:
            return await task
        finally:
            await self._supervisor.cancel_task(name)

    async def _check_proxy_health_manual(self, proxy_id: int) -> dict[str, object]:
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
        name = f"proxy-selection:{uuid4().hex}"
        task = self._supervisor.create_task(
            name,
            run_in_thread_pool(
                proxy_catalog.read_targets, self._session_factory or SessionLocal
            ),
        )
        try:
            targets = await task
        finally:
            await self._supervisor.cancel_task(name)
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
        name = f"proxy-statistics:{uuid4().hex}"
        task = self._supervisor.create_task(
            name,
            run_in_thread_pool(
                proxy_catalog.increment_stats,
                self._session_factory or SessionLocal,
                proxy_url,
                success,
            ),
        )
        try:
            await task
        finally:
            await self._supervisor.cancel_task(name)


# Singleton instance
proxy_health_service = ProxyHealthService()
