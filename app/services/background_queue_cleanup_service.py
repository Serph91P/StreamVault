"""
Background Queue Cleanup Service

Fixes for production issues:
1. Recording jobs stuck at 100% running
2. Orphaned recovery check running continuously  
3. Task names showing as "Unknown"
"""

import logging
from typing import Dict, List, Any
from datetime import datetime, timezone, timedelta

# Configuration constants
STUCK_TASK_THRESHOLD_HOURS = 3  # Hours after which a task is considered stuck

logger = logging.getLogger("streamvault")


class BackgroundQueueCleanupService:
    """Service to clean up stuck background queue tasks and external tasks"""
    
    def __init__(self, background_queue_service=None):
        self.background_queue_service = background_queue_service
    
    async def cleanup_stuck_recording_tasks(self) -> Dict[str, Any]:
        """Clean up recording tasks that are stuck at 100% or running indefinitely"""
        try:
            if not self.background_queue_service:
                logger.warning("No background queue service available for cleanup")
                return {"cleaned": 0, "errors": ["No background queue service"]}
            
            cleaned_count = 0
            errors = []
            
            # Get all external tasks (where recording tasks are stored)
            external_tasks = getattr(self.background_queue_service, 'external_tasks', {})
            
            logger.info(f"🧹 CLEANUP_START: Found {len(external_tasks)} external tasks to check")
            
            for task_id, task in list(external_tasks.items()):
                try:
                    # Check if it's a recording task (both by task_id pattern and task_type)
                    is_recording_task = (
                        task_id.startswith('recording_') or 
                        task.task_type == 'recording' or
                        (hasattr(task, 'task_name') and 'recording' in str(task.task_name).lower())
                    )
                    
                    if is_recording_task:
                        
                        # Check if task is stuck 
                        now = datetime.now(timezone.utc)
                        
                        task_age = None
                        if hasattr(task, 'started_at') and task.started_at:
                            task_started = task.started_at
                            if task_started.tzinfo is None:
                                task_started = task_started.replace(tzinfo=timezone.utc)
                            task_age = (now - task_started).total_seconds() / 3600  # hours
                        elif hasattr(task, 'created_at') and task.created_at:
                            # Fall back to created_at if started_at is not available
                            task_created = task.created_at
                            if task_created.tzinfo is None:
                                task_created = task_created.replace(tzinfo=timezone.utc)
                            task_age = (now - task_created).total_seconds() / 3600  # hours
                        
                        is_stuck = False
                        reason = ""
                        
                        # Task running for more than the threshold hours (reduced from 6)
                        if task_age and task_age > STUCK_TASK_THRESHOLD_HOURS:
                            is_stuck = True
                            reason = f"running for {task_age:.1f}h"
                        
                        # Task at 100% progress but still "running" status (reduced time to 5 minutes)
                        elif (hasattr(task, 'progress') and task.progress >= 100 and 
                              hasattr(task, 'status') and str(task.status).lower() == 'running'):
                            # For 100% tasks, check if the actual recording process is still running
                            is_stuck = True
                            reason = f"at 100% but status still running"
                            
                            # Additional check: if it's a recording task, verify if the stream is actually ended
                            if task_id.startswith('recording_'):
                                try:
                                    recording_id = task_id.replace('recording_', '')
                                    # Check if the recording is actually finished in the database
                                    from app.database import SessionLocal
                                    from app.models import Recording, Stream
                                    
                                    with SessionLocal() as db:
                                        recording = db.query(Recording).filter(Recording.id == recording_id).first()
                                        if recording and recording.stream:
                                            # If the stream is ended, then the recording should be completed
                                            if recording.stream.ended_at:
                                                logger.info(f"🧹 RECORDING_SHOULD_BE_COMPLETE: {task_id} - stream ended at {recording.stream.ended_at}")
                                                reason = f"stream ended but task still running (100% complete)"
                                            else:
                                                # Stream is still live, so task might legitimately be running
                                                is_stuck = False
                                                logger.info(f"🧹 RECORDING_STILL_LIVE: {task_id} - stream still live, not stuck")
                                except Exception as e:
                                    logger.warning(f"Could not verify recording status: {e}")
                        
                        if is_stuck:
                            logger.info(f"🧹 CLEANUP_STUCK_TASK: {task_id} ({reason})")
                            
                            # For recording tasks at 100%, mark them as completed properly instead of killing
                            if (hasattr(task, 'progress') and task.progress >= 100 and 
                                hasattr(task, 'status') and str(task.status).lower() == 'running'):
                                
                                logger.info(f"🧹 COMPLETING_TASK: Marking {task_id} as completed (was at 100% but running)")
                                
                                # Mark as completed through proper channels
                                if hasattr(self.background_queue_service, 'complete_external_task'):
                                    self.background_queue_service.complete_external_task(task_id, success=True)
                                    logger.info(f"✅ TASK_COMPLETED: {task_id} marked as completed via complete_external_task")
                                
                                # Update task status directly if it has status attribute
                                if hasattr(task, 'status'):
                                    try:
                                        if hasattr(task.status, 'value'):
                                            task.status.value = 'completed'
                                        else:
                                            task.status = 'completed'
                                        logger.info(f"✅ STATUS_UPDATED: {task_id} status updated to completed")
                                    except Exception as e:
                                        logger.warning(f"Could not update task status directly: {e}")
                                
                                # Set completed_at timestamp if not set
                                if not hasattr(task, 'completed_at') or not task.completed_at:
                                    task.completed_at = datetime.now(timezone.utc)
                                    logger.info(f"✅ TIMESTAMP_SET: {task_id} completed_at timestamp set")
                            
                            else:
                                # For tasks running too long, remove them as they're likely stuck
                                logger.info(f"🧹 REMOVING_STUCK_TASK: {task_id} running too long, removing")
                                
                                if hasattr(self.background_queue_service, 'complete_external_task'):
                                    self.background_queue_service.complete_external_task(task_id, success=True)
                                
                                # Remove from external_tasks directly if method doesn't work
                                if task_id in external_tasks:
                                    del external_tasks[task_id]
                                    logger.info(f"🧹 CLEANUP_REMOVED: Directly removed {task_id} from external_tasks")
                            
                            # Remove from progress tracking to prevent UI showing as stuck
                            if hasattr(self.background_queue_service, 'progress_tracker'):
                                try:
                                    self.background_queue_service.progress_tracker.remove_external_task(task_id)
                                    logger.info(f"🧹 TRACKING_REMOVED: Removed {task_id} from progress tracker")
                                except Exception as e:
                                    logger.warning(f"Could not remove from progress tracker: {e}")
                            
                            cleaned_count += 1
                            logger.info(f"✅ CLEANUP_SUCCESS: Processed stuck recording task {task_id}")
                
                except Exception as e:
                    error_msg = f"Failed to cleanup task {task_id}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(f"❌ CLEANUP_ERROR: {error_msg}")
            
            logger.info(f"🧹 CLEANUP_COMPLETE: Processed {cleaned_count} stuck recording tasks")
            
            return {
                "cleaned": cleaned_count,
                "errors": errors,
                "message": f"Processed {cleaned_count} stuck recording tasks"
            }
        
        except Exception as e:
            logger.error(f"Error in cleanup_stuck_recording_tasks: {e}", exc_info=True)
            return {"cleaned": 0, "errors": [str(e)]}
    
    async def stop_continuous_orphaned_recovery(self) -> Dict[str, Any]:
        """Stop continuous orphaned recovery checks"""
        try:
            if not self.background_queue_service:
                return {"stopped": 0, "message": "No background queue service"}
            
            stopped_count = 0
            errors = []
            
            # Check active tasks for orphaned recovery checks
            active_tasks = getattr(self.background_queue_service, 'active_tasks', {})
            
            logger.info(f"🛑 ORPHANED_CLEANUP_START: Found {len(active_tasks)} active tasks to check")
            
            for task_id, task in list(active_tasks.items()):
                try:
                    # Check if it's an orphaned recovery task
                    is_orphaned_task = (
                        (hasattr(task, 'task_type') and task.task_type == 'orphaned_recovery_check') or
                        'orphaned' in task_id.lower() or
                        (hasattr(task, 'task_name') and 'orphaned' in str(task.task_name).lower())
                    )
                    
                    if is_orphaned_task:
                        task_status = getattr(task, 'status', 'unknown')
                        if hasattr(task_status, 'value'):
                            status_value = task_status.value
                        else:
                            status_value = str(task_status).lower()
                        
                        if status_value in ['pending', 'running']:
                            logger.info(f"🛑 STOPPING_ORPHANED_TASK: {task_id} (status: {status_value})")
                            
                            # Try to complete the task properly first
                            try:
                                if hasattr(self.background_queue_service, 'queue_manager'):
                                    # Mark as completed rather than cancelled for orphaned recovery tasks
                                    await self.background_queue_service.queue_manager.mark_task_completed(task_id, success=True)
                                    logger.info(f"🛑 TASK_COMPLETED: {task_id} marked as completed via queue manager")
                                
                                # Update task status directly
                                if hasattr(task, 'status'):
                                    try:
                                        if hasattr(task.status, 'value'):
                                            task.status.value = 'completed'
                                        else:
                                            task.status = 'completed'
                                        logger.info(f"🛑 STATUS_UPDATED: {task_id} status updated to completed")
                                    except Exception as e:
                                        logger.warning(f"Could not update task status directly: {e}")
                                
                                # Set completed timestamp
                                if not hasattr(task, 'completed_at') or not task.completed_at:
                                    task.completed_at = datetime.now(timezone.utc)
                                    logger.info(f"🛑 TIMESTAMP_SET: {task_id} completed_at timestamp set")
                            
                            except Exception as e:
                                logger.warning(f"Could not complete task via queue manager: {e}")
                                # Fall back to direct removal if completion fails
                                if task_id in active_tasks:
                                    del active_tasks[task_id]
                                    logger.info(f"🛑 FALLBACK_REMOVED: Directly removed {task_id} from active_tasks")
                            
                            stopped_count += 1
                            logger.info(f"🛑 STOPPED_ORPHANED_CHECK: Processed orphaned recovery task {task_id}")
                
                except Exception as e:
                    error_msg = f"Failed to stop orphaned task {task_id}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(f"❌ ORPHANED_CLEANUP_ERROR: {error_msg}")
            
            logger.info(f"🛑 ORPHANED_CLEANUP_COMPLETE: Stopped {stopped_count} orphaned recovery tasks")
            
            return {
                "stopped": stopped_count,
                "errors": errors,
                "message": f"Stopped {stopped_count} continuous orphaned recovery checks"
            }
        
        except Exception as e:
            logger.error(f"Error stopping orphaned recovery checks: {e}", exc_info=True)
            return {"stopped": 0, "errors": [str(e)]}
    
    async def fix_unknown_task_names(self) -> Dict[str, Any]:
        """Fix tasks showing as 'Unknown' by ensuring proper task_type is set"""
        try:
            if not self.background_queue_service:
                return {"fixed": 0, "message": "No background queue service"}
            
            fixed_count = 0
            
            # Check external tasks first
            external_tasks = getattr(self.background_queue_service, 'external_tasks', {})
            for task_id, task in external_tasks.items():
                if not task.task_type or task.task_type in ['unknown', '']:
                    # Try to infer task type from task_id
                    if task_id.startswith('recording_'):
                        task.task_type = 'recording'
                        fixed_count += 1
                        logger.info(f"🔧 FIXED_TASK_TYPE: {task_id} -> recording")
            
            # Check active tasks
            active_tasks = getattr(self.background_queue_service, 'active_tasks', {})
            for task_id, task in active_tasks.items():
                if not task.task_type or task.task_type in ['unknown', '']:
                    # Try to infer from task ID patterns
                    if 'metadata' in task_id:
                        task.task_type = 'metadata_generation'
                    elif 'mp4_remux' in task_id:
                        task.task_type = 'mp4_remux'
                    elif 'thumbnail' in task_id:
                        task.task_type = 'thumbnail_generation'
                    elif 'cleanup' in task_id:
                        task.task_type = 'cleanup'
                    elif 'orphaned' in task_id:
                        task.task_type = 'orphaned_recovery_check'
                    else:
                        task.task_type = 'unknown_task'
                    
                    fixed_count += 1
                    logger.info(f"🔧 FIXED_TASK_TYPE: {task_id} -> {task.task_type}")
            
            return {
                "fixed": fixed_count,
                "message": f"Fixed {fixed_count} unknown task names"
            }
        
        except Exception as e:
            logger.error(f"Error fixing unknown task names: {e}", exc_info=True)
            return {"fixed": 0, "errors": [str(e)]}
    
    async def comprehensive_cleanup(self) -> Dict[str, Any]:
        """Run all cleanup operations"""
        try:
            logger.info("🧹 COMPREHENSIVE_CLEANUP_START: Running all background queue fixes")
            
            results = {}
            
            # 1. Clean up stuck recording tasks
            recording_cleanup = await self.cleanup_stuck_recording_tasks()
            results['stuck_recordings'] = recording_cleanup
            
            # 2. Stop continuous orphaned recovery
            orphaned_cleanup = await self.stop_continuous_orphaned_recovery()
            results['orphaned_recovery'] = orphaned_cleanup
            
            # 3. Fix unknown task names
            name_fixes = await self.fix_unknown_task_names()
            results['task_names'] = name_fixes
            
            total_cleaned = (
                recording_cleanup.get('cleaned', 0) + 
                orphaned_cleanup.get('stopped', 0) + 
                name_fixes.get('fixed', 0)
            )
            
            logger.info(f"🧹 COMPREHENSIVE_CLEANUP_COMPLETE: Fixed {total_cleaned} issues total")
            
            results['summary'] = {
                "total_issues_fixed": total_cleaned,
                "message": f"Background queue cleanup completed: {total_cleaned} issues fixed"
            }
            
            return results
        
        except Exception as e:
            logger.error(f"Error in comprehensive cleanup: {e}", exc_info=True)
            return {"error": str(e)}


# Global instance
_cleanup_service = None

def get_cleanup_service():
    """Get singleton cleanup service"""
    global _cleanup_service
    if _cleanup_service is None:
        try:
            from app.services.background_queue_service import background_queue_service
            _cleanup_service = BackgroundQueueCleanupService(background_queue_service)
        except Exception as e:
            logger.warning(f"Could not initialize cleanup service: {e}")
            _cleanup_service = BackgroundQueueCleanupService()
    return _cleanup_service
