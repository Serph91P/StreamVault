"""
Automated Recovery API Endpoints

Automatisierung der existierenden Recovery-Services:
- Unified Recovery (umfassend)
- Orphaned Recovery (orphaned segments)
- Failed Recovery (fehlgeschlagene Post-Processing)
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Dict, Any
import logging
import asyncio
from datetime import datetime, timedelta

logger = logging.getLogger("streamvault")

router = APIRouter(prefix="/api/recovery/automated", tags=["automated-recovery"])

# Global state für automatisierten Recovery
automated_recovery_running = False
recovery_interval = 300  # 5 Minuten Standard
last_recovery_run = None
recovery_stats = {
    "total_runs": 0,
    "successful_runs": 0,
    "failed_runs": 0,
    "last_error": None
}


async def run_comprehensive_recovery() -> Dict[str, Any]:
    """
    Führt umfassende Recovery mit allen existierenden Services aus
    
    Nutzt:
    1. Unified Recovery - für komplette Analyse
    2. Orphaned Recovery - für orphaned segments
    3. Failed Recovery - für fehlgeschlagene Post-Processing
    """
    global recovery_stats, last_recovery_run
    
    recovery_stats["total_runs"] += 1
    last_recovery_run = datetime.utcnow()
    
    results = {
        "start_time": last_recovery_run.isoformat(),
        "unified_recovery": None,
        "orphaned_recovery": None, 
        "failed_recovery": None,
        "total_recoveries": 0,
        "success": False
    }
    
    try:
        # 1. Unified Recovery (umfassendste Analyse)
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
        
        # 2. Orphaned Recovery (zusätzlich für orphaned segments)
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
        
        # 3. Failed Recovery (spezifisch für fehlgeschlagene Post-Processing)  
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
        
        results["end_time"] = datetime.utcnow().isoformat()
        results["success"] = True
        recovery_stats["successful_runs"] += 1
        recovery_stats["last_error"] = None
        
        logger.info(f"🎉 Comprehensive recovery completed: {results['total_recoveries']} total recoveries")
        return results
        
    except Exception as e:
        results["end_time"] = datetime.utcnow().isoformat()
        results["success"] = False
        results["error"] = str(e)
        recovery_stats["failed_runs"] += 1
        recovery_stats["last_error"] = str(e)
        logger.error(f"❌ Comprehensive recovery failed: {e}")
        return results


async def automated_recovery_loop():
    """
    Hauptschleife für automatisierte Recovery
    
    Läuft kontinuierlich und führt alle recovery_interval Sekunden
    umfassende Recovery durch.
    """
    global automated_recovery_running
    
    logger.info(f"🚀 Starting automated recovery loop (interval: {recovery_interval}s)")
    
    while automated_recovery_running:
        try:
            logger.info("🔄 Running automated recovery cycle...")
            result = await run_comprehensive_recovery()
            
            if result["success"]:
                logger.info(f"✅ Recovery cycle completed: {result['total_recoveries']} total recoveries")
            else:
                logger.error(f"❌ Recovery cycle failed: {result.get('error', 'Unknown error')}")
            
            # Warte bis zum nächsten Zyklus
            await asyncio.sleep(recovery_interval)
            
        except Exception as e:
            logger.error(f"❌ Error in automated recovery loop: {e}")
            await asyncio.sleep(60)  # Kurze Pause bei Fehlern
    
    logger.info("🛑 Automated recovery loop stopped")


@router.post("/start")
async def start_automated_recovery(
    background_tasks: BackgroundTasks,
    interval_minutes: int = 5
):
    """
    Startet automatisierte Recovery mit allen existierenden Services
    
    Args:
        interval_minutes: Intervall zwischen Recovery-Läufen (Standard: 5 Minuten)
    """
    global automated_recovery_running, recovery_interval
    
    try:
        if automated_recovery_running:
            return {
                "success": False,
                "message": "Automated recovery is already running"
            }
        
        if interval_minutes < 1 or interval_minutes > 1440:
            raise HTTPException(status_code=400, detail="Interval must be between 1 and 1440 minutes")
        
        recovery_interval = interval_minutes * 60
        automated_recovery_running = True
        
        # Starte Loop im Hintergrund
        background_tasks.add_task(automated_recovery_loop)
        
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
    global automated_recovery_running
    
    try:
        if not automated_recovery_running:
            return {
                "success": False,
                "message": "Automated recovery is not running"
            }
        
        automated_recovery_running = False
        
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


@router.get("/status")
async def get_recovery_status():
    """Gibt Status der automatisierten Recovery zurück"""
    global automated_recovery_running, last_recovery_run, recovery_stats
    
    return {
        "success": True,
        "data": {
            "is_running": automated_recovery_running,
            "interval_minutes": recovery_interval // 60,
            "last_run": last_recovery_run.isoformat() if last_recovery_run else None,
            "statistics": recovery_stats,
            "services": ["unified_recovery", "orphaned_recovery", "failed_recovery"]
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
    """
    global recovery_interval
    
    try:
        if interval_minutes is not None:
            if interval_minutes < 1 or interval_minutes > 1440:
                raise HTTPException(status_code=400, detail="Interval must be between 1 and 1440 minutes")
            recovery_interval = interval_minutes * 60
        
        return {
            "success": True,
            "message": "Configuration updated",
            "current_config": {
                "interval_minutes": recovery_interval // 60,
                "is_running": automated_recovery_running
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
