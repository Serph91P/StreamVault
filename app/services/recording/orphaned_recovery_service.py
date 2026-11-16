"""
Orphaned Recovery Service - Compatibility wrapper for UnifiedRecoveryService

This module provides backward compatibility for code that still imports
the old orphaned_recovery_service. It wraps the new UnifiedRecoveryService.

DEPRECATED: New code should use UnifiedRecoveryService directly.
"""

import logging
from typing import Dict, Any, TypedDict, NotRequired
from collections.abc import Callable
from sqlalchemy.orm import Session, joinedload
from app.models import Recording, Stream
from app.services.recording.recording_values import RecordingValue
from app.services.recording.media_ownership import (
    CaptureState,
    LocalCapture,
    capture_state,
)
from app.utils.async_db_utils import run_in_thread_pool
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
        logger.debug(
            "Creating new OrphanedRecoveryService instance (compatibility wrapper)"
        )
        _recovery_service_instance = OrphanedRecoveryService()

    return _recovery_service_instance


class RecoveryValidation(TypedDict):
    valid: bool
    reason: str | None
    file_size: int
    file_age_seconds: float


class SegmentCleanupResult(TypedDict):
    segments_cleaned: int
    segments_cleaned_list: NotRequired[list[str]]
    segments_cleanup_failed: NotRequired[int]
    errors: NotRequired[list[str]]


