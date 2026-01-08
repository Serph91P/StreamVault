"""
Automated Recovery API Endpoints

Automatisierung der existierenden Recovery-Services:
- Unified Recovery (umfassend)
- Orphaned Recovery (orphaned segments)
- Failed Recovery (fehlgeschlagene Post-Processing)
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional
import logging
import asyncio
from datetime import datetime, timezone

logger = logging.getLogger("streamvault")

router = APIRouter(prefix="/api/recovery/automated", tags=["automated-recovery"])

# Constants
DEFAULT_RECOVERY_INTERVAL = 300  # 5 Minuten Standard
ERROR_DELAY_ON_FAILURE = 60  # Pause bei Fehlern in Sekunden
MIN_INTERVAL_MINUTES = 1
MAX_INTERVAL_MINUTES = 1440

# Thread-safe state management


class AutomatedRecoveryState:
    """Thread-safe state management for automated recovery"""

    def __init__(self):
        self._lock = asyncio.Lock()
        self._running = False
        self._interval = DEFAULT_RECOVERY_INTERVAL
        self._last_run = None
        self._stats = {
            "total_runs": 0,
            "successful_runs": 0,
            "failed_runs": 0,
            "last_error": None
        }
        self._task: Optional[asyncio.Task] = None

    async def is_running(self) -> bool:
        async with self._lock:
            return self._running

    async def set_running(self, running: bool):
        async with self._lock:
            self._running = running

    async def get_interval(self) -> int:
        async with self._lock:
            return self._interval

    async def set_interval(self, interval: int):
        async with self._lock:
            self._interval = interval

    async def get_last_run(self) -> Optional[datetime]:
        async with self._lock:
            return self._last_run

    async def set_last_run(self, timestamp: datetime):
        async with self._lock:
            self._last_run = timestamp

    async def get_stats(self) -> Dict[str, Any]:
        async with self._lock:
            return self._stats.copy()

    async def increment_total_runs(self):
        async with self._lock:
            self._stats["total_runs"] += 1

    async def increment_successful_runs(self):
        async with self._lock:
            self._stats["successful_runs"] += 1
            self._stats["last_error"] = None

    async def increment_failed_runs(self, error: str):
        async with self._lock:
            self._stats["failed_runs"] += 1
            self._stats["last_error"] = error

    async def set_task(self, task: Optional[asyncio.Task]):
        async with self._lock:
            self._task = task

    async def get_task(self) -> Optional[asyncio.Task]:
        async with self._lock:
            return self._task

    async def cancel_task(self):
        async with self._lock:
            if self._task and not self._task.done():
                self._task.cancel()
                self._task = None


# Global state instance
recovery_state = AutomatedRecoveryState()


async def run_comprehensive_recovery() -> Dict[str, Any]:
    """
    Runs comprehensive recovery with all existing services

    Uses:
    1. Simple Recovery - reliable metadata_generation tasks (WITHOUT dependencies)
    2. Unified Recovery - for complete analysis (if dependency chains work)
    3. Orphaned Recovery - for orphaned segments
    4. Failed Recovery - for failed post-processing
    """
    await recovery_state.increment_total_runs()
    now = datetime.now(timezone.utc)
    await recovery_state.set_last_run(now)

    results = {
        "start_time": now.isoformat(),
        "simple_recovery": None,
        "unified_recovery": None,
        "orphaned_recovery": None,
        "failed_recovery": None,
        "total_recoveries": 0,
        "success": False
    }

    try:
        # 1. Simple Recovery (reliable - single tasks without dependencies)
        logger.info("🔧 Starting simple reliable recovery...")
        try:
            from ..services.simple_recovery_service import run_simple_reliable_recovery
            simple_result = await run_simple_reliable_recovery()
            results["simple_recovery"] = simple_result.get("simple_recovery", {})
            results["total_recoveries"] += simple_result.get("total_recoveries", 0)
            logger.info(f"✅ Simple recovery: {simple_result.get('total_recoveries', 0)} tasks created")
        except Exception as e:
            logger.error(f"❌ Simple recovery failed: {e}")
            results["simple_recovery"] = {"success": False, "error": str(e)}

        # 2. Unified Recovery (most comprehensive analysis - if dependencies work)
        logger.info("🔧 Starting unified recovery...")
        try:
            from ..services.recording.unified_recovery_service import get_unified_recovery_service
            unified_service = await get_unified_recovery_service()
            unified_stats = await unified_service.comprehensive_recovery_scan(
                max_age_hours=72,
                dry_run=False
            )
            results["unified_recovery"] = {
                "success": True,
                "orphaned_segments": unified_stats.orphaned_segments,
                "failed_post_processing": unified_stats.failed_post_processing,
                "recovered_recordings": unified_stats.recovered_recordings,
                "triggered_post_processing": unified_stats.triggered_post_processing,
                "total_size_gb": unified_stats.total_size_gb
            }
            results["total_recoveries"] += unified_stats.recovered_recordings + unified_stats.triggered_post_processing
            logger.info(f"✅ Unified recovery: {unified_stats.recovered_recordings} recovered, {unified_stats.triggered_post_processing} triggered")
        except Exception as e:
            logger.error(f"❌ Unified recovery failed: {e}")
            results["unified_recovery"] = {"success": False, "error": str(e)}

        # 3. Orphaned Recovery (additional for orphaned segments)
        logger.info("🔧 Starting orphaned recovery...")
        try:
            from ..services.recording.orphaned_recovery_service import get_orphaned_recovery_service
            orphaned_service = await get_orphaned_recovery_service()
            orphaned_result = await orphaned_service.scan_and_recover_orphaned_recordings(
                max_age_hours=48,
                dry_run=False
            )
            results["orphaned_recovery"] = {
                "success": True,
                "recovery_triggered": orphaned_result.get("recovery_triggered", 0),
                "orphaned_found": orphaned_result.get("orphaned_found", 0)
            }
            results["total_recoveries"] += orphaned_result.get("recovery_triggered", 0)
            logger.info(f"✅ Orphaned recovery: {orphaned_result.get('recovery_triggered', 0)} triggered")
        except Exception as e:
            logger.error(f"❌ Orphaned recovery failed: {e}")
            results["orphaned_recovery"] = {"success": False, "error": str(e)}

        # 4. Failed Recovery (specific for failed post-processing)
        logger.info("🔧 Starting failed recovery...")
        try:
            from ..services.recording.failed_recording_recovery_service import get_failed_recovery_service
            failed_service = await get_failed_recovery_service()
            failed_result = await failed_service.scan_and_recover_failed_recordings(dry_run=False)
            results["failed_recovery"] = {
                "success": True,
                "recovery_triggered": failed_result.get("recovery_triggered", 0),
                "failed_found": failed_result.get("failed_found", 0),
                "recoverable_found": failed_result.get("recoverable_found", 0)
            }
            results["total_recoveries"] += failed_result.get("recovery_triggered", 0)
            logger.info(f"✅ Failed recovery: {failed_result.get('recovery_triggered', 0)} triggered")
        except Exception as e:
            logger.error(f"❌ Failed recovery failed: {e}")
            results["failed_recovery"] = {"success": False, "error": str(e)}

        results["end_time"] = datetime.now(timezone.utc).isoformat()
        results["success"] = True
        await recovery_state.increment_successful_runs()

        logger.info(f"🎉 Comprehensive recovery completed: {results['total_recoveries']} total recoveries")
        return results

    except Exception as e:
        results["end_time"] = datetime.now(timezone.utc).isoformat()
        results["success"] = False
        results["error"] = str(e)
        await recovery_state.increment_failed_runs(str(e))
        logger.error(f"❌ Comprehensive recovery failed: {e}")
        return results


async def automated_recovery_loop():
    """
    Hauptschleife für automatisierte Recovery

    Läuft kontinuierlich und führt alle recovery_interval Sekunden
    umfassende Recovery durch.
    """
    interval = await recovery_state.get_interval()
    logger.info(f"🚀 Starting automated recovery loop (interval: {interval}s)")

    while await recovery_state.is_running():
        try:
            logger.info("🔄 Running automated recovery cycle...")
            result = await run_comprehensive_recovery()

            if result["success"]:
                logger.info(f"✅ Recovery cycle completed: {result['total_recoveries']} total recoveries")
            else:
                logger.error(f"❌ Recovery cycle failed: {result.get('error', 'Unknown error')}")

            # Aktuelle Interval-Zeit abrufen (könnte geändert worden sein)
            current_interval = await recovery_state.get_interval()
            await asyncio.sleep(current_interval)

        except asyncio.CancelledError:
            logger.info("🛑 Automated recovery loop cancelled")
            break
        except Exception as e:
            logger.error(f"❌ Error in automated recovery loop: {e}")
            await asyncio.sleep(ERROR_DELAY_ON_FAILURE)

    await recovery_state.set_running(False)
    logger.info("🛑 Automated recovery loop stopped")


@router.post("/start")
async def start_automated_recovery(
    interval_minutes: int = 5
):
    """
    Startet automatisierte Recovery mit allen existierenden Services

    Args:
        interval_minutes: Intervall zwischen Recovery-Läufen (Standard: 5 Minuten)
    """
    try:
        if await recovery_state.is_running():
            return {
                "success": False,
                "message": "Automated recovery is already running"
            }

        if interval_minutes < MIN_INTERVAL_MINUTES or interval_minutes > MAX_INTERVAL_MINUTES:
            raise HTTPException(
                status_code=400,
                detail=f"Interval must be between {MIN_INTERVAL_MINUTES} and {MAX_INTERVAL_MINUTES} minutes"
            )

        await recovery_state.set_interval(interval_minutes * 60)
        await recovery_state.set_running(True)

        # Erstelle persistente Task statt Background Task
        task = asyncio.create_task(automated_recovery_loop())
        await recovery_state.set_task(task)

        return {
            "success": True,
            "message": "Automated comprehensive recovery started",
            "interval_minutes": interval_minutes,
            "services": ["unified_recovery", "orphaned_recovery", "failed_recovery"]
        }

    except Exception as e:
        logger.error(f"Failed to start automated recovery: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start recovery: {str(e)}")


@router.post("/stop")
async def stop_automated_recovery():
    """Stoppt die automatisierte Recovery"""
    try:
        if not await recovery_state.is_running():
            return {
                "success": False,
                "message": "Automated recovery is not running"
            }

        await recovery_state.set_running(False)
        await recovery_state.cancel_task()

        return {
            "success": True,
            "message": "Automated recovery stopped"
        }

    except Exception as e:
        logger.error(f"Failed to stop automated recovery: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to stop recovery: {str(e)}")


@router.post("/run-once")
async def run_manual_recovery():
    """
    Führt einmalig umfassende Recovery aus (alle Services)
    """
    try:
        result = await run_comprehensive_recovery()
        return result

    except Exception as e:
        logger.error(f"Manual comprehensive recovery failed: {e}")
        raise HTTPException(status_code=500, detail=f"Recovery failed: {str(e)}")


@router.post("/run-simple")
async def run_simple_recovery():
    """
    Runs simple reliable recovery once (only metadata_generation without dependencies).
    This bypasses the dependency chain problem and is the most reliable recovery method.
    """
    try:
        await recovery_state.increment_total_runs()
        now = datetime.now(timezone.utc)
        await recovery_state.set_last_run(now)

        logger.info("🔧 Starting manual simple reliable recovery...")
        from ..services.simple_recovery_service import run_simple_reliable_recovery
        result = await run_simple_reliable_recovery()

        await recovery_state.increment_successful_runs()
        logger.info(f"✅ Simple recovery completed: {result.get('total_recoveries', 0)} tasks created")
        return result

    except Exception as e:
        await recovery_state.increment_failed_runs(str(e))
        logger.error(f"❌ Simple recovery failed: {e}")
        raise HTTPException(status_code=500, detail=f"Simple recovery failed: {str(e)}")


@router.get("/status")
async def get_recovery_status():
    """Gibt Status der automatisierten Recovery zurück"""
    last_run = await recovery_state.get_last_run()
    stats = await recovery_state.get_stats()
    interval = await recovery_state.get_interval()

    return {
        "success": True,
        "data": {
            "is_running": await recovery_state.is_running(),
            "interval_minutes": interval // 60,
            "last_run": last_run.isoformat() if last_run else None,
            "statistics": stats,
            "services": ["simple_recovery", "unified_recovery", "orphaned_recovery", "failed_recovery"],
            "primary_service": "simple_recovery",
            "description": "Simple recovery runs first as it's most reliable (no dependency chains)"
        }
    }


@router.post("/configure")
async def configure_recovery(
    interval_minutes: int = None
):
    """
    Konfiguriert automatisierte Recovery

    Args:
        interval_minutes: Neues Intervall zwischen Recovery-Läufen

    Note: Änderungen werden beim nächsten Zyklus wirksam, nicht sofort
    """
    try:
        if interval_minutes is not None:
            if interval_minutes < MIN_INTERVAL_MINUTES or interval_minutes > MAX_INTERVAL_MINUTES:
                raise HTTPException(
                    status_code=400,
                    detail=f"Interval must be between {MIN_INTERVAL_MINUTES} and {MAX_INTERVAL_MINUTES} minutes"
                )
            await recovery_state.set_interval(interval_minutes * 60)

        current_interval = await recovery_state.get_interval()

        return {
            "success": True,
            "message": "Configuration updated (changes take effect on next cycle)",
            "current_config": {
                "interval_minutes": current_interval // 60,
                "is_running": await recovery_state.is_running()
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to configure recovery: {e}")
        raise HTTPException(status_code=500, detail=f"Configuration failed: {str(e)}")


@router.get("/test-services")
async def test_recovery_services():
    """
    Testet alle Recovery-Services (dry run)

    Nützlich um zu prüfen ob alle Services verfügbar sind
    """
    results = {
        "unified_recovery": None,
        "orphaned_recovery": None,
        "failed_recovery": None
    }

    # Test Unified Recovery
    try:
        from ..services.recording.unified_recovery_service import get_unified_recovery_service
        unified_service = await get_unified_recovery_service()
        unified_stats = await unified_service.comprehensive_recovery_scan(max_age_hours=72, dry_run=True)
        results["unified_recovery"] = {
            "available": True,
            "orphaned_segments": unified_stats.orphaned_segments,
            "failed_post_processing": unified_stats.failed_post_processing,
            "total_size_gb": unified_stats.total_size_gb
        }
    except Exception as e:
        results["unified_recovery"] = {"available": False, "error": str(e)}

    # Test Orphaned Recovery
    try:
        from ..services.recording.orphaned_recovery_service import get_orphaned_recovery_service
        orphaned_service = await get_orphaned_recovery_service()
        orphaned_result = await orphaned_service.scan_and_recover_orphaned_recordings(max_age_hours=48, dry_run=True)
        results["orphaned_recovery"] = {
            "available": True,
            "orphaned_found": orphaned_result.get("orphaned_found", 0)
        }
    except Exception as e:
        results["orphaned_recovery"] = {"available": False, "error": str(e)}

    # Test Failed Recovery
    try:
        from ..services.recording.failed_recording_recovery_service import get_failed_recovery_service
        failed_service = await get_failed_recovery_service()
        failed_result = await failed_service.scan_and_recover_failed_recordings(dry_run=True)
        results["failed_recovery"] = {
            "available": True,
            "failed_found": failed_result.get("failed_found", 0),
            "recoverable_found": failed_result.get("recoverable_found", 0)
        }
    except Exception as e:
        results["failed_recovery"] = {"available": False, "error": str(e)}

    return {
        "success": True,
        "services": results,
        "all_available": all(service.get("available", False) for service in results.values())
    }
