"""
API endpoints for background queue monitoring
"""

from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
import logging
from datetime import datetime, timezone

from app.services.init.background_queue_init import get_background_queue_service

router = APIRouter(prefix="/api/background-queue", tags=["background-queue"])
logger = logging.getLogger("streamvault")


@router.get("/stats")
async def get_queue_stats() -> Dict[str, Any]:
    """Get background queue statistics"""
    try:
        queue_service = get_background_queue_service()
        stats = await queue_service.get_queue_stats()
        return stats
    except Exception as e:
        logger.error(f"Error getting queue stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get queue statistics")


@router.get("/active-tasks")
async def get_active_tasks() -> List[Dict[str, Any]]:
    """Get currently active tasks"""
    try:
        queue_service = get_background_queue_service()
        active_tasks = []

        # Get active tasks from the queue service
        for task_id, task in queue_service.active_tasks.items():
            task_info = task.to_dict()
            active_tasks.append(task_info)

        # Also include external tasks (like recordings)
        for task_id, task in queue_service.external_tasks.items():
            if task.status.value in ["running", "pending"]:
                task_info = task.to_dict()
                active_tasks.append(task_info)

        return active_tasks
    except Exception as e:
        logger.error(f"Error getting active tasks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get active tasks")


@router.get("/recent-tasks")
async def get_recent_tasks() -> List[Dict[str, Any]]:
    """Get recently completed tasks"""
    try:
        queue_service = get_background_queue_service()
        recent_tasks = []

        # Get recent tasks from the queue service (last 50)
        completed_tasks = sorted(
            queue_service.completed_tasks.items(), key=lambda x: x[1].completed_at or x[1].created_at, reverse=True
        )

        for task_id, task in completed_tasks[:50]:
            task_info = task.to_dict()
            recent_tasks.append(task_info)

        # Also include completed external tasks
        external_completed = sorted(
            [
                (tid, task)
                for tid, task in queue_service.external_tasks.items()
                if task.status.value in ["completed", "failed"]
            ],
            key=lambda x: x[1].completed_at or x[1].created_at,
            reverse=True,
        )

        for task_id, task in external_completed[:25]:  # Include up to 25 external tasks
            task_info = task.to_dict()
            recent_tasks.append(task_info)

        # Sort all tasks together by completion/creation time
        recent_tasks.sort(
            key=lambda x: x.get("completed_at") or x.get("created_at") or datetime.min.isoformat(), reverse=True
        )

        return recent_tasks[:50]  # Return max 50 total tasks
    except Exception as e:
        logger.error(f"Error getting recent tasks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get recent tasks")


@router.get("/task/{task_id}")
async def get_task_status(task_id: str) -> Dict[str, Any]:
    """Get status of a specific task"""
    try:
        queue_service = get_background_queue_service()
        task = queue_service.get_task(task_id)

        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        return task.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting task status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get task status")


@router.get("/stream/{stream_id}/tasks")
async def get_stream_tasks(stream_id: int) -> Dict[str, Any]:
    """Get all tasks for a specific stream"""
    try:
        queue_service = get_background_queue_service()

        # Get all tasks (active, completed, external) for this stream
        stream_tasks = {"active": [], "completed": [], "external": []}

        # Check active tasks
        for task_id, task in queue_service.active_tasks.items():
            if task.payload.get("stream_id") == stream_id:
                stream_tasks["active"].append(task.to_dict())

        # Check completed tasks
        for task_id, task in queue_service.completed_tasks.items():
            if task.payload.get("stream_id") == stream_id:
                stream_tasks["completed"].append(task.to_dict())

        # Check external tasks
        for task_id, task in queue_service.external_tasks.items():
            if task.payload.get("stream_id") == stream_id:
                stream_tasks["external"].append(task.to_dict())

        return stream_tasks
    except Exception as e:
        logger.error(f"Error getting stream tasks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get stream tasks")


@router.post("/cancel-stream/{stream_id}")
async def cancel_stream_tasks(stream_id: int) -> Dict[str, Any]:
    """Cancel all tasks for a specific stream"""
    try:
        queue_service = get_background_queue_service()
        cancelled_count = 0

        # Cancel active tasks for this stream
        tasks_to_cancel = []
        for task_id, task in queue_service.active_tasks.items():
            if task.payload.get("stream_id") == stream_id:
                tasks_to_cancel.append(task_id)

        # Cancel external tasks for this stream
        external_to_cancel = []
        for task_id, task in queue_service.external_tasks.items():
            if task.payload.get("stream_id") == stream_id and task.status.value in ["running", "pending"]:
                external_to_cancel.append(task_id)

        # Cancel the tasks using the queue manager
        for task_id in tasks_to_cancel:
            try:
                await queue_service.queue_manager.mark_task_completed(task_id, success=False)
                cancelled_count += 1
            except Exception as e:
                logger.warning(f"Failed to cancel task {task_id}: {e}")

        # Mark external tasks as cancelled
        for task_id in external_to_cancel:
            try:
                queue_service.complete_external_task(task_id, success=False)
                cancelled_count += 1
            except Exception as e:
                logger.warning(f"Failed to cancel external task {task_id}: {e}")

        return {"success": True, "cancelled_count": cancelled_count, "stream_id": stream_id}
    except Exception as e:
        logger.error(f"Error cancelling stream tasks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to cancel stream tasks")


