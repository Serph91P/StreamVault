"""
Orphaned Recovery Service - Compatibility wrapper for UnifiedRecoveryService

This module provides backward compatibility for code that still imports
the old orphaned_recovery_service. It wraps the new UnifiedRecoveryService.

DEPRECATED: New code should use UnifiedRecoveryService directly.
"""

import logging
from typing import Dict, Any
from app.services.recording.unified_recovery_service import UnifiedRecoveryService

logger = logging.getLogger("streamvault")

# Singleton instance
_recovery_service_instance: UnifiedRecoveryService | None = None


async def get_orphaned_recovery_service() -> UnifiedRecoveryService:
    """
    Get singleton instance of UnifiedRecoveryService.

    DEPRECATED: Use UnifiedRecoveryService directly instead.
    This function exists for backward compatibility only.

    Returns:
        UnifiedRecoveryService instance
    """
    global _recovery_service_instance

    if _recovery_service_instance is None:
        logger.debug("Creating new UnifiedRecoveryService instance (via compatibility wrapper)")
        _recovery_service_instance = UnifiedRecoveryService()

    return _recovery_service_instance


class OrphanedRecoveryService:
    """
    DEPRECATED: Compatibility wrapper for UnifiedRecoveryService.

    This class exists only for backward compatibility. New code should use
    UnifiedRecoveryService directly.
    """

    def __init__(self):
        logger.warning("OrphanedRecoveryService is deprecated. Use UnifiedRecoveryService instead.")
        self._service = UnifiedRecoveryService()

    async def get_orphaned_statistics(self, max_age_hours: int = 72) -> Dict[str, Any]:
        """Get statistics about orphaned recordings (compatibility wrapper)"""
        stats = await self._service.comprehensive_recovery_scan(max_age_hours=max_age_hours, dry_run=True)

        return {
            "total_orphaned": stats.orphaned_segments + stats.failed_post_processing,
            "total_orphaned_segments": stats.orphaned_segments,
            "failed_post_processing": stats.failed_post_processing,
            "total_size_gb": stats.total_size_gb,
            "by_streamer": {}  # Not supported in new service
        }

    async def scan_and_recover_orphaned_recordings(
        self,
        max_age_hours: int = 72,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """Scan and recover orphaned recordings (compatibility wrapper)"""
        stats = await self._service.comprehensive_recovery_scan(max_age_hours=max_age_hours, dry_run=dry_run)

        return {
            "success": True,
            "orphaned_found": stats.orphaned_segments,
            "recovered": stats.recovered_recordings,
            "triggered_post_processing": stats.triggered_post_processing,
            "total_size_gb": stats.total_size_gb
        }

    async def cleanup_orphaned_segments(
        self,
        max_age_hours: int = 72,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """Cleanup orphaned segment directories (compatibility wrapper)"""
        # Use comprehensive scan which includes segment cleanup
        stats = await self._service.comprehensive_recovery_scan(max_age_hours=max_age_hours, dry_run=dry_run)

        return {
            "success": True,
            "segments_cleaned": stats.orphaned_segments,
            "total_size_gb": stats.total_size_gb
        }
