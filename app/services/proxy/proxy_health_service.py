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

import asyncio
import logging
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timezone
from sqlalchemy import select, and_
from sqlalchemy.orm import Session

import httpx

from app.database import SessionLocal
from app.models import ProxySettings, RecordingSettings
from app.config.constants import TIMEOUTS

logger = logging.getLogger('streamvault')


class ProxyHealthService:
    """
    Service for monitoring proxy health and selecting best available proxy.
    
    This is a singleton service that runs a background task for periodic health checks.
    """
    
    def __init__(self):
        self._background_task: Optional[asyncio.Task] = None
        self._running = False
        self._lock = asyncio.Lock()
        
        # Test endpoint - Twitch API (fast, reliable, no auth needed for connectivity test)
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
            except Exception as e:
                logger.error(f"🚨 Error in health check loop: {e}", exc_info=True)
                # Wait before retrying to avoid tight error loop
                await asyncio.sleep(60)
    
    async def _get_check_interval(self) -> int:
        """Get health check interval from database settings"""
        try:
            with SessionLocal() as db:
                settings = db.query(RecordingSettings).first()
                if settings and hasattr(settings, 'proxy_health_check_interval_seconds'):
                    return settings.proxy_health_check_interval_seconds
        except Exception as e:
            logger.error(f"Error getting check interval: {e}")
        
        # Default: 5 minutes
        return 300
    
    async def _are_checks_enabled(self) -> bool:
        """Check if proxy health checks are enabled in settings"""
        try:
            with SessionLocal() as db:
                settings = db.query(RecordingSettings).first()
                if settings and hasattr(settings, 'proxy_health_check_enabled'):
                    return settings.proxy_health_check_enabled
        except Exception as e:
            logger.error(f"Error checking if health checks enabled: {e}")
        
        # Default: enabled
        return True
    
    async def run_health_checks(self):
        """
        Run health checks on all enabled proxies and update database.
        
        This method is called by the background task periodically, but can also
        be called manually (e.g., from API endpoint for manual health check).
        """
        async with self._lock:
            logger.info("🏥 Running proxy health checks...")
            
            with SessionLocal() as db:
                # Get all enabled proxies
                proxies = db.query(ProxySettings).filter(
                    ProxySettings.enabled == True
                ).all()
                
                if not proxies:
                    logger.debug("ℹ️ No enabled proxies to check")
                    return
                
                logger.info(f"🔍 Checking {len(proxies)} enabled proxies...")
                
                # Check each proxy
                for proxy in proxies:
                    try:
                        health_result = await self._check_proxy_health(proxy.proxy_url)
                        
                        # Update proxy health in database
                        proxy.last_health_check = datetime.now(timezone.utc)
                        proxy.health_status = health_result['status']
                        proxy.average_response_time_ms = health_result.get('response_time_ms')
                        
                        # Update consecutive failures counter
                        if health_result['status'] == 'failed':
                            proxy.consecutive_failures += 1
                            logger.warning(
                                f"⚠️ Proxy health check failed: {proxy.masked_url} - "
                                f"Failures: {proxy.consecutive_failures}/{await self._get_max_failures()}"
                            )
                        else:
                            # Reset counter on success
                            proxy.consecutive_failures = 0
                            logger.info(
                                f"✅ Proxy health check passed: {proxy.masked_url} - "
                                f"{health_result['status']} ({health_result.get('response_time_ms')}ms)"
                            )
                        
                        # Auto-disable after max consecutive failures
                        max_failures = await self._get_max_failures()
                        if proxy.consecutive_failures >= max_failures and proxy.enabled:
                            proxy.enabled = False
                            logger.error(
                                f"🚨 Proxy auto-disabled after {proxy.consecutive_failures} failures: "
                                f"{proxy.masked_url}"
                            )
                            
                            # Broadcast notification
                            await self._broadcast_proxy_status(proxy, auto_disabled=True)
                        else:
                            # Broadcast normal status update
                            await self._broadcast_proxy_status(proxy, auto_disabled=False)
                        
                        db.commit()
                        
                    except Exception as e:
                        logger.error(f"Error checking proxy {proxy.id}: {e}", exc_info=True)
                        db.rollback()
                
                logger.info("✅ Proxy health checks completed")
    
    async def _get_max_failures(self) -> int:
        """Get max consecutive failures threshold from settings"""
        try:
            with SessionLocal() as db:
                settings = db.query(RecordingSettings).first()
                if settings and hasattr(settings, 'proxy_max_consecutive_failures'):
                    return settings.proxy_max_consecutive_failures
        except Exception as e:
            logger.error(f"Error getting max failures: {e}")
        
        # Default: 3 failures
        return 3
    
    async def _check_proxy_health(self, proxy_url: str) -> Dict[str, Any]:
        """
        Check health of a single proxy by testing connectivity.
        
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
        timeout = httpx.Timeout(10.0, connect=5.0)  # 10s total, 5s connect
        
        try:
            start_time = asyncio.get_event_loop().time()
            
            async with httpx.AsyncClient(
                proxies={
                    'http://': proxy_url,
                    'https://': proxy_url,
                },
                timeout=timeout,
                follow_redirects=True
            ) as client:
                # Test with Twitch API endpoint
                response = await client.get(self.test_endpoint)
                
                end_time = asyncio.get_event_loop().time()
                response_time_ms = int((end_time - start_time) * 1000)
                
                # Categorize status based on HTTP status code
                if response.status_code == 200:
                    return {
                        'status': 'healthy',
                        'response_time_ms': response_time_ms,
                        'error': None
                    }
                elif 400 <= response.status_code < 500:
                    # 4xx = proxy works but request invalid (degraded)
                    return {
                        'status': 'degraded',
                        'response_time_ms': response_time_ms,
                        'error': f'HTTP {response.status_code}'
                    }
                else:
                    # 5xx = proxy or upstream error (failed)
                    return {
                        'status': 'failed',
                        'response_time_ms': response_time_ms,
                        'error': f'HTTP {response.status_code}'
                    }
        
        except httpx.TimeoutException:
            return {
                'status': 'failed',
                'response_time_ms': None,
                'error': 'Timeout after 10 seconds'
            }
        
        except httpx.ProxyError as e:
            return {
                'status': 'failed',
                'response_time_ms': None,
                'error': f'Proxy error: {str(e)[:100]}'
            }
        
        except Exception as e:
            logger.error(f"Unexpected error checking proxy health: {e}", exc_info=True)
            return {
                'status': 'failed',
                'response_time_ms': None,
                'error': f'Exception: {str(e)[:100]}'
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
        with SessionLocal() as db:
            proxy = db.query(ProxySettings).filter(ProxySettings.id == proxy_id).first()
            
            if not proxy:
                return {'error': 'Proxy not found'}
            
            # Run health check
            health_result = await self._check_proxy_health(proxy.proxy_url)
            
            # Update database
            proxy.last_health_check = datetime.now(timezone.utc)
            proxy.health_status = health_result['status']
            proxy.average_response_time_ms = health_result.get('response_time_ms')
            
            # Update consecutive failures
            if health_result['status'] == 'failed':
                proxy.consecutive_failures += 1
            else:
                proxy.consecutive_failures = 0
            
            db.commit()
            
            # Broadcast status update
            await self._broadcast_proxy_status(proxy, auto_disabled=False)
            
            logger.info(f"🔧 Manual health check: {proxy.masked_url} - {health_result['status']}")
            
            return {
                'proxy_id': proxy.id,
                'health_status': proxy.health_status,
                'response_time_ms': proxy.average_response_time_ms,
                'consecutive_failures': proxy.consecutive_failures,
                'enabled': proxy.enabled
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
        with SessionLocal() as db:
            # Define status priority order
            status_order = {
                'healthy': 1,
                'degraded': 2,
                'failed': 3,
                'unknown': 4
            }
            
            # Get all enabled proxies ordered by selection criteria
            proxies = db.query(ProxySettings).filter(
                ProxySettings.enabled == True
            ).all()
            
            if not proxies:
                logger.debug("ℹ️ No enabled proxies available")
                return None
            
            # Sort by: health status > priority > response time
            sorted_proxies = sorted(
                proxies,
                key=lambda p: (
                    status_order.get(p.health_status, 999),  # Health status priority
                    p.priority,  # Priority field (0 = highest)
                    p.average_response_time_ms if p.average_response_time_ms else 9999  # Response time
                )
            )
            
            # Get best proxy
            best_proxy = sorted_proxies[0]
            
            logger.info(
                f"✅ Selected best proxy: {best_proxy.masked_url} - "
                f"Status: {best_proxy.health_status}, Priority: {best_proxy.priority}, "
                f"Response: {best_proxy.average_response_time_ms}ms"
            )
            
            return best_proxy.proxy_url
    
    async def _broadcast_proxy_status(self, proxy: ProxySettings, auto_disabled: bool = False):
        """
        Broadcast proxy status update via WebSocket.
        
        Args:
            proxy: ProxySettings model instance
            auto_disabled: Whether proxy was auto-disabled due to failures
        """
        try:
            from app.services.communication.websocket_manager import websocket_manager
            
            message = {
                'type': 'proxy_health_update',
                'proxy': proxy.to_dict(mask_password=True),
                'auto_disabled': auto_disabled,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
            await websocket_manager.broadcast(message)
            
        except Exception as e:
            logger.error(f"Error broadcasting proxy status: {e}", exc_info=True)
    
    async def increment_recording_stats(self, proxy_url: str, success: bool):
        """
        Update recording statistics for a proxy.
        
        Args:
            proxy_url: Full proxy URL used for recording
            success: Whether recording succeeded (True) or failed (False)
        """
        with SessionLocal() as db:
            proxy = db.query(ProxySettings).filter(
                ProxySettings.proxy_url == proxy_url
            ).first()
            
            if proxy:
                proxy.total_recordings += 1
                if not success:
                    proxy.failed_recordings += 1
                
                proxy.update_success_rate()
                db.commit()
                
                logger.debug(
                    f"📊 Proxy stats updated: {proxy.masked_url} - "
                    f"Total: {proxy.total_recordings}, Failed: {proxy.failed_recordings}, "
                    f"Success rate: {proxy.success_rate:.1f}%"
                )


# Singleton instance
proxy_health_service = ProxyHealthService()
