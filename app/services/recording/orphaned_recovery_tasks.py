"""
Background task handler for orphaned recording recovery checks

This module provides task handlers that run orphaned recovery checks
when triggered by events (like post-processing completion) rather than
on a time-based schedule.
"""

import logging
from typing import Dict, Any

# Configuration constants
ORPHANED_RECOVERY_TIMEOUT_SECONDS = 120  # 2 minutes timeout for recovery operations
MAX_CONCURRENT_ORPHANED_CHECKS = 3  # Maximum concurrent orphaned recovery checks

logger = logging.getLogger("streamvault")


async def handle_orphaned_recovery_check(task_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle background orphaned recovery check task

    Args:
        task_data: Dict containing:
            - max_age_hours: int - Maximum age of recordings to check
            - trigger_reason: str - Reason for the check

    Returns:
        Dict with task result
    """
    try:
        max_age_hours = task_data.get("max_age_hours", 48)
        trigger_reason = task_data.get("trigger_reason", "background_check")

        logger.info(f"🔍 ORPHANED_RECOVERY_CHECK_START: max_age={max_age_hours}h, reason={trigger_reason}")

        # PRODUCTION FIX: Check if too many orphaned checks are already running
        from app.services.background_queue_service import get_background_queue_service
        queue_service = get_background_queue_service()
        if queue_service:
            active_tasks = queue_service.get_active_tasks()
            orphaned_check_count = sum(1 for task in active_tasks.values()
                                       if task.task_type == 'orphaned_recovery_check')

            if orphaned_check_count > MAX_CONCURRENT_ORPHANED_CHECKS:  # Limit to max 3 concurrent orphaned checks
                logger.warning(f"🔍 ORPHANED_RECOVERY_CHECK_SKIP: Too many orphaned checks running ({orphaned_check_count}), skipping this one")
                return {
                    "success": True,
                    "orphaned_found": 0,
                    "recovery_triggered": 0,
                    "message": f"Skipped - too many orphaned checks running ({orphaned_check_count})"
                }

        # Import the orphaned recovery service
        from app.services.recording.orphaned_recovery_service import get_orphaned_recovery_service

        recovery_service = await get_orphaned_recovery_service()

        # Get statistics first
        stats = await recovery_service.get_orphaned_statistics(max_age_hours=max_age_hours)

        if stats.get("total_orphaned", 0) == 0:
            logger.debug("🔍 ORPHANED_RECOVERY_CHECK: No orphaned recordings found")
            return {
                "success": True,
                "orphaned_found": 0,
                "recovery_triggered": 0,
                "message": "No orphaned recordings found"
            }

        logger.info(f"🔍 ORPHANED_RECOVERY_CHECK: Found {stats['total_orphaned']} orphaned recordings")

        # PRODUCTION FIX: Add timeout for orphaned recovery to prevent hanging
        import asyncio
        try:
            # Trigger recovery for orphaned recordings with timeout
            result = await asyncio.wait_for(
                recovery_service.scan_and_recover_orphaned_recordings(
                    max_age_hours=max_age_hours,
                    dry_run=False
                ),
                timeout=ORPHANED_RECOVERY_TIMEOUT_SECONDS  # 2 minutes timeout
            )
        except asyncio.TimeoutError:
            logger.warning("🔍 ORPHANED_RECOVERY_CHECK_TIMEOUT: Recovery check timed out after 2 minutes")
            return {
                "success": False,
                "orphaned_found": stats.get("total_orphaned", 0),
                "recovery_triggered": 0,
                "message": "Orphaned recovery check timed out",
                "error": "timeout"
            }

        logger.info(f"🔍 ORPHANED_RECOVERY_CHECK_COMPLETE: {result['recovery_triggered']} recoveries triggered")

        # Send notification if significant number of orphaned recordings were found
        if result["recovery_triggered"] > 0:
            try:
                from app.services.websocket.websocket_service import websocket_service
                if websocket_service:
                    await websocket_service.send_system_notification({
                        "type": "orphaned_recovery_auto_triggered",
                        "message": f"Automatic orphaned recovery: {result['recovery_triggered']} recordings processed",
                        "data": {
                            "recovery_triggered": result["recovery_triggered"],
                            "trigger_reason": trigger_reason,
                            "statistics": stats
                        }
                    })
            except Exception as e:
                logger.debug(f"Could not send WebSocket notification: {e}")

        return {
            "success": True,
            "orphaned_found": stats.get("total_orphaned", 0),
            "recovery_triggered": result["recovery_triggered"],
            "message": f"Orphaned recovery check completed: {result['recovery_triggered']} recoveries triggered",
            "statistics": stats,
            "recovery_result": result
        }

    except Exception as e:
        logger.error(f"🔍 ORPHANED_RECOVERY_CHECK_ERROR: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "message": f"Orphaned recovery check failed: {str(e)}"
        }


# Register the task handler
TASK_HANDLERS = {
    "orphaned_recovery_check": handle_orphaned_recovery_check
}