@router.post("/enqueue/recording-post-processing")
async def enqueue_recording_post_processing(
    stream_id: int,
    recording_id: int,
    ts_file_path: str,
    output_dir: str,
    streamer_name: str,
    started_at: str,
    cleanup_ts_file: bool = True,
) -> Dict[str, Any]:
    """Enqueue a recording post-processing chain"""
    try:
        from app.services.init.background_queue_init import enqueue_recording_post_processing

        task_ids = await enqueue_recording_post_processing(
            stream_id=stream_id,
            recording_id=recording_id,
            ts_file_path=ts_file_path,
            output_dir=output_dir,
            streamer_name=streamer_name,
            started_at=started_at,
            cleanup_ts_file=cleanup_ts_file,
        )

        return {"success": True, "task_ids": task_ids, "stream_id": stream_id}
    except Exception as e:
        logger.error(f"Error enqueuing recording post-processing: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to enqueue recording post-processing")


@router.post("/enqueue/metadata-generation")
async def enqueue_metadata_generation(
    stream_id: int, recording_id: int, mp4_file_path: str, output_dir: str, streamer_name: str, started_at: str
) -> Dict[str, Any]:
    """Enqueue metadata generation tasks"""
    try:
        from app.services.init.background_queue_init import enqueue_metadata_generation

        task_ids = await enqueue_metadata_generation(
            stream_id=stream_id,
            recording_id=recording_id,
            mp4_file_path=mp4_file_path,
            output_dir=output_dir,
            streamer_name=streamer_name,
            started_at=started_at,
        )

        return {"success": True, "task_ids": task_ids, "stream_id": stream_id}
    except Exception as e:
        logger.error(f"Error enqueuing metadata generation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to enqueue metadata generation")


@router.post("/enqueue/thumbnail-generation")
async def enqueue_thumbnail_generation(
    stream_id: int, recording_id: int, mp4_file_path: str, output_dir: str, streamer_name: str, started_at: str
) -> Dict[str, Any]:
    """Enqueue thumbnail generation task"""
    try:
        from app.services.init.background_queue_init import enqueue_thumbnail_generation

        task_id = await enqueue_thumbnail_generation(
            stream_id=stream_id,
            recording_id=recording_id,
            mp4_file_path=mp4_file_path,
            output_dir=output_dir,
            streamer_name=streamer_name,
            started_at=started_at,
        )

        return {"success": True, "task_id": task_id, "stream_id": stream_id}
    except Exception as e:
        logger.error(f"Error enqueuing thumbnail generation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to enqueue thumbnail generation")


@router.post("/cleanup-stuck-tasks")
async def cleanup_stuck_tasks() -> Dict[str, Any]:
    """Clean up tasks that are stuck in pending state for too long"""
    try:
        queue_service = get_background_queue_service()
        cleanup_count = 0
        now = datetime.now(timezone.utc)

        # Clean up tasks older than 1 hour that are still pending
        tasks_to_cleanup = []
        for task_id, task in queue_service.active_tasks.items():
            # Handle both enum and string status values
            status_value = task.status.value if hasattr(task.status, "value") else str(task.status)
            if status_value == "pending":
                # Make both timestamps timezone-aware for comparison
                task_created = task.created_at
                if task_created.tzinfo is None:
                    task_created = task_created.replace(tzinfo=timezone.utc)

                task_age_hours = (now - task_created).total_seconds() / 3600
                if task_age_hours > 1:  # More than 1 hour old
                    tasks_to_cleanup.append((task_id, task.task_type, task_age_hours))

        # Clean up stuck external tasks
        external_to_cleanup = []
        for task_id, task in queue_service.external_tasks.items():
            if task.status.value in ["pending", "running"]:
                # Make both timestamps timezone-aware for comparison
                task_created = task.created_at
                if task_created.tzinfo is None:
                    task_created = task_created.replace(tzinfo=timezone.utc)

                task_age_hours = (now - task_created).total_seconds() / 3600
                if task_age_hours > 2:  # More than 2 hours old for external tasks
                    external_to_cleanup.append((task_id, task.task_type, task_age_hours))

        # Clean up internal tasks
        for task_id, task_type, age_hours in tasks_to_cleanup:
            try:
                await queue_service.queue_manager.mark_task_completed(task_id, success=False)
                cleanup_count += 1
                logger.info(f"Cleaned up stuck task {task_id} ({task_type}) - age: {age_hours:.1f}h")
            except Exception as e:
                logger.warning(f"Failed to cleanup task {task_id}: {e}")

        # Clean up external tasks
        for task_id, task_type, age_hours in external_to_cleanup:
            try:
                queue_service.complete_external_task(task_id, success=False)
                cleanup_count += 1
                logger.info(f"Cleaned up stuck external task {task_id} ({task_type}) - age: {age_hours:.1f}h")
            except Exception as e:
                logger.warning(f"Failed to cleanup external task {task_id}: {e}")

        return {
            "success": True,
            "cleaned_up_count": cleanup_count,
            "internal_tasks": len(tasks_to_cleanup),
            "external_tasks": len(external_to_cleanup),
        }
    except Exception as e:
        logger.error(f"Error cleaning up stuck tasks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to clean up stuck tasks")
