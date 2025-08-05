"""
Unified Recovery Service - Single point for all recording recovery operations

This service consolidates all recovery operations into one robust system:
- Orphaned segment recovery (segments exist but no final files)
- Failed post-processing recovery 
- Database state recovery
- Active recordings recovery

Replaces multiple overlapping services with one unified approach.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

from app.database import SessionLocal
from app.models import Recording, Stream, Streamer
from app.services.system.logging_service import logging_service

logger = logging.getLogger("streamvault")

@dataclass
class RecoveryStats:
    orphaned_segments: int = 0
    failed_post_processing: int = 0
    corrupted_recordings: int = 0
    recovered_recordings: int = 0
    triggered_post_processing: int = 0
    updated_database_entries: int = 0
    total_size_gb: float = 0.0

class UnifiedRecoveryService:
    """Unified service for all recording recovery operations"""
    
    def __init__(self):
        self.recordings_base_path = Path("/recordings")
        self.is_running = False
        
    async def comprehensive_recovery_scan(self, max_age_hours: int = 72, dry_run: bool = False) -> RecoveryStats:
        """
        Comprehensive recovery scan that handles all types of recovery
        
        Args:
            max_age_hours: Only process recordings newer than this
            dry_run: If True, only scan and report, don't make changes
            
        Returns:
            RecoveryStats with all recovery information
        """
        if self.is_running:
            logger.warning("🔄 Recovery scan already running, skipping")
            return RecoveryStats()
            
        self.is_running = True
        stats = RecoveryStats()
        
        try:
            logger.info(f"🔍 UNIFIED_RECOVERY_START: max_age={max_age_hours}h, dry_run={dry_run}")
            
            # Step 1: Database consistency check and fix
            await self._fix_database_inconsistencies(stats, dry_run)
            
            # Step 2: Find all orphaned segments and failed recordings
            orphaned_recordings = await self._scan_orphaned_segments(max_age_hours)
            failed_recordings = await self._scan_failed_post_processing(max_age_hours)
            
            stats.orphaned_segments = len(orphaned_recordings)
            stats.failed_post_processing = len(failed_recordings)
            
            # Step 3: Process orphaned segments (concatenation needed)
            for recording_info in orphaned_recordings:
                try:
                    if not dry_run:
                        success = await self._process_orphaned_recording(recording_info)
                        if success:
                            stats.recovered_recordings += 1
                            stats.triggered_post_processing += 1
                    
                    stats.total_size_gb += recording_info.get('size_gb', 0)
                    
                except Exception as e:
                    logger.error(f"❌ Failed to process orphaned recording {recording_info.get('recording_id')}: {e}")
            
            # Step 4: Process failed post-processing (files exist but post-processing failed)
            for recording_info in failed_recordings:
                try:
                    if not dry_run:
                        success = await self._retry_post_processing(recording_info)
                        if success:
                            stats.triggered_post_processing += 1
                    
                except Exception as e:
                    logger.error(f"❌ Failed to retry post-processing for {recording_info.get('recording_id')}: {e}")
            
            # Step 5: Final database cleanup
            if not dry_run:
                await self._final_database_cleanup(stats)
            
            logger.info(f"🔍 UNIFIED_RECOVERY_COMPLETE: {stats}")
            
            # Log to dedicated recovery file
            logging_service.log_recording_activity_to_file(
                "SYSTEM_RECOVERY",
                "UnifiedRecovery", 
                f"Recovery scan completed: orphaned={stats.orphaned_segments}, "
                f"failed_pp={stats.failed_post_processing}, recovered={stats.recovered_recordings}, "
                f"triggered_pp={stats.triggered_post_processing}, size={stats.total_size_gb:.1f}GB"
            )
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ Comprehensive recovery scan failed: {e}", exc_info=True)
            return stats
        finally:
            self.is_running = False
    
    async def _scan_orphaned_segments(self, max_age_hours: int) -> List[Dict[str, Any]]:
        """Scan for orphaned segment directories that need concatenation"""
        orphaned = []
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        try:
            if not self.recordings_base_path.exists():
                return orphaned
                
            # Get currently active recordings to avoid processing them
            active_recording_paths = await self._get_active_recording_paths()
            
            for streamer_dir in self.recordings_base_path.iterdir():
                if not streamer_dir.is_dir():
                    continue
                    
                logger.debug(f"🔍 Scanning streamer directory: {streamer_dir.name}")
                    
                for season_dir in streamer_dir.iterdir():
                    if not season_dir.is_dir():
                        continue
                        
                    # Look for segment directories
                    for item in season_dir.iterdir():
                        if item.is_dir() and item.name.endswith('_segments'):
                            # Check if segments exist
                            segment_files = list(item.glob('*.ts'))
                            if not segment_files:
                                continue
                                
                            # Check age
                            newest_segment = max(segment_files, key=lambda f: f.stat().st_mtime)
                            segment_time = datetime.fromtimestamp(newest_segment.stat().st_mtime)
                            
                            if segment_time < cutoff_time:
                                continue
                                
                            # Check if final files exist
                            expected_ts = season_dir / item.name.replace('_segments', '.ts')
                            expected_mp4 = season_dir / item.name.replace('_segments', '.mp4')
                            
                            # CRITICAL: Skip if this recording is currently active
                            if str(expected_ts) in active_recording_paths:
                                logger.info(f"⚠️ SKIPPING_ACTIVE_RECORDING: {expected_ts} is currently being recorded")
                                continue
                            
                            if not expected_ts.exists() and not expected_mp4.exists():
                                # This is orphaned - has segments but no final files
                                total_size = sum(f.stat().st_size for f in segment_files)
                                
                                # Try to find recording in database
                                recording_id = await self._find_recording_by_path(str(expected_ts))
                                
                                logger.info(f"🔍 FOUND_ORPHANED: streamer={streamer_dir.name}, recording_id={recording_id}, size={total_size/(1024**3):.1f}GB")
                                
                                orphaned.append({
                                    'recording_id': recording_id,
                                    'streamer_name': streamer_dir.name,
                                    'segments_dir': item,
                                    'expected_ts_path': expected_ts,
                                    'expected_mp4_path': expected_mp4,
                                    'segment_files': segment_files,
                                    'size_gb': total_size / (1024**3),
                                    'segment_time': segment_time
                                })
                                
        except Exception as e:
            logger.error(f"Error scanning orphaned segments: {e}")
            
        logger.info(f"🔍 ORPHANED_SCAN_COMPLETE: Found {len(orphaned)} orphaned recordings across all streamers")
        return orphaned
    
    async def _scan_failed_post_processing(self, max_age_hours: int) -> List[Dict[str, Any]]:
        """Scan for recordings where .ts exists but .mp4 is missing or failed"""
        failed = []
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        try:
            # Get currently active recordings to avoid processing them
            active_recording_paths = await self._get_active_recording_paths()
            
            with SessionLocal() as db:
                # Find recordings that are completed but may have failed post-processing
                recent_recordings = db.query(Recording).join(Stream).join(Streamer).filter(
                    Recording.status.in_(['completed', 'stopped']),
                    Recording.start_time >= cutoff_time
                ).all()
                
                for recording in recent_recordings:
                    if not recording.path:
                        continue
                        
                    # CRITICAL: Skip if this recording is currently active
                    if recording.path in active_recording_paths:
                        logger.info(f"⚠️ SKIPPING_ACTIVE_RECORDING: {recording.path} is currently being recorded")
                        continue
                    
                    ts_path = Path(recording.path)
                    mp4_path = ts_path.with_suffix('.mp4')
                    
                    # Case 1: TS file exists but no MP4 (post-processing never started or failed)
                    if ts_path.exists() and not mp4_path.exists():
                        logger.info(f"🔍 FOUND_FAILED_PP: recording_id={recording.id}, streamer={recording.stream.streamer.username}, missing MP4")
                        failed.append({
                            'recording_id': recording.id,
                            'recording': recording,
                            'ts_path': ts_path,
                            'mp4_path': mp4_path,
                            'type': 'missing_mp4',
                            'streamer_name': recording.stream.streamer.username
                        })
                        
                    # Case 2: Neither TS nor MP4 exists but segments might exist
                    elif not ts_path.exists() and not mp4_path.exists():
                        segments_dir = Path(str(ts_path).replace('.ts', '_segments'))
                        if segments_dir.exists() and list(segments_dir.glob('*.ts')):
                            logger.info(f"🔍 FOUND_FAILED_PP: recording_id={recording.id}, streamer={recording.stream.streamer.username}, needs concatenation")
                            failed.append({
                                'recording_id': recording.id,
                                'recording': recording,
                                'segments_dir': segments_dir,
                                'ts_path': ts_path,
                                'mp4_path': mp4_path,
                                'type': 'needs_concatenation',
                                'streamer_name': recording.stream.streamer.username
                            })
                            
        except Exception as e:
            logger.error(f"Error scanning failed post-processing: {e}")
            
        logger.info(f"🔍 FAILED_PP_SCAN_COMPLETE: Found {len(failed)} failed post-processing recordings across all streamers")
        return failed
    
    async def _process_orphaned_recording(self, recording_info: Dict[str, Any]) -> bool:
        """Process a single orphaned recording by concatenating segments"""
        try:
            segments_dir = recording_info['segments_dir']
            expected_ts_path = recording_info['expected_ts_path']
            recording_id = recording_info['recording_id']
            streamer_name = recording_info['streamer_name']
            
            logger.info(f"🔄 PROCESSING_ORPHANED: recording_id={recording_id}, streamer={streamer_name}")
            
            # Log to dedicated file
            logging_service.log_post_processing_activity(
                "CONCATENATION_START",
                streamer_name,
                f"Starting concatenation for orphaned recording {recording_id}: {segments_dir.name}"
            )
            
            # Use the existing concatenation system
            from app.services.recording.recording_lifecycle_manager import RecordingLifecycleManager
            lifecycle_manager = RecordingLifecycleManager()
            
            result = await lifecycle_manager._concatenate_segments(segments_dir, expected_ts_path)
            
            if result and result.exists():
                logger.info(f"✅ CONCATENATION_SUCCESS: {expected_ts_path}")
                
                # Update database if we have a recording_id
                if recording_id:
                    await self._update_recording_after_concatenation(recording_id, str(expected_ts_path))
                
                # Trigger post-processing
                await self._trigger_post_processing(recording_id, str(expected_ts_path), streamer_name)
                
                logging_service.log_post_processing_activity(
                    "CONCATENATION_SUCCESS",
                    streamer_name,
                    f"Successfully concatenated orphaned recording {recording_id}"
                )
                
                return True
            else:
                logger.error(f"❌ CONCATENATION_FAILED: {segments_dir}")
                logging_service.log_post_processing_activity(
                    "CONCATENATION_FAILED",
                    streamer_name,
                    f"Failed to concatenate orphaned recording {recording_id}"
                )
                return False
                
        except Exception as e:
            logger.error(f"❌ Error processing orphaned recording: {e}")
            return False
    
    async def _retry_post_processing(self, recording_info: Dict[str, Any]) -> bool:
        """Retry post-processing for a failed recording"""
        try:
            recording_id = recording_info['recording_id']
            ts_path = recording_info['ts_path']
            streamer_name = recording_info['streamer_name']
            
            logger.info(f"🔄 RETRY_POST_PROCESSING: recording_id={recording_id}")
            
            # If we need concatenation first
            if recording_info['type'] == 'needs_concatenation':
                segments_dir = recording_info['segments_dir']
                result = await self._process_orphaned_recording({
                    'recording_id': recording_id,
                    'segments_dir': segments_dir,
                    'expected_ts_path': ts_path,
                    'streamer_name': streamer_name
                })
                return result
            
            # Otherwise just trigger post-processing
            return await self._trigger_post_processing(recording_id, str(ts_path), streamer_name)
            
        except Exception as e:
            logger.error(f"❌ Error retrying post-processing: {e}")
            return False
    
    async def _trigger_post_processing(self, recording_id: Optional[int], ts_file_path: str, streamer_name: str) -> bool:
        """Trigger post-processing for a recording"""
        try:
            # Skip if no recording_id
            if recording_id is None:
                logger.warning(f"⚠️ Cannot trigger post-processing without recording_id for {ts_file_path}")
                return False
                
            # Use the existing post-processing system
            from app.services.recording.post_processing_coordinator import PostProcessingCoordinator
            
            coordinator = PostProcessingCoordinator()
            
            # Create recording data for post-processing
            recording_data = {
                'recording_id': recording_id,
                'streamer_name': streamer_name,
                'file_path': ts_file_path
            }
            
            success = await coordinator.enqueue_post_processing(recording_id, ts_file_path, recording_data)
            
            if success:
                logger.info(f"✅ POST_PROCESSING_TRIGGERED: recording_id={recording_id}")
                logging_service.log_post_processing_activity(
                    "POST_PROCESSING_START",
                    streamer_name,
                    f"Successfully triggered post-processing for recording {recording_id}"
                )
            else:
                logger.error(f"❌ POST_PROCESSING_TRIGGER_FAILED: recording_id={recording_id}")
                
            return success
            
        except Exception as e:
            logger.error(f"❌ Error triggering post-processing: {e}")
            return False
    
    async def _find_recording_by_path(self, file_path: str) -> Optional[int]:
        """Find recording ID by file path"""
        try:
            with SessionLocal() as db:
                recording = db.query(Recording).filter(Recording.path == file_path).first()
                return recording.id if recording else None
        except Exception:
            return None
    
    async def _update_recording_after_concatenation(self, recording_id: int, file_path: str):
        """Update recording in database after successful concatenation"""
        try:
            with SessionLocal() as db:
                recording = db.query(Recording).filter(Recording.id == recording_id).first()
                if recording:
                    recording.status = 'completed'
                    recording.path = file_path
                    if not recording.end_time:
                        recording.end_time = datetime.utcnow()
                    db.commit()
                    logger.info(f"✅ Updated recording {recording_id} status to completed")
        except Exception as e:
            logger.error(f"❌ Error updating recording {recording_id}: {e}")
    
    async def _fix_database_inconsistencies(self, stats: RecoveryStats, dry_run: bool):
        """Fix database inconsistencies"""
        try:
            with SessionLocal() as db:
                # Find recordings stuck in 'recording' status
                stuck_recordings = db.query(Recording).filter(
                    Recording.status == 'recording'
                ).all()
                
                for recording in stuck_recordings:
                    # Check if recording should be completed
                    if recording.path:
                        ts_path = Path(recording.path)
                        segments_dir = Path(str(recording.path).replace('.ts', '_segments'))
                        
                        # If TS file exists, mark as completed
                        if ts_path.exists():
                            if not dry_run:
                                recording.status = 'completed'
                                if not recording.end_time:
                                    recording.end_time = datetime.utcnow()
                                stats.updated_database_entries += 1
                        
                        # If segments exist but no TS file, this will be handled by orphaned recovery
                        elif segments_dir.exists() and list(segments_dir.glob('*.ts')):
                            # Will be processed by orphaned recovery
                            pass
                
                if not dry_run:
                    db.commit()
                    
        except Exception as e:
            logger.error(f"❌ Error fixing database inconsistencies: {e}")
    
    async def _final_database_cleanup(self, stats: RecoveryStats):
        """Final database cleanup after recovery"""
        try:
            with SessionLocal() as db:
                # Remove any recordings that have no associated files and are very old
                cutoff = datetime.now() - timedelta(days=7)
                
                orphaned_db_records = db.query(Recording).filter(
                    Recording.status == 'recording',
                    Recording.start_time < cutoff,
                    Recording.path.is_(None)
                ).all()
                
                for recording in orphaned_db_records:
                    logger.warning(f"🗑️ Removing orphaned DB record: recording_id={recording.id}")
                    db.delete(recording)
                    stats.updated_database_entries += 1
                
                db.commit()
                
        except Exception as e:
            logger.error(f"❌ Error in final database cleanup: {e}")
    
    async def _get_active_recording_paths(self) -> set:
        """Get paths of currently active recordings to avoid processing them"""
        active_paths = set()
        try:
            # Get active recordings from the recording service
            from app.services.recording.recording_service import RecordingService
            recording_service = RecordingService()
            
            active_recordings = recording_service.get_active_recordings()
            for recording_data in active_recordings.values():
                if 'file_path' in recording_data and recording_data['file_path']:
                    active_paths.add(recording_data['file_path'])
                    
            # Also check database for recordings with status 'recording' that are very recent
            with SessionLocal() as db:
                recent_cutoff = datetime.now() - timedelta(hours=1)  # Only very recent ones
                active_db_recordings = db.query(Recording).filter(
                    Recording.status == 'recording',
                    Recording.start_time >= recent_cutoff
                ).all()
                
                for recording in active_db_recordings:
                    if recording.path:
                        active_paths.add(recording.path)
                        
            logger.info(f"🔍 ACTIVE_RECORDINGS_CHECK: Found {len(active_paths)} active recording paths")
            return active_paths
            
        except Exception as e:
            logger.error(f"Error getting active recording paths: {e}")
            return set()

# Singleton instance
_unified_recovery_service = None

async def get_unified_recovery_service() -> UnifiedRecoveryService:
    """Get the singleton unified recovery service"""
    global _unified_recovery_service
    if _unified_recovery_service is None:
        _unified_recovery_service = UnifiedRecoveryService()
    return _unified_recovery_service
