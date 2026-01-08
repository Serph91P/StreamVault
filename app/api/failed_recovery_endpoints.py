"""
Failed Recording Recovery API Endpoints

Provides API endpoints for managing and triggering failed recording recovery.
"""

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from typing import Dict, Any
import logging

logger = logging.getLogger("streamvault")

router = APIRouter(prefix="/api/admin/failed-recovery", tags=["Failed Recording Recovery"])


@router.get("/stats")
async def get_failed_recovery_stats() -> Dict[str, Any]:
    """Get statistics about failed recordings that can be recovered"""
    try:
        from app.services.recording.failed_recording_recovery_service import get_failed_recovery_service

        recovery_service = await get_failed_recovery_service()
        result = await recovery_service.scan_and_recover_failed_recordings(dry_run=True)

        return {
            "success": True,
            "stats": {
                "failed_recordings": result["failed_found"],
                "recoverable_recordings": result["recoverable_found"],
                "pending_recovery": result["recovery_triggered"]
            },
            "details": result["details"]
        }

    except Exception as e:
        logger.error(f"Failed to get failed recovery stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@router.post("/scan")
async def scan_failed_recordings(
    dry_run: bool = Query(False, description="If true, only show what would be recovered"),
    background_tasks: BackgroundTasks = None
) -> Dict[str, Any]:
    """Scan for failed recordings and optionally trigger recovery"""
    try:
        from app.services.recording.failed_recovery_recovery_service import get_failed_recovery_service

        recovery_service = await get_failed_recovery_service()

        if dry_run:
            # Synchronous dry run
            result = await recovery_service.scan_and_recover_failed_recordings(dry_run=True)

            return {
                "success": True,
                "message": "Dry run completed",
                "data": result
            }
        else:
            # Asynchronous recovery in background
            if background_tasks:
                background_tasks.add_task(
                    _background_failed_recovery,
                    recovery_service
                )
            else:
                # Run synchronously if no background tasks available
                result = await recovery_service.scan_and_recover_failed_recordings(dry_run=False)
                return {
                    "success": True,
                    "message": "Recovery completed",
                    "data": result
                }

            return {
                "success": True,
                "message": "Failed recording recovery started in background",
                "data": {
                    "background": True
                }
            }

    except Exception as e:
        logger.error(f"Failed to scan failed recordings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to scan: {str(e)}")


@router.post("/recover/{recording_id}")
async def recover_specific_recording(recording_id: int) -> Dict[str, Any]:
    """Manually trigger recovery for a specific failed recording"""
    try:
        from app.services.recording.failed_recording_recovery_service import get_failed_recovery_service

        recovery_service = await get_failed_recovery_service()
        result = await recovery_service.recover_specific_recording(recording_id)

        if result["success"]:
            return {
                "success": True,
                "message": result["message"],
                "data": {
                    "recording_id": recording_id,
                    "segments_found": result.get("segments_found", 0),
                    "segments_dir": result.get("segments_dir")
                }
            }
        else:
            return {
                "success": False,
                "message": result["error"]
            }

    except Exception as e:
        logger.error(f"Failed to recover recording {recording_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to recover recording: {str(e)}")


async def _background_failed_recovery(recovery_service):
    """Background task for failed recording recovery"""
    try:
        logger.info("🔧 Starting background failed recording recovery...")

        result = await recovery_service.scan_and_recover_failed_recordings(dry_run=False)

        logger.info(f"🔧 Background failed recovery completed: "
                    f"triggered={result['recovery_triggered']}, "
                    f"failed={result['recovery_failed']}")

        # Send WebSocket notification if available
        try:
            from app.services.websocket.websocket_service import websocket_service
            if websocket_service and result["recovery_triggered"] > 0:
                await websocket_service.send_system_notification({
                    "type": "failed_recovery_completed",
                    "message": f"Failed recording recovery completed: {result['recovery_triggered']} recordings processed",
                    "data": {
                        "recovery_triggered": result["recovery_triggered"],
                        "recovery_failed": result["recovery_failed"],
                        "total_recoverable": result["recoverable_found"]
                    }
                })
        except Exception as e:
            logger.debug(f"Could not send WebSocket notification: {e}")

    except Exception as e:
        logger.error(f"Background failed recording recovery failed: {e}", exc_info=True)
