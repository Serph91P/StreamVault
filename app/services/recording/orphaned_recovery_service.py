"""
Orphaned Recording Recovery Service

Database-driven recovery system for .ts files that need post-processing.
This service scans the database for recordings with .ts files that haven't
been post-processed and triggers their processing without filesystem scanning.
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Recording, Stream, Streamer
from app.services.recording.recording_orchestrator import RecordingOrchestrator

logger = logging.getLogger("streamvault")


class OrphanedRecoveryService:
    """Service for recovering orphaned .ts files based on database state"""
    
    # Configuration constants
    DEFAULT_ORPHANED_RECORDINGS_LIMIT = 100
    FILE_TOO_RECENT_THRESHOLD_SECONDS = 1800  # 30 minutes - don't process files that are too recent
    MIN_FILE_SIZE_BYTES = 1024 * 1024  # 1MB minimum file size requirement
    
    def __init__(self, recording_orchestrator: RecordingOrchestrator):
        self.recording_orchestrator = recording_orchestrator
        
    async def scan_and_recover_orphaned_recordings(
        self, 
        max_age_hours: int = 48,
        dry_run: bool = False,
        cleanup_segments: bool = True
    ) -> Dict[str, Any]:
        """
        Scan database for orphaned recordings and trigger post-processing.
        
        Args:
            max_age_hours: Only process recordings newer than this (default: 48h)
            dry_run: If True, only return what would be processed without doing it
            cleanup_segments: If True, also cleanup orphaned segment directories
        
        Returns:
            Dictionary with recovery statistics and results
        """
        logger.info(f"Starting orphaned recording recovery scan (max_age: {max_age_hours}h, dry_run: {dry_run}, cleanup_segments: {cleanup_segments})")
        
        result = {
            "scanned_recordings": 0,
            "orphaned_found": 0,
            "recovery_triggered": 0,
            "recovery_failed": 0,
            "skipped_missing_files": 0,
            "skipped_recent": 0,
            "segments_cleaned": 0,
            "segments_cleanup_failed": 0,
            "orphaned_recordings": [],
            "segments_cleaned_list": [],
            "errors": []
        }
        
        try:
            with SessionLocal() as db:
                # Find recordings that might be orphaned
                orphaned_recordings = await self._find_orphaned_recordings(db, max_age_hours)
                result["scanned_recordings"] = len(orphaned_recordings)
                
                logger.info(f"Found {len(orphaned_recordings)} potentially orphaned recordings")
                
                for recording in orphaned_recordings:
                    try:
                        result["orphaned_found"] += 1
                        
                        # Validate recording file exists
                        validation_result = await self._validate_orphaned_recording(recording)
                        
                        if not validation_result["valid"]:
                            if validation_result["reason"] == "file_missing":
                                result["skipped_missing_files"] += 1
                            elif validation_result["reason"] == "too_recent":
                                result["skipped_recent"] += 1
                            
                            logger.debug(f"Skipping recording {recording.id}: {validation_result['reason']}")
                            continue
                        
                        orphaned_info = {
                            "recording_id": recording.id,
                            "stream_id": recording.stream_id,
                            "streamer_name": recording.stream.streamer.username if recording.stream and recording.stream.streamer else "unknown",
                            "file_path": recording.path,
                            "created_at": recording.created_at.isoformat() if recording.created_at else None,
                            "file_size": validation_result.get("file_size"),
                            "recovery_triggered": False,
                            "error": None
                        }
                        
                        if not dry_run:
                            # Trigger post-processing recovery
                            success = await self._trigger_orphaned_recovery(recording, db)
                            
                            if success:
                                result["recovery_triggered"] += 1
                                orphaned_info["recovery_triggered"] = True
                                logger.info(f"✅ Triggered recovery for recording {recording.id}")
                            else:
                                result["recovery_failed"] += 1
                                orphaned_info["error"] = "Failed to trigger recovery"
                                logger.error(f"❌ Failed to trigger recovery for recording {recording.id}")
                        
                        result["orphaned_recordings"].append(orphaned_info)
                        
                    except Exception as e:
                        result["recovery_failed"] += 1
                        result["errors"].append(f"Recording {recording.id}: {str(e)}")
                        logger.error(f"Error processing recording {recording.id}: {e}", exc_info=True)
                
                # Cleanup orphaned segment directories if enabled
                if cleanup_segments:
                    await self._cleanup_orphaned_segments(db, max_age_hours, dry_run, result)
                
        except Exception as e:
            result["errors"].append(f"Scan failed: {str(e)}")
            logger.error(f"Orphaned recovery scan failed: {e}", exc_info=True)
        
        logger.info(f"Orphaned recovery scan completed: {result['recovery_triggered']} recoveries triggered")
        return result
    
    async def validate_orphaned_recording(self, recording: Recording) -> Dict[str, Any]:
        """
        Public method to validate if a recording is suitable for orphaned recovery
        
        Args:
            recording: Recording object to validate
            
        Returns:
            Dict with validation result and details
        """
        return await self._validate_orphaned_recording(recording)
    
    async def trigger_orphaned_recovery(self, recording: Recording, db: Session) -> bool:
        """
        Public method to trigger orphaned recovery for a specific recording
        
        Args:
            recording: Recording object to recover
            db: Database session
            
        Returns:
            True if recovery was triggered successfully, False otherwise
        """
        return await self._trigger_orphaned_recovery(recording, db)
    
    async def _find_orphaned_recordings(self, db: Session, max_age_hours: int) -> List[Recording]:
        """Find recordings that appear to be orphaned (have .ts but no .mp4)"""
        
        # Calculate cutoff time
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
        
        # Query for recordings that:
        # 1. Have a .ts file path
        # 2. Status is 'completed' or 'recording' (but not 'processing' or 'post_processing')
        # 3. Are older than 30 minutes (to avoid interfering with active recordings)
        # 4. Within the age limit
        
        recent_cutoff = datetime.utcnow() - timedelta(minutes=30)
        
        orphaned_recordings = (
            db.query(Recording)
            .join(Stream)
            .join(Streamer)
            .filter(
                Recording.path.like('%.ts'),  # Has .ts file
                Recording.status.in_(['completed', 'recording']),  # Not actively processing
                Recording.created_at >= cutoff_time,  # Within age limit
                Recording.created_at <= recent_cutoff  # Not too recent
            )
            .order_by(Recording.created_at.desc())
            .limit(self.DEFAULT_ORPHANED_RECORDINGS_LIMIT)  # Safety limit
            .all()
        )
        
        # Additional filtering: check if .mp4 exists in database or filesystem
        truly_orphaned = []
        
        for recording in orphaned_recordings:
            if recording.path and recording.path.endswith('.ts'):
                # Check if there's already an MP4 version in database
                mp4_path = recording.path.replace('.ts', '.mp4')
                
                # Check if another recording exists with the MP4 path
                mp4_recording = (
                    db.query(Recording)
                    .filter(Recording.path == mp4_path)
                    .first()
                )
                
                if not mp4_recording:
                    # No MP4 recording in database, this might be orphaned
                    truly_orphaned.append(recording)
        
        return truly_orphaned
    
    async def _validate_orphaned_recording(self, recording: Recording) -> Dict[str, Any]:
        """Validate if recording file exists and is suitable for recovery"""
        
        if not recording.path:
            return {"valid": False, "reason": "no_path"}
        
        file_path = Path(recording.path)
        
        # Check if file exists
        if not file_path.exists():
            return {"valid": False, "reason": "file_missing"}
        
        # Check if it's actually a .ts file
        if not recording.path.endswith('.ts'):
            return {"valid": False, "reason": "not_ts_file"}
        
        # Check if .mp4 already exists
        mp4_path = file_path.with_suffix('.mp4')
        if mp4_path.exists():
            return {"valid": False, "reason": "mp4_exists"}
        
        # Check file age (don't process files that are too recent)
        file_stat = file_path.stat()
        file_age = datetime.now() - datetime.fromtimestamp(file_stat.st_mtime)

        if file_age.total_seconds() < self.FILE_TOO_RECENT_THRESHOLD_SECONDS:  # Less than 30 minutes old
            return {"valid": False, "reason": "too_recent"}
        
        # Check file size (must be reasonable)
        file_size = file_stat.st_size
        if file_size < self.MIN_FILE_SIZE_BYTES:  # Less than 1MB
            return {"valid": False, "reason": "file_too_small"}
        
        return {
            "valid": True,
            "file_size": file_size,
            "file_age_seconds": file_age.total_seconds()
        }
    
    async def _trigger_orphaned_recovery(self, recording: Recording, db: Session) -> bool:
        """Trigger post-processing for an orphaned recording"""
        
        try:
            # Lock the recording row to prevent concurrent updates
            locked_recording = db.query(Recording).filter(Recording.id == recording.id).with_for_update().one_or_none()
            if not locked_recording:
                logger.error(f"Recording {recording.id} not found when attempting to lock")
                return False
            
            # Check if another process already started processing this recording
            if locked_recording.status == 'post_processing':
                logger.info(f"Recording {recording.id} is already being processed by another process")
                return False
            
            # Mark recording as processing to prevent double-processing
            locked_recording.status = 'post_processing'
            locked_recording.updated_at = datetime.utcnow()
            db.commit()
            
            # Prepare recording data for post-processing
            recording_data = {
                'streamer_id': locked_recording.stream.streamer_id if locked_recording.stream else None,
                'stream_id': locked_recording.stream_id,
                'started_at': locked_recording.created_at.isoformat() if locked_recording.created_at else datetime.utcnow().isoformat(),
                'recording_id': locked_recording.id,
                'metadata': {
                    'title': locked_recording.stream.title if locked_recording.stream else 'Recovered Stream',
                    'streamer': locked_recording.stream.streamer.username if locked_recording.stream and locked_recording.stream.streamer else 'unknown'
                }
            }
            
            # Trigger post-processing through orchestrator
            success = await self.recording_orchestrator.enqueue_post_processing(
                locked_recording.id,
                locked_recording.path,
                recording_data
            )
            
            if not success:
                # Revert status if post-processing failed to enqueue
                locked_recording.status = 'completed'
                db.commit()
                return False
            
            logger.info(f"Successfully triggered orphaned recovery for recording {recording.id}")
            return True
            
        except Exception as e:
            # Revert status on error
            try:
                # Try to revert the status using the original recording object
                recovery_recording = db.query(Recording).filter(Recording.id == recording.id).first()
                if recovery_recording:
                    recovery_recording.status = 'completed'
                    db.commit()
            except Exception as inner_e:
                logger.error(f"Failed to revert recording status for recording {recording.id}: {inner_e}")
                # Don't raise the inner exception, we want to raise the original one
            
            logger.error(f"Failed to trigger orphaned recovery for recording {recording.id}: {e}")
            return False
    
    async def get_orphaned_statistics(self, max_age_hours: int = 168) -> Dict[str, Any]:
        """Get statistics about potentially orphaned recordings"""
        
        try:
            with SessionLocal() as db:
                # Find orphaned recordings
                orphaned_recordings = await self._find_orphaned_recordings(db, max_age_hours)
                
                # Find orphaned segment directories
                orphaned_segments = await self._find_orphaned_segments(db, max_age_hours)
                
                # Calculate statistics
                total_size = 0
                total_segments_size = 0
                by_streamer = {}
                
                for recording in orphaned_recordings:
                    if recording.path and Path(recording.path).exists():
                        file_size = Path(recording.path).stat().st_size
                        total_size += file_size
                        
                        streamer_name = recording.stream.streamer.username if recording.stream and recording.stream.streamer else 'unknown'
                        if streamer_name not in by_streamer:
                            by_streamer[streamer_name] = {'count': 0, 'size': 0, 'segments': 0, 'segments_size': 0}
                        
                        by_streamer[streamer_name]['count'] += 1
                        by_streamer[streamer_name]['size'] += file_size
                
                # Add segment statistics
                for segment_info in orphaned_segments:
                    total_segments_size += segment_info['size']
                    streamer_name = segment_info['streamer_name']
                    
                    if streamer_name not in by_streamer:
                        by_streamer[streamer_name] = {'count': 0, 'size': 0, 'segments': 0, 'segments_size': 0}
                    
                    by_streamer[streamer_name]['segments'] += 1
                    by_streamer[streamer_name]['segments_size'] += segment_info['size']
                
                return {
                    "total_orphaned": len(orphaned_recordings),
                    "total_orphaned_segments": len(orphaned_segments),
                    "total_size_bytes": total_size,
                    "total_size_gb": round(total_size / (1024**3), 2),
                    "total_segments_size_bytes": total_segments_size,
                    "total_segments_size_gb": round(total_segments_size / (1024**3), 2),
                    "by_streamer": by_streamer,
                    "oldest_recording": min(r.created_at for r in orphaned_recordings) if orphaned_recordings else None,
                    "newest_recording": max(r.created_at for r in orphaned_recordings) if orphaned_recordings else None,
                    "orphaned_segments_details": orphaned_segments
                }
                
        except Exception as e:
            logger.error(f"Failed to get orphaned statistics: {e}")
            return {
                "total_orphaned": 0,
                "total_size_bytes": 0,
                "total_size_gb": 0,
                "by_streamer": {},
                "error": str(e)
            }
    
    async def _cleanup_orphaned_segments(self, db: Session, max_age_hours: int, dry_run: bool, result: Dict[str, Any]):
        """
        Find and cleanup orphaned segment directories
        
        Segment directories that exist but have no corresponding .mp4 file and no active recording
        are considered orphaned and can be safely removed.
        """
        try:
            logger.info("🧹 Scanning for orphaned segment directories...")
            
            # Calculate cutoff time
            cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
            recent_cutoff = datetime.utcnow() - timedelta(minutes=30)
            
            # Find recordings that might have orphaned segment directories
            recordings_with_ts = (
                db.query(Recording)
                .join(Stream) 
                .join(Streamer)
                .filter(
                    Recording.path.like('%.ts'),
                    Recording.created_at >= cutoff_time,
                    Recording.created_at <= recent_cutoff
                )
                .all()
            )
            
            for recording in recordings_with_ts:
                if not recording.path:
                    continue
                    
                # Check for segment directory
                ts_path = Path(recording.path)
                segments_dir_name = ts_path.stem + "_segments"
                segments_dir = ts_path.parent / segments_dir_name
                
                if segments_dir.exists() and segments_dir.is_dir():
                    logger.debug(f"🔍 Found segment directory: {segments_dir}")
                    
                    # Check if there's a corresponding MP4 file
                    mp4_path = ts_path.with_suffix('.mp4')
                    
                    # Check if MP4 exists in filesystem or database
                    mp4_exists_file = mp4_path.exists()
                    mp4_exists_db = (
                        db.query(Recording)
                        .filter(Recording.path == str(mp4_path))
                        .first() is not None
                    )
                    
                    # Check if recording is currently active (being processed)
                    is_active = recording.status in ['recording', 'post_processing', 'processing']
                    
                    if not mp4_exists_file and not mp4_exists_db and not is_active:
                        # This segment directory is orphaned
                        logger.info(f"🗑️  Found orphaned segment directory: {segments_dir}")
                        
                        segment_info = {
                            "recording_id": recording.id,
                            "recording_path": recording.path,
                            "segments_dir": str(segments_dir),
                            "streamer_name": recording.stream.streamer.username if recording.stream and recording.stream.streamer else "Unknown",
                            "created_at": recording.created_at.isoformat() if recording.created_at else None,
                            "cleanup_triggered": False,
                            "error": None
                        }
                        
                        if not dry_run:
                            try:
                                # Calculate directory size before removal
                                import shutil
                                dir_size = sum(
                                    f.stat().st_size for f in segments_dir.rglob('*') if f.is_file()
                                )
                                
                                # Remove the entire segment directory
                                shutil.rmtree(segments_dir)
                                
                                result["segments_cleaned"] += 1
                                segment_info["cleanup_triggered"] = True
                                segment_info["size_cleaned"] = dir_size
                                
                                logger.info(f"✅ Cleaned orphaned segment directory: {segments_dir} ({dir_size / (1024**2):.1f} MB)")
                                
                            except Exception as e:
                                result["segments_cleanup_failed"] += 1
                                segment_info["error"] = str(e)
                                result["errors"].append(f"Failed to cleanup {segments_dir}: {str(e)}")
                                logger.error(f"❌ Failed to cleanup segment directory {segments_dir}: {e}")
                        else:
                            # Dry run - just count what would be cleaned
                            try:
                                dir_size = sum(
                                    f.stat().st_size for f in segments_dir.rglob('*') if f.is_file()
                                )
                                segment_info["size_would_clean"] = dir_size
                                logger.info(f"🔍 Would clean orphaned segment directory: {segments_dir} ({dir_size / (1024**2):.1f} MB)")
                            except Exception as e:
                                segment_info["error"] = f"Could not calculate size: {str(e)}"
                        
                        result["segments_cleaned_list"].append(segment_info)
            
            if result["segments_cleaned"] > 0:
                logger.info(f"🧹 Cleaned {result['segments_cleaned']} orphaned segment directories")
            elif len(result["segments_cleaned_list"]) > 0 and dry_run:
                logger.info(f"🔍 Found {len(result['segments_cleaned_list'])} orphaned segment directories (dry run)")
            else:
                logger.debug("🧹 No orphaned segment directories found")
                
        except Exception as e:
            result["errors"].append(f"Segment cleanup failed: {str(e)}")
            logger.error(f"Error during segment cleanup: {e}", exc_info=True)
    
    async def _find_orphaned_segments(self, db: Session, max_age_hours: int) -> List[Dict[str, Any]]:
        """Find orphaned segment directories for statistics"""
        try:
            orphaned_segments = []
            
            # Calculate cutoff time
            cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
            recent_cutoff = datetime.utcnow() - timedelta(minutes=30)
            
            # Find recordings that might have orphaned segment directories
            recordings_with_ts = (
                db.query(Recording)
                .join(Stream)
                .join(Streamer)
                .filter(
                    Recording.path.like('%.ts'),
                    Recording.created_at >= cutoff_time,
                    Recording.created_at <= recent_cutoff
                )
                .all()
            )
            
            for recording in recordings_with_ts:
                if not recording.path:
                    continue
                    
                # Check for segment directory
                ts_path = Path(recording.path)
                segments_dir_name = ts_path.stem + "_segments"
                segments_dir = ts_path.parent / segments_dir_name
                
                if segments_dir.exists() and segments_dir.is_dir():
                    # Check if there's a corresponding MP4 file
                    mp4_path = ts_path.with_suffix('.mp4')
                    
                    # Check if MP4 exists in filesystem or database
                    mp4_exists_file = mp4_path.exists()
                    mp4_exists_db = (
                        db.query(Recording)
                        .filter(Recording.path == str(mp4_path))
                        .first() is not None
                    )
                    
                    # Check if recording is currently active
                    is_active = recording.status in ['recording', 'post_processing', 'processing']
                    
                    if not mp4_exists_file and not mp4_exists_db and not is_active:
                        # Calculate directory size
                        try:
                            dir_size = sum(
                                f.stat().st_size for f in segments_dir.rglob('*') if f.is_file()
                            )
                        except:
                            dir_size = 0
                        
                        orphaned_segments.append({
                            "recording_id": recording.id,
                            "segments_dir": str(segments_dir),
                            "streamer_name": recording.stream.streamer.username if recording.stream and recording.stream.streamer else "Unknown",
                            "size": dir_size,
                            "created_at": recording.created_at
                        })
            
            return orphaned_segments
            
        except Exception as e:
            logger.error(f"Error finding orphaned segments: {e}", exc_info=True)
            return []


# Singleton instance
_orphaned_recovery_service: Optional[OrphanedRecoveryService] = None


async def get_orphaned_recovery_service() -> OrphanedRecoveryService:
    """Get singleton instance of OrphanedRecoveryService"""
    global _orphaned_recovery_service
    
    if _orphaned_recovery_service is None:
        from app.services.recording.recording_service import RecordingService
        recording_service = RecordingService()
        recording_orchestrator = recording_service.orchestrator
        
        _orphaned_recovery_service = OrphanedRecoveryService(recording_orchestrator)
    
    return _orphaned_recovery_service
