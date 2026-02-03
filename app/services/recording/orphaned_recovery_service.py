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

# Singleton instance - use OrphanedRecoveryService wrapper for compatibility
_recovery_service_instance: "OrphanedRecoveryService | None" = None


async def get_orphaned_recovery_service() -> "OrphanedRecoveryService":
    """
    Get singleton instance of OrphanedRecoveryService (compatibility wrapper).

    This returns the OrphanedRecoveryService wrapper which provides
    backward-compatible methods that delegate to UnifiedRecoveryService.

    Returns:
        OrphanedRecoveryService instance (wrapper around UnifiedRecoveryService)
    """
    global _recovery_service_instance

    if _recovery_service_instance is None:
        logger.debug("Creating new OrphanedRecoveryService instance (compatibility wrapper)")
        _recovery_service_instance = OrphanedRecoveryService()

    return _recovery_service_instance


class OrphanedRecoveryService:
    """
    Compatibility wrapper for UnifiedRecoveryService.

    This class provides backward-compatible methods that delegate to
    UnifiedRecoveryService for admin endpoints and legacy code.
    """

    def __init__(self):
        self._service = UnifiedRecoveryService()

    async def get_orphaned_statistics(self, max_age_hours: int = 72) -> Dict[str, Any]:
        """Get statistics about orphaned recordings (compatibility wrapper)"""
        stats = await self._service.comprehensive_recovery_scan(max_age_hours=max_age_hours, dry_run=True)

        return {
            "total_orphaned": stats.orphaned_segments + stats.failed_post_processing,
            "total_orphaned_segments": stats.orphaned_segments,
            "failed_post_processing": stats.failed_post_processing,
            "total_size_gb": stats.total_size_gb,
            "by_streamer": {},  # Not supported in new service
        }

    async def scan_and_recover_orphaned_recordings(
        self, max_age_hours: int = 72, dry_run: bool = False, cleanup_segments: bool = True
    ) -> Dict[str, Any]:
        """Scan and recover orphaned recordings (compatibility wrapper)"""
        stats = await self._service.comprehensive_recovery_scan(max_age_hours=max_age_hours, dry_run=dry_run)

        return {
            "success": True,
            "orphaned_found": stats.orphaned_segments,
            "recovered": stats.recovered_recordings,
            "recovery_triggered": stats.triggered_post_processing,
            "recovery_failed": 0,
            "segments_cleaned": stats.orphaned_segments if cleanup_segments else 0,
            "triggered_post_processing": stats.triggered_post_processing,
            "total_size_gb": stats.total_size_gb,
            "orphaned_recordings": [],
            "errors": [],
        }

    async def cleanup_orphaned_segments(self, max_age_hours: int = 72, dry_run: bool = False) -> Dict[str, Any]:
        """Cleanup orphaned segment directories (compatibility wrapper)"""
        # Use comprehensive scan which includes segment cleanup
        stats = await self._service.comprehensive_recovery_scan(max_age_hours=max_age_hours, dry_run=dry_run)

        return {"success": True, "segments_cleaned": stats.orphaned_segments, "total_size_gb": stats.total_size_gb}

    async def _find_orphaned_recordings(self, db, max_age_hours: int = 72):
        """Find orphaned recordings from database (compatibility wrapper)"""
        from datetime import datetime, timedelta
        from sqlalchemy.orm import joinedload
        from app.models import Recording, Stream, Streamer
        
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
        
        # Find recordings that are in 'recording' or 'processing' status but older than cutoff
        orphaned = db.query(Recording).options(
            joinedload(Recording.stream).joinedload(Stream.streamer)
        ).filter(
            Recording.status.in_(["recording", "processing", "failed"]),
            Recording.created_at < cutoff_time
        ).all()
        
        return orphaned

    async def _validate_orphaned_recording(self, recording) -> Dict[str, Any]:
        """Validate if a recording is truly orphaned and can be recovered"""
        import os
        from pathlib import Path
        from datetime import datetime
        
        result = {
            "valid": False,
            "reason": None,
            "file_size": 0,
            "file_age_seconds": 0,
        }
        
        if not recording.path:
            result["reason"] = "No file path"
            return result
            
        file_path = Path(recording.path)
        
        # Check if TS file exists
        if not file_path.exists():
            # Check for segments directory
            segments_dir = file_path.parent / f"{file_path.stem}_segments"
            if segments_dir.exists():
                result["valid"] = True
                result["reason"] = "Segments directory exists"
                return result
            result["reason"] = "File not found"
            return result
        
        # Get file info
        stat = file_path.stat()
        result["file_size"] = stat.st_size
        result["file_age_seconds"] = (datetime.now() - datetime.fromtimestamp(stat.st_mtime)).total_seconds()
        
        # Check if file is too small
        if stat.st_size < 1024:  # Less than 1KB
            result["reason"] = "File too small"
            return result
        
        # Check if MP4 already exists
        mp4_path = file_path.with_suffix(".mp4")
        if mp4_path.exists():
            result["reason"] = "MP4 already exists"
            return result
        
        result["valid"] = True
        return result

    async def _trigger_orphaned_recovery(self, recording, db) -> bool:
        """Trigger recovery for an orphaned recording"""
        from app.services.init.background_queue_init import enqueue_recording_post_processing
        from datetime import datetime
        import os
        
        try:
            if not recording.path:
                return False
                
            # Prepare post-processing payload
            streamer_name = "Unknown"
            if recording.stream and recording.stream.streamer:
                streamer_name = recording.stream.streamer.username
            
            stream_id = recording.stream_id if recording.stream_id else (recording.stream.id if recording.stream else None)
            
            if not stream_id:
                logger.error(f"Cannot trigger recovery for recording {recording.id}: no stream_id")
                return False
            
            output_dir = os.path.dirname(recording.path)
            
            await enqueue_recording_post_processing(
                stream_id=stream_id,
                recording_id=recording.id,
                ts_file_path=recording.path,
                output_dir=output_dir,
                streamer_name=streamer_name,
                started_at=datetime.now().isoformat(),
                cleanup_ts_file=True,
            )
            
            logger.info(f"Triggered recovery for recording {recording.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to trigger recovery for recording {recording.id}: {e}")
            return False

    async def _cleanup_orphaned_segments(self, db, max_age_hours: int, dry_run: bool, result: Dict) -> None:
        """Cleanup orphaned segment directories"""
        from pathlib import Path
        from datetime import datetime, timedelta
        import shutil
        
        recordings_root = Path(self._service.recordings_base_path)
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        if not recordings_root.exists():
            return
        
        # Find all _segments directories
        for segments_dir in recordings_root.rglob("*_segments"):
            if not segments_dir.is_dir():
                continue
                
            try:
                # Check if directory is old enough
                dir_stat = segments_dir.stat()
                dir_time = datetime.fromtimestamp(dir_stat.st_mtime)
                if dir_time > cutoff_time:
                    continue
                
                # Check if corresponding MP4 exists
                parent_dir = segments_dir.parent
                base_name = segments_dir.name.replace("_segments", "")
                mp4_path = parent_dir / f"{base_name}.mp4"
                ts_path = parent_dir / f"{base_name}.ts"
                
                # Only cleanup if MP4 exists (post-processing completed)
                if mp4_path.exists():
                    if not dry_run:
                        shutil.rmtree(segments_dir)
                        logger.info(f"Cleaned up segments directory: {segments_dir}")
                    result["segments_cleaned"] += 1
                    result.get("segments_cleaned_list", []).append(str(segments_dir))
                    
            except Exception as e:
                logger.error(f"Error cleaning segments directory {segments_dir}: {e}")
                result["segments_cleanup_failed"] = result.get("segments_cleanup_failed", 0) + 1
                result.get("errors", []).append(str(e))
