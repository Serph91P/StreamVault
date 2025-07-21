"""
API endpoints for orphaned recording recovery management
"""

import logging
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import Dict, Any, Optional
from pydantic import BaseModel

from app.services.recording.orphaned_recovery_service import get_orphaned_recovery_service
from app.middleware.auth import require_auth

logger = logging.getLogger("streamvault")

router = APIRouter(prefix="/api/recording/orphaned", tags=["Recording Orphaned Recovery"])


class OrphanedRecoveryScanRequest(BaseModel):
    max_age_hours: int = 48
    dry_run: bool = False


class OrphanedRecoveryStatsRequest(BaseModel):
    max_age_hours: int = 168  # 1 week default


@router.get("/statistics")
async def get_orphaned_statistics(
    max_age_hours: int = 168,
    _: dict = Depends(require_auth)
) -> Dict[str, Any]:
    """Get statistics about orphaned recordings"""
    try:
        recovery_service = await get_orphaned_recovery_service()
        stats = await recovery_service.get_orphaned_statistics(max_age_hours)
        
        return {
            "success": True,
            "data": stats
        }
        
    except Exception as e:
        logger.error(f"Failed to get orphaned statistics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {str(e)}")


@router.post("/scan")
async def scan_orphaned_recordings(
    request: OrphanedRecoveryScanRequest,
    background_tasks: BackgroundTasks,
    _: dict = Depends(require_auth)
) -> Dict[str, Any]:
    """Scan for orphaned recordings and optionally trigger recovery"""
    try:
        recovery_service = await get_orphaned_recovery_service()
        
        if request.dry_run:
            # Synchronous dry run
            result = await recovery_service.scan_and_recover_orphaned_recordings(
                max_age_hours=request.max_age_hours,
                dry_run=True
            )
            
            return {
                "success": True,
                "message": "Dry run completed",
                "data": result
            }
        else:
            # Asynchronous recovery in background
            background_tasks.add_task(
                _background_orphaned_recovery,
                recovery_service,
                request.max_age_hours
            )
            
            return {
                "success": True,
                "message": f"Orphaned recovery started in background (max_age: {request.max_age_hours}h)",
                "data": {
                    "max_age_hours": request.max_age_hours,
                    "background": True
                }
            }
        
    except Exception as e:
        logger.error(f"Failed to scan orphaned recordings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to scan: {str(e)}")


@router.post("/recover-all")
async def recover_all_orphaned(
    background_tasks: BackgroundTasks,
    max_age_hours: int = 48,
    _: dict = Depends(require_auth)
) -> Dict[str, Any]:
    """Trigger recovery for all orphaned recordings (background task)"""
    try:
        recovery_service = await get_orphaned_recovery_service()
        
        # Run recovery in background
        background_tasks.add_task(
            _background_orphaned_recovery,
            recovery_service,
            max_age_hours
        )
        
        return {
            "success": True,
            "message": f"Orphaned recovery for all recordings started in background (max_age: {max_age_hours}h)"
        }
        
    except Exception as e:
        logger.error(f"Failed to start orphaned recovery: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to start recovery: {str(e)}")


@router.post("/recover-recording/{recording_id}")
async def recover_specific_recording(
    recording_id: int,
    _: dict = Depends(require_auth)
) -> Dict[str, Any]:
    """Trigger recovery for a specific recording"""
    try:
        recovery_service = await get_orphaned_recovery_service()
        
        # Get recording details first
        from app.database import SessionLocal
        from app.models import Recording
        
        with SessionLocal() as db:
            recording = db.query(Recording).filter(Recording.id == recording_id).first()
            if not recording:
                raise HTTPException(status_code=404, detail=f"Recording {recording_id} not found")

            # Validate it's actually orphaned
            validation = await recovery_service.validate_orphaned_recording(recording)
            if not validation["valid"]:
                return {
                    "success": False,
                    "message": f"Recording {recording_id} is not suitable for recovery: {validation['reason']}"
                }
            
            # Trigger recovery
            success = await recovery_service.trigger_orphaned_recovery(recording, db)
            
            if success:
                return {
                    "success": True,
                    "message": f"Recovery triggered for recording {recording_id}",
                    "data": {
                        "recording_id": recording_id,
                        "file_path": recording.path,
                        "file_size": validation.get("file_size")
                    }
                }
            else:
                return {
                    "success": False,
                    "message": f"Failed to trigger recovery for recording {recording_id}"
                }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to recover recording {recording_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to recover recording: {str(e)}")


async def _background_orphaned_recovery(
    recovery_service,
    max_age_hours: int
):
    """Background task for orphaned recovery"""
    try:
        logger.info(f"Starting background orphaned recovery (max_age: {max_age_hours}h)")
        
        result = await recovery_service.scan_and_recover_orphaned_recordings(
            max_age_hours=max_age_hours,
            dry_run=False
        )
        
        logger.info(f"Background orphaned recovery completed: {result['recovery_triggered']} recoveries triggered")
        
        # Send notification about completion if WebSocket service is available
        try:
            from app.services.websocket.websocket_service import websocket_service
            if websocket_service:
                await websocket_service.send_system_notification({
                    "type": "orphaned_recovery_complete",
                    "message": f"Orphaned recovery completed: {result['recovery_triggered']} recordings processed",
                    "data": result
                })
        except Exception as e:
            logger.debug(f"Could not send WebSocket notification: {e}")
        
    except Exception as e:
        logger.error(f"Background orphaned recovery failed: {e}", exc_info=True)
        
        # Send error notification
        try:
            from app.services.websocket.websocket_service import websocket_service
            if websocket_service:
                await websocket_service.send_system_notification({
                    "type": "orphaned_recovery_error",
                    "message": f"Orphaned recovery failed: {str(e)}",
                    "error": str(e)
                })
        except Exception as e2:
            logger.debug(f"Could not send error notification: {e2}")