class OrphanedRecoveryService:
    """
    Compatibility wrapper for UnifiedRecoveryService.

    This class provides backward-compatible methods that delegate to
    UnifiedRecoveryService for admin endpoints and legacy code.
    """

    def __init__(self, service: UnifiedRecoveryService | None = None) -> None:
        self._service = service if service is not None else UnifiedRecoveryService()

    async def get_orphaned_statistics(self, max_age_hours: int = 72) -> Dict[str, Any]:
        """Get statistics about orphaned recordings (compatibility wrapper)"""
        stats = await self._service.comprehensive_recovery_scan(
            max_age_hours=max_age_hours, dry_run=True
        )

        return {
            "total_orphaned": stats.orphaned_segments + stats.failed_post_processing,
            "total_orphaned_segments": stats.orphaned_segments,
            "failed_post_processing": stats.failed_post_processing,
            "total_size_gb": stats.total_size_gb,
            "by_streamer": {},  # Not supported in new service
        }

    async def scan_and_recover_orphaned_recordings(
        self,
        max_age_hours: int = 72,
        dry_run: bool = False,
        cleanup_segments: bool = True,
    ) -> Dict[str, Any]:
        """Scan and recover orphaned recordings (compatibility wrapper)"""
        stats = await self._service.comprehensive_recovery_scan(
            max_age_hours=max_age_hours, dry_run=dry_run
        )

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

    async def cleanup_orphaned_segments(
        self, max_age_hours: int = 72, dry_run: bool = False
    ) -> Dict[str, Any]:
        """Cleanup orphaned segment directories (compatibility wrapper)"""
        # Use comprehensive scan which includes segment cleanup
        stats = await self._service.comprehensive_recovery_scan(
            max_age_hours=max_age_hours, dry_run=dry_run
        )

        return {
            "success": True,
            "segments_cleaned": stats.orphaned_segments,
            "total_size_gb": stats.total_size_gb,
        }

    async def _find_orphaned_recordings(
        self, db: Session, max_age_hours: int = 72
    ) -> list[Recording]:
        """Find orphaned recordings from database (compatibility wrapper)"""
        from datetime import datetime, timedelta
        from sqlalchemy.orm import joinedload
        from app.models import Recording, Stream

        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)

        # Find recordings that are in 'recording' or 'processing' status but older than cutoff
        orphaned = (
            db.query(Recording)
            .options(joinedload(Recording.stream).joinedload(Stream.streamer))
            .filter(
                Recording.status.in_(["recording", "processing", "failed"]),
                Recording.created_at < cutoff_time,
            )
            .all()
        )

        return orphaned

    async def _validate_orphaned_recording(
        self, recording: Recording
    ) -> RecoveryValidation:
        """Compatibility for session-bound legacy callers; HTTP uses scalar reads."""
        if not recording.path:
            return self._validate_path(None)
        from app.services.recording.media_ownership import recording_is_protected

        owner = await run_in_thread_pool(self._service._recording_owner)
        snapshots = await owner.process_manager.capture_process_snapshot()
        protected = await recording_is_protected(recording, snapshots)
        return await run_in_thread_pool(self._validate_path, recording.path, protected)

    @staticmethod
    def _validate_path(path: str | None, protected: bool = False) -> RecoveryValidation:
        """Retain the legacy 1KiB/MP4/segments eligibility in its worker scope."""
        from pathlib import Path
        from datetime import datetime

        result: RecoveryValidation = {
            "valid": False,
            "reason": None,
            "file_size": 0,
            "file_age_seconds": 0,
        }
        if not path:
            result["reason"] = "No file path"
            return result
        if protected:
            result["reason"] = "Capture is active or its ownership is unverified"
            return result
        file_path = Path(path)

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
        result["file_age_seconds"] = (
            datetime.now() - datetime.fromtimestamp(stat.st_mtime)
        ).total_seconds()

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

    async def recover_recording(
        self, recording_id: int, session_factory: Callable[[], Session]
    ) -> dict[str, object] | None:
        """Mounted single-record recovery: close SQL/FS scopes before admission."""
        from datetime import datetime
        from pathlib import Path
        from app.services.init.background_queue_init import (
            enqueue_recording_post_processing,
        )

        owner = await run_in_thread_pool(self._service._recording_owner)

        def snapshot(
            captures: dict[str, LocalCapture],
        ) -> tuple[RecordingValue, RecoveryValidation] | None:
            with session_factory() as db:
                row = (
                    db.query(Recording)
                    .options(joinedload(Recording.stream).joinedload(Stream.streamer))
                    .filter(Recording.id == recording_id)
                    .first()
                )
                if row is None:
                    return None
                state = capture_state(db, row, captures.get(f"stream_{row.stream_id}"))
                protected = state in {CaptureState.ALIVE, CaptureState.UNKNOWN} or (
                    state is CaptureState.ABSENT and row.status == "recording"
                )
                validation = self._validate_path(row.path, protected)
                return RecordingValue.from_model(row), validation

        async def read() -> tuple[RecordingValue, RecoveryValidation] | None:
            captures = await owner.process_manager.capture_process_snapshot()
            return await run_in_thread_pool(snapshot, captures)

        initial = await read()
        if initial is None:
            return None
        value, validation = initial
        if not validation["valid"] or not value.path:
            return {
                "success": False,
                "message": f"Recording {recording_id} is not suitable for recovery: {validation['reason']}",
            }
        success = False
        try:
            current = await read()
            if (
                current is not None
                and current[1]["valid"]
                and current[0].path == value.path
                and current[0].stream_id == value.stream_id
                and value.stream_id
            ):
                streamer_name = (
                    value.stream.streamer.username
                    if value.stream is not None and value.stream.streamer is not None
                    else "Unknown"
                )
                admitted = await enqueue_recording_post_processing(
                    stream_id=value.stream_id,
                    recording_id=value.id,
                    ts_file_path=value.path,
                    output_dir=str(Path(value.path).parent),
                    streamer_name=streamer_name,
                    started_at=datetime.now().isoformat(),
                    cleanup_ts_file=True,
                    settings=self._service.settings,
                    session_factory=session_factory,
                    queue_service=self._service.queue_service,
                )
                success = bool(admitted)
        except Exception as error:
            logger.error("Single recording recovery failed (%s)", type(error).__name__)
        if success:
            return {
                "success": True,
                "message": f"Recovery triggered for recording {recording_id}",
                "data": {
                    "recording_id": recording_id,
                    "file_path": value.path,
                    "file_size": validation["file_size"],
                },
            }
        return {
            "success": False,
            "message": f"Failed to trigger recovery for recording {recording_id}",
        }

    async def _trigger_orphaned_recovery(
        self, recording: Recording, db: Session
    ) -> bool:
        """Trigger recovery for an orphaned recording"""
        from app.services.init.background_queue_init import (
            enqueue_recording_post_processing,
        )
        from datetime import datetime
        import os

        try:
            if not (await self._validate_orphaned_recording(recording))["valid"]:
                return False
            if not recording.path:
                return False

            # Prepare post-processing payload
            streamer_name = "Unknown"
            if recording.stream and recording.stream.streamer:
                streamer_name = recording.stream.streamer.username

            stream_id = (
                recording.stream_id
                if recording.stream_id
                else (recording.stream.id if recording.stream else None)
            )

            if not stream_id:
                logger.error(
                    f"Cannot trigger recovery for recording {recording.id}: no stream_id"
                )
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
            logger.error(
                f"Failed to trigger recovery for recording {recording.id}: {e}"
            )
            return False

    # Original #959/c966fa4e: keep both legacy and public admin callers native.
    validate_orphaned_recording = _validate_orphaned_recording
    trigger_orphaned_recovery = _trigger_orphaned_recovery

    async def _cleanup_orphaned_segments(
        self,
        db: Session | None,
        max_age_hours: int,
        dry_run: bool,
        result: SegmentCleanupResult,
    ) -> None:
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

                # Only cleanup if MP4 exists (post-processing completed)
                if mp4_path.exists():
                    if not dry_run:
                        shutil.rmtree(segments_dir)
                        logger.info(f"Cleaned up segments directory: {segments_dir}")
                    result["segments_cleaned"] += 1
                    result.get("segments_cleaned_list", []).append(str(segments_dir))

            except Exception as e:
                logger.error(f"Error cleaning segments directory {segments_dir}: {e}")
                result["segments_cleanup_failed"] = (
                    result.get("segments_cleanup_failed", 0) + 1
                )
                result.get("errors", []).append(str(e))
