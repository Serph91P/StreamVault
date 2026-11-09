"""
Simple Recovery Service

Creates simple metadata_generation tasks without dependencies.
These work reliably compared to complex dependency chains.
"""

import logging
from typing import Dict, Any, TYPE_CHECKING
from datetime import datetime, timezone


if TYPE_CHECKING:
    from ..services.recording.unified_recovery_service import UnifiedRecoveryService

logger = logging.getLogger("streamvault")


async def run_simple_reliable_recovery(
    unified_service: "UnifiedRecoveryService | None" = None,
) -> Dict[str, Any]:
    """
    Performs simple, reliable recovery.

    Uses only single metadata_generation tasks without dependencies,
    as these are more reliable than complex chains.
    """
    results = {
        "start_time": datetime.now(timezone.utc).isoformat(),
        "simple_recovery": None,
        "total_recoveries": 0,
        "success": False,
    }

    try:
        logger.info("🔧 Starting simple reliable recovery...")

        # Find failed recordings with Unified Recovery Service
        from ..services.recording.unified_recovery_service import (
            get_unified_recovery_service,
        )

        if unified_service is None:
            unified_service = await get_unified_recovery_service()

        # Run only scan (dry_run=True) to find failed recordings
        unified_stats = await unified_service.comprehensive_recovery_scan(
            max_age_hours=72,
            dry_run=True,  # Only scan, don't create complex chains
        )

        failed_count = unified_stats.failed_post_processing
        logger.info(f"🔍 Found {failed_count} failed post-processing recordings")

        if failed_count > 0:
            # Use the scan results to create full post-processing chains
            recovery_triggered = await create_full_recovery_chains(unified_service)

            results["simple_recovery"] = {
                "success": True,
                "failed_found": failed_count,
                "recovery_triggered": recovery_triggered,
                "method": "full_post_processing_chains",
            }
            results["total_recoveries"] = recovery_triggered

            logger.info(
                f"✅ Simple recovery: {recovery_triggered} metadata_generation tasks created"
            )
        else:
            results["simple_recovery"] = {
                "success": True,
                "failed_found": 0,
                "recovery_triggered": 0,
                "method": "full_post_processing_chains",
            }
            logger.info("ℹ️ No failed recordings found")

        results["end_time"] = datetime.now(timezone.utc).isoformat()
        results["success"] = True

        logger.info(
            f"🎉 Simple recovery completed: {results['total_recoveries']} full post-processing chains created"
        )
        return results

    except Exception as e:
        results["end_time"] = datetime.now(timezone.utc).isoformat()
        results["success"] = False
        results["error"] = str(e)
        logger.error(f"❌ Simple recovery failed: {e}")
        return results


async def create_full_recovery_chains(unified_service: "UnifiedRecoveryService") -> int:
    """
    Creates full post-processing chains for failed recordings.

    Uses the proper enqueue_recording_post_processing to trigger complete chains
    with mp4_remux, chapters_generation, etc. - not just metadata.

    Args:
        unified_service: The unified recovery service instance

    Returns:
        Number of post-processing chains created.
    """
    return await unified_service.retry_failed_recordings()
