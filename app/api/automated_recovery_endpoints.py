"""
Automated Recovery API Endpoints

Automatisierung der existierenden Recovery-Services:
- Unified Recovery (umfassend)
- Orphaned Recovery (orphaned segments)
- Failed Recovery (fehlgeschlagene Post-Processing)
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Dict, Any
from functools import partial
from app.services.core.automated_recovery_state import AutomatedRecoveryState
from app.services.system.supervisor import TaskSupervisor
from app.dependencies import get_application_recovery_service
from app.services.recording.unified_recovery_service import UnifiedRecoveryService
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

# Global state instance
recovery_state = AutomatedRecoveryState()


def get_recovery_state(request: Request) -> AutomatedRecoveryState:
    return request.app.state.automated_recovery_state


def get_recovery_supervisor(request: Request) -> TaskSupervisor:
    supervisor = getattr(request.app.state, "task_supervisor", None)
    if supervisor is None or supervisor.closed:
        raise HTTPException(status_code=503, detail="Application is not running")
    return supervisor


async def run_comprehensive_recovery(
    state: AutomatedRecoveryState | None = None,
    service: UnifiedRecoveryService | None = None,
) -> Dict[str, Any]:
    """
    Runs comprehensive recovery with all existing services

    Uses:
    1. Simple Recovery - reliable metadata_generation tasks (WITHOUT dependencies)
    2. Unified Recovery - for complete analysis (if dependency chains work)
    3. Orphaned Recovery - for orphaned segments
    4. Failed Recovery - for failed post-processing
    """
    state = recovery_state if state is None else state
    await state.increment_total_runs()
    now = datetime.now(timezone.utc)
    await state.set_last_run(now)

    results = {
        "start_time": now.isoformat(),
        "simple_recovery": None,
        "unified_recovery": None,
        "orphaned_recovery": None,
        "failed_recovery": None,
        "total_recoveries": 0,
        "success": False,
    }

    try:
        # 1. Simple Recovery (reliable - single tasks without dependencies)
        logger.info("🔧 Starting simple reliable recovery...")
        try:
            from ..services.simple_recovery_service import run_simple_reliable_recovery

            simple_result = await run_simple_reliable_recovery(unified_service=service)
            results["simple_recovery"] = simple_result.get("simple_recovery", {})
            results["total_recoveries"] += simple_result.get("total_recoveries", 0)
            logger.info(
                f"✅ Simple recovery: {simple_result.get('total_recoveries', 0)} tasks created"
            )
        except Exception as e:
            logger.error(f"❌ Simple recovery failed: {e}")
            results["simple_recovery"] = {
                "success": False,
                "error": "Simple recovery failed",
            }

        # 2. Unified Recovery (most comprehensive analysis - if dependencies work)
        logger.info("🔧 Starting unified recovery...")
        try:
            from ..services.recording.unified_recovery_service import (
                get_unified_recovery_service,
            )

            unified_service = (
                service if service is not None else await get_unified_recovery_service()
            )
            unified_stats = await unified_service.comprehensive_recovery_scan(
                max_age_hours=72, dry_run=False
            )
            results["unified_recovery"] = {
                "success": True,
                "orphaned_segments": unified_stats.orphaned_segments,
                "failed_post_processing": unified_stats.failed_post_processing,
                "recovered_recordings": unified_stats.recovered_recordings,
                "triggered_post_processing": unified_stats.triggered_post_processing,
                "total_size_gb": unified_stats.total_size_gb,
            }
            results["total_recoveries"] += (
                unified_stats.recovered_recordings
                + unified_stats.triggered_post_processing
            )
            logger.info(
                f"✅ Unified recovery: {unified_stats.recovered_recordings} recovered, {unified_stats.triggered_post_processing} triggered"
            )
        except Exception as e:
            logger.error(f"❌ Unified recovery failed: {e}")
            results["unified_recovery"] = {
                "success": False,
                "error": "Unified recovery failed",
            }

        # 3. Orphaned Recovery (additional for orphaned segments)
        logger.info("🔧 Starting orphaned recovery...")
        try:
            from ..services.recording.orphaned_recovery_service import (
                OrphanedRecoveryService,
                get_orphaned_recovery_service,
            )

            orphaned_service = (
                OrphanedRecoveryService(service)
                if service is not None
                else await get_orphaned_recovery_service()
            )
            orphaned_result = (
                await orphaned_service.scan_and_recover_orphaned_recordings(
                    max_age_hours=48, dry_run=False
                )
            )
            results["orphaned_recovery"] = {
                "success": True,
                "recovery_triggered": orphaned_result.get("recovery_triggered", 0),
                "orphaned_found": orphaned_result.get("orphaned_found", 0),
            }
            results["total_recoveries"] += orphaned_result.get("recovery_triggered", 0)
            logger.info(
                f"✅ Orphaned recovery: {orphaned_result.get('recovery_triggered', 0)} triggered"
            )
        except Exception as e:
            logger.error(f"❌ Orphaned recovery failed: {e}")
            results["orphaned_recovery"] = {
                "success": False,
                "error": "Orphaned recovery failed",
            }

        # 4. Failed Recovery (specific for failed post-processing)
        logger.info("🔧 Starting failed recovery...")
        try:
            if service is None:
                from ..services.recording.unified_recovery_service import (
                    get_unified_recovery_service,
                )

                failed_service = await get_unified_recovery_service()
            else:
                failed_service = service
            failed_summary = await failed_service.comprehensive_recovery_scan(
                max_age_hours=72, dry_run=True
            )
            triggered = await failed_service.retry_failed_recordings()
            failed_result = {
                "failed_found": failed_summary.failed_post_processing,
                "recoverable_found": triggered,
                "recovery_triggered": triggered,
            }
            results["failed_recovery"] = {
                "success": True,
                "recovery_triggered": failed_result.get("recovery_triggered", 0),
                "failed_found": failed_result.get("failed_found", 0),
                "recoverable_found": failed_result.get("recoverable_found", 0),
            }
            results["total_recoveries"] += failed_result.get("recovery_triggered", 0)
            logger.info(
                f"✅ Failed recovery: {failed_result.get('recovery_triggered', 0)} triggered"
            )
        except Exception as e:
            logger.error(f"❌ Failed recovery failed: {e}")
            results["failed_recovery"] = {
                "success": False,
                "error": "Failed recovery failed",
            }

        results["end_time"] = datetime.now(timezone.utc).isoformat()
        results["success"] = all(
            isinstance(results[key], dict) and results[key].get("success") is True
            for key in (
                "simple_recovery",
                "unified_recovery",
                "orphaned_recovery",
                "failed_recovery",
            )
        )
        if results["success"]:
            await state.increment_successful_runs()
        else:
            await state.increment_failed_runs("Comprehensive recovery failed")

        logger.info(
            f"🎉 Comprehensive recovery completed: {results['total_recoveries']} total recoveries"
        )
        return results

    except Exception as e:
        results["end_time"] = datetime.now(timezone.utc).isoformat()
        results["success"] = False
        results["error"] = str(e)
        await state.increment_failed_runs(str(e))
        logger.error(f"❌ Comprehensive recovery failed: {e}")
        return results


async def automated_recovery_loop(
    state: AutomatedRecoveryState | None = None,
    service: UnifiedRecoveryService | None = None,
) -> None:
    """
    Hauptschleife für automatisierte Recovery

    Läuft kontinuierlich und führt alle recovery_interval Sekunden
    umfassende Recovery durch.
    """
    state = recovery_state if state is None else state
    interval = await state.get_interval()
    logger.info(f"🚀 Starting automated recovery loop (interval: {interval}s)")

    while await state.is_running():
        try:
            logger.info("🔄 Running automated recovery cycle...")
            result = await run_comprehensive_recovery(state=state, service=service)

            if result["success"]:
                logger.info(
                    f"✅ Recovery cycle completed: {result['total_recoveries']} total recoveries"
                )
            else:
                logger.error(
                    f"❌ Recovery cycle failed: {result.get('error', 'Unknown error')}"
                )

            # Aktuelle Interval-Zeit abrufen (könnte geändert worden sein)
            current_interval = await state.get_interval()
            await asyncio.sleep(current_interval)

        except asyncio.CancelledError:
            logger.info("🛑 Automated recovery loop cancelled")
            break
        except Exception as e:
            logger.error(f"❌ Error in automated recovery loop: {e}")
            await asyncio.sleep(ERROR_DELAY_ON_FAILURE)

    await state.set_running(False)
    logger.info("🛑 Automated recovery loop stopped")


@router.post("/start")
async def start_automated_recovery(
    interval_minutes: int = 5,
    state: AutomatedRecoveryState = Depends(get_recovery_state),
    supervisor: TaskSupervisor = Depends(get_recovery_supervisor),
    service: UnifiedRecoveryService = Depends(get_application_recovery_service),
):
    """
    Startet automatisierte Recovery mit allen existierenden Services

    Args:
        interval_minutes: Intervall zwischen Recovery-Läufen (Standard: 5 Minuten)
    """
    try:
        if await state.is_running():
            return {
                "success": False,
                "message": "Automated recovery is already running",
            }

        if (
            interval_minutes < MIN_INTERVAL_MINUTES
            or interval_minutes > MAX_INTERVAL_MINUTES
        ):
            raise HTTPException(
                status_code=400,
                detail=f"Interval must be between {MIN_INTERVAL_MINUTES} and {MAX_INTERVAL_MINUTES} minutes",
            )

        if not await state.start(
            supervisor,
            partial(automated_recovery_loop, state=state, service=service),
            interval_minutes * 60,
        ):
            return {
                "success": False,
                "message": "Automated recovery is already running",
            }

        return {
            "success": True,
            "message": "Automated comprehensive recovery started",
            "interval_minutes": interval_minutes,
            "services": ["unified_recovery", "orphaned_recovery", "failed_recovery"],
        }

    except Exception as e:
        logger.error(f"Failed to start automated recovery: {e}")
        raise HTTPException(status_code=500, detail="Failed to start recovery")


@router.post("/stop")
async def stop_automated_recovery(
    state: AutomatedRecoveryState = Depends(get_recovery_state),
):
    """Stoppt die automatisierte Recovery"""
    try:
        if not await state.is_running():
            return {"success": False, "message": "Automated recovery is not running"}

        await state.set_running(False)
        await state.cancel_task()

        return {"success": True, "message": "Automated recovery stopped"}

    except Exception as e:
        logger.error(f"Failed to stop automated recovery: {e}")
        raise HTTPException(status_code=500, detail="Failed to stop recovery")


@router.post("/run-once")
async def run_manual_recovery(
    state: AutomatedRecoveryState = Depends(get_recovery_state),
    service: UnifiedRecoveryService = Depends(get_application_recovery_service),
):
    """
    Führt einmalig umfassende Recovery aus (alle Services)
    """
    try:
        result = await run_comprehensive_recovery(state=state, service=service)
        return result

    except Exception as e:
        logger.error(f"Manual comprehensive recovery failed: {e}")
        raise HTTPException(status_code=500, detail="Recovery failed")


@router.post("/run-simple")
async def run_simple_recovery(
    state: AutomatedRecoveryState = Depends(get_recovery_state),
    service: UnifiedRecoveryService = Depends(get_application_recovery_service),
):
    """
    Runs simple reliable recovery once (only metadata_generation without dependencies).
    This bypasses the dependency chain problem and is the most reliable recovery method.
    """
    try:
        await state.increment_total_runs()
        now = datetime.now(timezone.utc)
        await state.set_last_run(now)

        logger.info("🔧 Starting manual simple reliable recovery...")
        from ..services.simple_recovery_service import run_simple_reliable_recovery

        result = await run_simple_reliable_recovery(unified_service=service)

        if result["success"]:
            await state.increment_successful_runs()
            logger.info(
                "Simple recovery completed: %s tasks created",
                result["total_recoveries"],
            )
        else:
            await state.increment_failed_runs("Simple recovery failed")
            logger.error("Simple recovery failed")
        return result

    except Exception as e:
        await state.increment_failed_runs(str(e))
        logger.error(f"❌ Simple recovery failed: {e}")
        raise HTTPException(status_code=500, detail="Simple recovery failed")


@router.get("/status")
async def get_recovery_status(
    state: AutomatedRecoveryState = Depends(get_recovery_state),
):
    """Gibt Status der automatisierten Recovery zurück"""
    last_run = await state.get_last_run()
    stats = await state.get_stats()
    interval = await state.get_interval()

    return {
        "success": True,
        "data": {
            "is_running": await state.is_running(),
            "interval_minutes": interval // 60,
            "last_run": last_run.isoformat() if last_run else None,
            "statistics": stats,
            "services": [
                "simple_recovery",
                "unified_recovery",
                "orphaned_recovery",
                "failed_recovery",
            ],
            "primary_service": "simple_recovery",
            "description": "Simple recovery runs first as it's most reliable (no dependency chains)",
        },
    }


@router.post("/configure")
async def configure_recovery(
    interval_minutes: int = None,
    state: AutomatedRecoveryState = Depends(get_recovery_state),
):
    """
    Konfiguriert automatisierte Recovery

    Args:
        interval_minutes: Neues Intervall zwischen Recovery-Läufen

    Note: Änderungen werden beim nächsten Zyklus wirksam, nicht sofort
    """
    try:
        if interval_minutes is not None:
            if (
                interval_minutes < MIN_INTERVAL_MINUTES
                or interval_minutes > MAX_INTERVAL_MINUTES
            ):
                raise HTTPException(
                    status_code=400,
                    detail=f"Interval must be between {MIN_INTERVAL_MINUTES} and {MAX_INTERVAL_MINUTES} minutes",
                )
            await state.set_interval(interval_minutes * 60)

        current_interval = await state.get_interval()

        return {
            "success": True,
            "message": "Configuration updated (changes take effect on next cycle)",
            "current_config": {
                "interval_minutes": current_interval // 60,
                "is_running": await state.is_running(),
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to configure recovery: {e}")
        raise HTTPException(status_code=500, detail="Configuration failed")


@router.get("/test-services")
async def test_recovery_services(
    service: UnifiedRecoveryService = Depends(get_application_recovery_service),
):
    """
    Testet alle Recovery-Services (dry run)

    Nützlich um zu prüfen ob alle Services verfügbar sind
    """
    results: dict[str, dict[str, bool | int | float | str]] = {}

    # Test Unified Recovery
    try:
        from ..services.recording.unified_recovery_service import (
            get_unified_recovery_service,
        )

        unified_service = (
            service if service is not None else await get_unified_recovery_service()
        )
        unified_stats = await unified_service.comprehensive_recovery_scan(
            max_age_hours=72, dry_run=True
        )
        results["unified_recovery"] = {
            "available": True,
            "orphaned_segments": unified_stats.orphaned_segments,
            "failed_post_processing": unified_stats.failed_post_processing,
            "total_size_gb": unified_stats.total_size_gb,
        }
    except Exception:
        results["unified_recovery"] = {
            "available": False,
            "error": "Service unavailable",
        }

    # Test Orphaned Recovery
    try:
        from ..services.recording.orphaned_recovery_service import (
            OrphanedRecoveryService,
            get_orphaned_recovery_service,
        )

        orphaned_service = (
            OrphanedRecoveryService(service)
            if service is not None
            else await get_orphaned_recovery_service()
        )
        orphaned_result = await orphaned_service.scan_and_recover_orphaned_recordings(
            max_age_hours=48, dry_run=True
        )
        results["orphaned_recovery"] = {
            "available": True,
            "orphaned_found": orphaned_result.get("orphaned_found", 0),
        }
    except Exception:
        results["orphaned_recovery"] = {
            "available": False,
            "error": "Service unavailable",
        }

    # Test Failed Recovery
    try:
        failed_summary = await service.comprehensive_recovery_scan(
            max_age_hours=72, dry_run=True
        )
        results["failed_recovery"] = {
            "available": True,
            "failed_found": failed_summary.failed_post_processing,
            # Preview never admits a chain, so recoverability is not yet proven.
            "recoverable_found": 0,
        }
    except Exception:
        results["failed_recovery"] = {
            "available": False,
            "error": "Service unavailable",
        }

    return {
        "success": True,
        "services": results,
        "all_available": all(
            service.get("available", False) for service in results.values()
        ),
    }
