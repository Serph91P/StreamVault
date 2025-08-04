#!/usr/bin/env python3
"""
Emergency Script to Clear Stuck Tasks

This script immediately clears all stuck orphaned recovery tasks 
and allows post-processing to resume.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add the app directory to the Python path
app_dir = Path(__file__).parent / "app"
sys.path.insert(0, str(app_dir))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def clear_stuck_tasks():
    """Clear all stuck tasks from the background queue"""
    try:
        # Import the background queue service
        from app.services.background_queue_service import get_background_queue_service
        
        queue_service = get_background_queue_service()
        if not queue_service:
            logger.error("❌ Background queue service not available")
            return False
        
        # Get current task statistics
        active_tasks = queue_service.get_active_tasks()
        logger.info(f"📊 Current active tasks: {len(active_tasks)}")
        
        # Count different task types
        task_counts = {}
        orphaned_tasks = []
        other_pending_tasks = []
        
        for task_id, task in active_tasks.items():
            task_type = task.task_type
            task_counts[task_type] = task_counts.get(task_type, 0) + 1
            
            if task_type == 'orphaned_recovery_check':
                orphaned_tasks.append(task_id)
            elif hasattr(task, 'status') and str(task.status).lower() == 'pending':
                # Check if it's a stuck post-processing task
                if task_type in ['mp4_remux', 'thumbnail_generation', 'cleanup_task']:
                    other_pending_tasks.append((task_id, task_type))
        
        logger.info(f"📊 Task breakdown: {task_counts}")
        logger.info(f"🧹 Found {len(orphaned_tasks)} stuck orphaned recovery tasks")
        logger.info(f"🧹 Found {len(other_pending_tasks)} stuck post-processing tasks")
        
        # Clear stuck orphaned recovery tasks
        cleared_count = 0
        for task_id in orphaned_tasks:
            try:
                # Mark as completed to remove from active tasks
                queue_service.complete_external_task(task_id, success=True)
                cleared_count += 1
                logger.info(f"✅ Cleared stuck orphaned task: {task_id}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to clear orphaned task {task_id}: {e}")
        
        # Clear stuck post-processing tasks (reset to pending so they can be picked up)
        reset_count = 0
        for task_id, task_type in other_pending_tasks:
            try:
                # Reset task to pending so it can be processed
                task = queue_service.get_task(task_id)
                if task:
                    queue_service.update_task_status(task_id, 'pending')
                    logger.info(f"🔄 Reset stuck {task_type} task: {task_id}")
                    reset_count += 1
            except Exception as e:
                logger.warning(f"⚠️ Failed to reset task {task_id}: {e}")
        
        # Also clear any old completed tasks
        queue_service.cleanup_old_tasks(max_age_hours=1)
        
        logger.info(f"🧹 CLEANUP_COMPLETE: Cleared {cleared_count} orphaned tasks, reset {reset_count} post-processing tasks")
        
        # Show final statistics
        remaining_active = queue_service.get_active_tasks()
        logger.info(f"📊 Remaining active tasks: {len(remaining_active)}")
        
        for task_id, task in remaining_active.items():
            status = getattr(task, 'status', 'unknown')
            logger.info(f"  - {task.task_type} ({task_id[:8]}...): {status}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error during cleanup: {e}", exc_info=True)
        return False


async def main():
    """Main function - Clear stuck tasks without restarting the system"""
    logger.info("🧹 Starting emergency cleanup of stuck tasks (live system repair)...")
    
    # Try to connect to the running background queue service
    try:
        import os
        import sys
        
        # Set environment to match the running application
        os.environ.setdefault('STREAMVAULT_ENV', 'production')
        
        # Import without initializing a new instance
        from app.services.background_queue_service import get_background_queue_service
        
        # Try to get the existing service instance
        queue_service = get_background_queue_service()
        
        if not queue_service:
            logger.error("❌ No running background queue service found")
            logger.info("💡 The application needs to be running for this script to work")
            return 1
        
        logger.info("✅ Connected to running background queue service")
        
        # Clear stuck tasks
        success = await clear_stuck_tasks()
        
        if success:
            logger.info("✅ Emergency cleanup completed successfully!")
            logger.info("🎯 Post-processing should now resume normally")
            logger.info("📹 maxim's recording will continue uninterrupted")
        else:
            logger.error("❌ Emergency cleanup failed")
            return 1
            
    except ImportError as e:
        logger.error(f"❌ Could not import background queue service: {e}")
        logger.info("💡 Make sure the StreamVault application is running")
        return 1
    except Exception as e:
        logger.error(f"❌ Failed to connect to running system: {e}", exc_info=True)
        logger.info("💡 The application may not be running or there may be a configuration issue")
        return 1
    
    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("🛑 Cleanup interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}", exc_info=True)
        sys.exit(1)
