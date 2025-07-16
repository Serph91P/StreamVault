"""
Background Queue API Routes

Provides endpoints for monitoring and managing the background queue.
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any, Optional
import logging

from app.services.background_queue_service import background_queue_service, TaskPriority
from app.dependencies import get_current_user

router = APIRouter(prefix="/background-queue", tags=["background-queue"])
logger = logging.getLogger("streamvault")

@router.get("/stats")
async def get_queue_stats():
    """Get background queue statistics - Note: Consider using WebSocket for real-time updates"""
    try:
        stats = await background_queue_service.get_queue_stats()
        logger.debug("Background queue stats requested via REST API (consider WebSocket)")
        return {"success": True, "stats": stats}
    except Exception as e:
        logger.error(f"Error getting queue stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get queue stats")

@router.get("/active-tasks")
async def get_active_tasks():
    """Get currently active tasks - Note: Consider using WebSocket for real-time updates"""
    try:
        active_tasks = background_queue_service.get_active_tasks()
        logger.debug("Background queue active tasks requested via REST API (consider WebSocket)")
        return {"success": True, "active_tasks": active_tasks}
    except Exception as e:
        logger.error(f"Error getting active tasks: {e}")
        raise HTTPException(status_code=500, detail="Failed to get active tasks")

@router.get("/recent-tasks")
async def get_recent_tasks(limit: int = 50):
    """Get recently completed tasks"""
    try:
        recent_tasks = await background_queue_service.get_recent_tasks(limit=limit)
        return {"success": True, "recent_tasks": recent_tasks}
    except Exception as e:
        logger.error(f"Error getting recent tasks: {e}")
        raise HTTPException(status_code=500, detail="Failed to get recent tasks")

@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """Get status of a specific task"""
    try:
        task_status = background_queue_service.get_task_status(task_id)
        if not task_status:
            raise HTTPException(status_code=404, detail="Task not found")
        return {"success": True, "task": task_status}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting task status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get task status")

@router.post("/tasks/enqueue")
async def enqueue_task(
    task_type: str,
    payload: Dict[str, Any],
    priority: str = "normal",
    max_retries: int = 3
):
    """Manually enqueue a background task"""
    try:
        # Convert priority string to enum
        priority_map = {
            "low": TaskPriority.LOW,
            "normal": TaskPriority.NORMAL,
            "high": TaskPriority.HIGH,
            "critical": TaskPriority.CRITICAL
        }
        
        task_priority = priority_map.get(priority.lower(), TaskPriority.NORMAL)
        
        # Enqueue task
        task_id = await background_queue_service.enqueue_task(
            task_type=task_type,
            payload=payload,
            priority=task_priority,
            max_retries=max_retries
        )
        
        return {"success": True, "task_id": task_id}
    except Exception as e:
        logger.error(f"Error enqueuing task: {e}")
        raise HTTPException(status_code=500, detail="Failed to enqueue task")

@router.post("/tasks/metadata-generation")
async def enqueue_metadata_generation(
    stream_id: int,
    base_path: str,
    base_filename: str,
    priority: str = "normal"
):
    """Enqueue metadata generation task"""
    try:
        priority_map = {
            "low": TaskPriority.LOW,
            "normal": TaskPriority.NORMAL,
            "high": TaskPriority.HIGH,
            "critical": TaskPriority.CRITICAL
        }
        
        task_priority = priority_map.get(priority.lower(), TaskPriority.NORMAL)
        
        task_id = await background_queue_service.enqueue_task(
            task_type='metadata_generation',
            payload={
                'stream_id': stream_id,
                'base_path': base_path,
                'base_filename': base_filename
            },
            priority=task_priority,
            max_retries=2
        )
        
        return {"success": True, "task_id": task_id}
    except Exception as e:
        logger.error(f"Error enqueuing metadata generation task: {e}")
        raise HTTPException(status_code=500, detail="Failed to enqueue metadata generation task")

@router.post("/tasks/thumbnail-generation")
async def enqueue_thumbnail_generation(
    stream_id: int,
    output_dir: str,
    video_path: Optional[str] = None,
    priority: str = "normal"
):
    """Enqueue thumbnail generation task"""
    try:
        priority_map = {
            "low": TaskPriority.LOW,
            "normal": TaskPriority.NORMAL,
            "high": TaskPriority.HIGH,
            "critical": TaskPriority.CRITICAL
        }
        
        task_priority = priority_map.get(priority.lower(), TaskPriority.NORMAL)
        
        payload = {
            'stream_id': stream_id,
            'output_dir': output_dir
        }
        
        if video_path:
            payload['video_path'] = video_path
        
        task_id = await background_queue_service.enqueue_task(
            task_type='thumbnail_generation',
            payload=payload,
            priority=task_priority,
            max_retries=2
        )
        
        return {"success": True, "task_id": task_id}
    except Exception as e:
        logger.error(f"Error enqueuing thumbnail generation task: {e}")
        raise HTTPException(status_code=500, detail="Failed to enqueue thumbnail generation task")

@router.post("/tasks/file-cleanup")
async def enqueue_file_cleanup(
    files_to_delete: List[str] = [],
    directories_to_delete: List[str] = [],
    priority: str = "low"
):
    """Enqueue file cleanup task"""
    try:
        priority_map = {
            "low": TaskPriority.LOW,
            "normal": TaskPriority.NORMAL,
            "high": TaskPriority.HIGH,
            "critical": TaskPriority.CRITICAL
        }
        
        task_priority = priority_map.get(priority.lower(), TaskPriority.LOW)
        
        task_id = await background_queue_service.enqueue_task(
            task_type='file_cleanup',
            payload={
                'files_to_delete': files_to_delete,
                'directories_to_delete': directories_to_delete
            },
            priority=task_priority,
            max_retries=1
        )
        
        return {"success": True, "task_id": task_id}
    except Exception as e:
        logger.error(f"Error enqueuing file cleanup task: {e}")
        raise HTTPException(status_code=500, detail="Failed to enqueue file cleanup task")

# Health check endpoint
@router.get("/health")
async def queue_health():
    """Check if the background queue is healthy"""
    try:
        stats = await background_queue_service.get_queue_stats()
        is_healthy = stats['is_running'] and stats['workers'] > 0
        
        return {
            "success": True,
            "healthy": is_healthy,
            "status": "running" if is_healthy else "stopped",
            "workers": stats['workers'],
            "pending_tasks": stats['pending_tasks']
        }
    except Exception as e:
        logger.error(f"Error checking queue health: {e}")
        raise HTTPException(status_code=500, detail="Failed to check queue health")
