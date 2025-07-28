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
                    # Check if it's a recording task
                    if task_id.startswith('recording_') and task.task_type == 'recording':
                        
                        # Check if task is stuck (running for more than 6 hours or at 100% for more than 30 minutes)
                        now = datetime.now(timezone.utc)
                        
                        task_age = None
                        if task.started_at:
                            task_started = task.started_at
                            if task_started.tzinfo is None:
                                task_started = task_started.replace(tzinfo=timezone.utc)
                            task_age = (now - task_started).total_seconds() / 3600  # hours
                        
                        is_stuck = False
                        reason = ""
                        
                        # Task running for more than 6 hours
                        if task_age and task_age > 6:
                            is_stuck = True
                            reason = f"running for {task_age:.1f}h"
                        
                        # Task at 100% for more than 30 minutes
                        elif task.progress >= 100 and task.status.value == 'running':
                            if task.completed_at:
                                completion_time = task.completed_at
                                if completion_time.tzinfo is None:
                                    completion_time = completion_time.replace(tzinfo=timezone.utc)
                                time_at_100 = (now - completion_time).total_seconds() / 60  # minutes
                                
                                if time_at_100 > 30:
                                    is_stuck = True
                                    reason = f"at 100% for {time_at_100:.1f}m"
                        
                        if is_stuck:
                            logger.info(f"🧹 CLEANUP_STUCK_TASK: {task_id} ({reason})")
                            
                            # Complete and remove the stuck task
                            self.background_queue_service.complete_external_task(task_id, success=True)
                            
                            # Also remove from tracking to prevent UI showing as stuck
                            if hasattr(self.background_queue_service, 'progress_tracker'):
                                self.background_queue_service.progress_tracker.remove_external_task(task_id)
                            
                            cleaned_count += 1
                            logger.info(f"✅ CLEANUP_SUCCESS: Cleaned stuck recording task {task_id}")
                
                except Exception as e:
                    error_msg = f"Failed to cleanup task {task_id}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(f"❌ CLEANUP_ERROR: {error_msg}")
            
            logger.info(f"🧹 CLEANUP_COMPLETE: Cleaned {cleaned_count} stuck recording tasks")
            
            return {
                "cleaned": cleaned_count,
                "errors": errors,
                "message": f"Cleaned up {cleaned_count} stuck recording tasks"
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
            
            # Check active tasks for orphaned recovery checks
            active_tasks = getattr(self.background_queue_service, 'active_tasks', {})
            
            for task_id, task in list(active_tasks.items()):
                if task.task_type == 'orphaned_recovery_check' and task.status.value in ['pending', 'running']:
                    # Cancel the task
                    if hasattr(self.background_queue_service, 'queue_manager'):
                        await self.background_queue_service.queue_manager.mark_task_completed(task_id, success=False)
                    
                    stopped_count += 1
                    logger.info(f"🛑 STOPPED_ORPHANED_CHECK: Cancelled orphaned recovery task {task_id}")
            
            return {
                "stopped": stopped_count,
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
