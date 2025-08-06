"""
API endpoints for unified recording recovery management
"""

import logging
from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Dict, Any, Optional
from pydantic import BaseModel

from app.services.recording.unified_recovery_service import get_unified_recovery_service

logger = logging.getLogger("streamvault")

router = APIRouter(prefix="/api/recording/recovery", tags=["Recording Recovery"])


class RecoveryScanRequest(BaseModel):
    max_age_hours: int = 72
    dry_run: bool = False


@router.get("/statistics")
async def get_recovery_statistics(
    max_age_hours: int = 72
) -> Dict[str, Any]:
    """Get statistics about recoverable recordings"""
    try:
        recovery_service = await get_unified_recovery_service()
        
        # Run scan to get current statistics
        stats = await recovery_service.comprehensive_recovery_scan(max_age_hours=max_age_hours, dry_run=True)
        
        return {
            "success": True,
            "statistics": {
                "orphaned_segments": stats.orphaned_segments,
                "failed_post_processing": stats.failed_post_processing,
                "corrupted_recordings": stats.corrupted_recordings,
                "recovered_recordings": stats.recovered_recordings,
                "triggered_post_processing": stats.triggered_post_processing,
                "total_size_gb": stats.total_size_gb
            }
        }
    except Exception as e:
        logger.error(f"Error getting recovery statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scan")
async def comprehensive_recovery_scan(
    request: RecoveryScanRequest,
    background_tasks: BackgroundTasks
) -> Dict[str, Any]:
    """Comprehensive recovery scan and optionally trigger recovery"""
    try:
        recovery_service = await get_unified_recovery_service()
        
        if request.dry_run:
            # Synchronous dry run
            stats = await recovery_service.comprehensive_recovery_scan(
                max_age_hours=request.max_age_hours,
                dry_run=True
            )
            
            return {
                "success": True,
                "message": "Dry run completed",
                "dry_run": True,
                "statistics": {
                    "orphaned_segments": stats.orphaned_segments,
                    "failed_post_processing": stats.failed_post_processing,
                    "corrupted_recordings": stats.corrupted_recordings,
                    "total_size_gb": stats.total_size_gb
                }
            }
        else:
            # Asynchronous actual recovery
            async def run_recovery():
                try:
                    stats = await recovery_service.comprehensive_recovery_scan(
                        max_age_hours=request.max_age_hours,
                        dry_run=False
                    )
                    logger.info(f"✅ COMPREHENSIVE_RECOVERY_COMPLETE: {stats}")
                except Exception as e:
                    logger.error(f"❌ COMPREHENSIVE_RECOVERY_FAILED: {e}")
            
            background_tasks.add_task(run_recovery)
            
            return {
                "success": True,
                "message": "Comprehensive recovery started in background",
                "dry_run": False
            }
            
    except Exception as e:
        logger.error(f"Error in comprehensive recovery scan: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_recovery_status() -> Dict[str, Any]:
    """Get current recovery service status"""
    try:
        recovery_service = await get_unified_recovery_service()
        
        return {
            "success": True,
            "status": {
                "is_running": recovery_service.is_running,
                "recordings_base_path": str(recovery_service.recordings_base_path)
            }
        }
    except Exception as e:
        logger.error(f"Error getting recovery status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
