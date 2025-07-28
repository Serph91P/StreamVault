"""
Admin API for background queue cleanup
"""

from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from app.dependencies import admin_key_guard
from app.services.background_queue_cleanup_service import get_cleanup_service
import logging

router = APIRouter()
logger = logging.getLogger("streamvault")


@router.post("/admin/cleanup/background-queue", dependencies=[Depends(admin_key_guard)])
async def cleanup_background_queue() -> Dict[str, Any]:
    """
    Clean up stuck background queue tasks and fix production issues:
    
    Fixes:
    1. Recording jobs stuck at 100% running
    2. Orphaned recovery check running continuously
    3. Task names showing as "Unknown"
    """
    try:
        cleanup_service = get_cleanup_service()
        
        logger.info("🧹 MANUAL_CLEANUP_START: Admin triggered background queue cleanup")
        
        results = await cleanup_service.comprehensive_cleanup()
        
        logger.info("🧹 MANUAL_CLEANUP_COMPLETE: Admin cleanup finished")
        
        return {
            "success": True,
            "message": "Background queue cleanup completed",
            "results": results
        }
    
    except Exception as e:
        logger.error(f"Manual cleanup failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")


@router.post("/admin/cleanup/stuck-recordings", dependencies=[Depends(admin_key_guard)])
async def cleanup_stuck_recordings() -> Dict[str, Any]:
    """Clean up only stuck recording tasks"""
    try:
        cleanup_service = get_cleanup_service()
        results = await cleanup_service.cleanup_stuck_recording_tasks()
        
        return {
            "success": True,
            "message": "Stuck recording cleanup completed",
            "results": results
        }
    
    except Exception as e:
        logger.error(f"Stuck recording cleanup failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")


@router.post("/admin/cleanup/orphaned-recovery", dependencies=[Depends(admin_key_guard)])
async def stop_orphaned_recovery() -> Dict[str, Any]:
    """Stop continuous orphaned recovery checks"""
    try:
        cleanup_service = get_cleanup_service()
        results = await cleanup_service.stop_continuous_orphaned_recovery()
        
        return {
            "success": True,
            "message": "Orphaned recovery cleanup completed",
            "results": results
        }
    
    except Exception as e:
        logger.error(f"Orphaned recovery cleanup failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")


@router.post("/admin/cleanup/task-names", dependencies=[Depends(admin_key_guard)])
async def fix_task_names() -> Dict[str, Any]:
    """Fix tasks showing as 'Unknown'"""
    try:
        cleanup_service = get_cleanup_service()
        results = await cleanup_service.fix_unknown_task_names()
        
        return {
            "success": True,
            "message": "Task name fixes completed",
            "results": results
        }
    
    except Exception as e:
        logger.error(f"Task name fix failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Fix failed: {str(e)}")


@router.get("/admin/status/background-queue", dependencies=[Depends(admin_key_guard)])
async def get_background_queue_status() -> Dict[str, Any]:
    """Get current background queue status for debugging"""
    try:
        from app.services.background_queue_service import background_queue_service
        
        external_tasks = getattr(background_queue_service, 'external_tasks', {})
        active_tasks = getattr(background_queue_service, 'active_tasks', {})
        
        # Analyze tasks for potential issues
        stuck_recordings = []
        continuous_orphaned = []
        unknown_tasks = []
        
        # Check external tasks
        for task_id, task in external_tasks.items():
            if task_id.startswith('recording_') and task.progress >= 100 and task.status.value == 'running':
                stuck_recordings.append(task_id)
            
            if not task.task_type or task.task_type in ['unknown', '']:
                unknown_tasks.append(task_id)
        
        # Check active tasks for orphaned recovery
        for task_id, task in active_tasks.items():
            if task.task_type == 'orphaned_recovery_check':
                continuous_orphaned.append(task_id)
            
            if not task.task_type or task.task_type in ['unknown', '']:
                unknown_tasks.append(task_id)
        
        return {
            "success": True,
            "status": {
                "external_tasks_count": len(external_tasks),
                "active_tasks_count": len(active_tasks),
                "issues": {
                    "stuck_recordings": stuck_recordings,
                    "continuous_orphaned_recovery": continuous_orphaned,
                    "unknown_task_names": unknown_tasks
                },
                "needs_cleanup": bool(stuck_recordings or continuous_orphaned or unknown_tasks)
            }
        }
    
    except Exception as e:
        logger.error(f"Failed to get background queue status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")
