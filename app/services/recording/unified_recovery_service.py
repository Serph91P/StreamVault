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
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

from app.database import SessionLocal
from app.models import Recording, Stream, Streamer
from app.services.system.logging_service import logging_service
from app.services.init.background_queue_init import enqueue_recording_post_processing

logger = logging.getLogger("streamvault")

# Constants for file validation
MIN_TS_FILE_SIZE_BYTES = 1024  # Minimum valid TS file size (1KB)

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
    
    # Configuration constants
    DATABASE_CLEANUP_DAYS = 7  # Days after which orphaned DB records are cleaned up
    ACTIVE_RECORDING_CHECK_HOURS = 1  # Hours to consider recent recordings as potentially active
    
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
            
            # CRITICAL: First check if background queue service is running
            if not dry_run:
                queue_status = await self._check_queue_status_via_api()
                if queue_status is None:
                    logger.error("❌ CRITICAL: Background queue service not responsive!")
                    logger.error("❌ Cannot safely perform recovery without working queue service")
                    
                    # Attempt to restart queue
                    restart_success = await self._attempt_queue_restart()
                    if not restart_success:
                        logger.error("❌ ABORTING RECOVERY: Queue service cannot be started")
                        return stats
                    
                    # Re-check after restart
                    queue_status = await self._check_queue_status_via_api()
                    if queue_status is None:
                        logger.error("❌ ABORTING RECOVERY: Queue service still not responsive after restart")
                        return stats
                
                logger.info("✅ QUEUE_SERVICE_VERIFIED: Background queue is responsive")
            
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
                            logger.info(f"✅ POST_PROCESSING_TRIGGERED: recording_id={recording_info.get('recording_id')}")
                        else:
                            logger.warning(f"⚠️ POST_PROCESSING_TRIGGER_FAILED: recording_id={recording_info.get('recording_id')}")
                    
                except Exception as e:
                    logger.error(f"❌ Failed to retry post-processing for {recording_info.get('recording_id')}: {e}", exc_info=True)
            
            # Step 5: Final queue verification (if we triggered any tasks)
            if not dry_run and stats.triggered_post_processing > 0:
                await self._final_queue_verification(stats)
            
            # Step 6: Final database cleanup
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
            
            # Collect all potential orphaned recordings first, then batch DB queries
            potential_orphans = []
            
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
                                
                                potential_orphans.append({
                                    'streamer_name': streamer_dir.name,
                                    'segments_dir': item,
                                    'expected_ts_path': expected_ts,
                                    'expected_mp4_path': expected_mp4,
                                    'segment_files': segment_files,
                                    'size_gb': total_size / (1024**3),
                                    'segment_time': segment_time
                                })
            
            # Batch query all recording IDs at once
            if potential_orphans:
                expected_paths = [str(orphan['expected_ts_path']) for orphan in potential_orphans]
                recording_map = await self._batch_find_recordings_by_paths(expected_paths)
                
                # Now combine the data
                for orphan_data in potential_orphans:
                    expected_ts_str = str(orphan_data['expected_ts_path'])
                    recording_id = recording_map.get(expected_ts_str)
                    
                    logger.info(f"🔍 FOUND_ORPHANED: streamer={orphan_data['streamer_name']}, recording_id={recording_id}, size={orphan_data['size_gb']:.1f}GB")
                    
                    orphan_data['recording_id'] = recording_id
                    orphaned.append(orphan_data)
                                
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
                        else:
                            logger.debug(f"🔍 SKIP_UNRECOVERABLE: recording_id={recording.id}, no TS file and no segments found")
                            
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
            
            # Use shared utility for segment concatenation
            result = await self._concatenate_segments_util(segments_dir, expected_ts_path)
            
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

            # Check if the TS file actually exists before triggering post-processing
            if not ts_path.exists():
                logger.warning(f"⚠️ SKIP_POST_PROCESSING: recording_id={recording_id}, TS file no longer exists: {ts_path}")
                return False

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

            # CRITICAL: Check if TS file exists before proceeding
            ts_path = Path(ts_file_path)
            if not ts_path.exists():
                logger.warning(f"⚠️ SKIP_POST_PROCESSING: recording_id={recording_id}, TS file does not exist: {ts_file_path}")
                return False

            # Check file size to ensure it's not empty/corrupted
            file_size = ts_path.stat().st_size
            if file_size < MIN_TS_FILE_SIZE_BYTES:  # Less than 1KB
                logger.warning(f"⚠️ SKIP_POST_PROCESSING: recording_id={recording_id}, TS file too small ({file_size} bytes): {ts_file_path}")
                return False
                
            # Get recording data from database to get stream_id and other info
            with SessionLocal() as db:
                recording = db.query(Recording).filter(Recording.id == recording_id).first()
                if not recording:
                    logger.error(f"❌ Recording {recording_id} not found in database")
                    return False
                
                # Get required parameters
                stream_id = recording.stream_id
                output_dir = Path(ts_file_path).parent
                
                # Validate that we have the required start_time
                if recording.start_time:
                    started_at = recording.start_time.isoformat()
                else:
                    logger.warning(f"⚠️ Recording {recording_id} has no start_time; cannot trigger post-processing accurately.")
                    return False

            logger.info(f"🔄 TRIGGERING_POST_PROCESSING: recording_id={recording_id}, file_size={file_size/1024/1024:.1f}MB")
            
            # Additional validation: ensure output directory exists and is writable
            output_dir = Path(ts_file_path).parent
            if not output_dir.exists():
                logger.error(f"❌ Output directory does not exist: {output_dir}")
                return False
            
            # Test if we can write to the output directory
            try:
                test_file = output_dir / f"test_write_{recording_id}.tmp"
                test_file.touch()
                test_file.unlink()
            except Exception as e:
                logger.error(f"❌ Cannot write to output directory {output_dir}: {e}")
                return False
            
            # CRITICAL: Check if background queue service is actually running
            success = await self._verify_and_enqueue_post_processing(
                stream_id=stream_id,
                recording_id=recording_id,
                ts_file_path=ts_file_path,
                output_dir=str(output_dir),
                streamer_name=streamer_name,
                started_at=started_at
            )
            
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
            logger.error(f"❌ Error triggering post-processing: {e}", exc_info=True)
            return False
    
    async def _find_recording_by_path(self, file_path: str) -> Optional[int]:
        """Find recording ID by file path"""
        try:
            with SessionLocal() as db:
                recording = db.query(Recording).filter(Recording.path == file_path).first()
                return recording.id if recording else None
        except Exception:
            return None
    
    async def _verify_and_enqueue_post_processing(self, stream_id: int, recording_id: int, ts_file_path: str, 
                                                   output_dir: str, streamer_name: str, started_at: str) -> bool:
        """
        Verify that queue service is running and enqueue task with verification
        
        This method ensures that:
        1. The background queue service is actually running
        2. The task is successfully enqueued
        3. The task appears in the queue status
        4. If queue is not responsive, attempts to restart it
        """
        try:
            logger.info(f"🔍 VERIFYING_QUEUE_SERVICE: recording_id={recording_id}")
            
            # First attempt: Try to enqueue normally
            initial_success = await enqueue_recording_post_processing(
                stream_id=stream_id,
                recording_id=recording_id,
                ts_file_path=ts_file_path,
                output_dir=output_dir,
                streamer_name=streamer_name,
                started_at=started_at,
                cleanup_ts_file=True
            )
            
            if not initial_success:
                logger.warning(f"⚠️ INITIAL_ENQUEUE_FAILED: recording_id={recording_id}")
                return False
            
            # Wait a moment for task to be registered
            await asyncio.sleep(2)
            
            # Verify the task actually exists in the queue
            queue_status = await self._check_queue_status_via_api()
            
            if queue_status is None:
                logger.error(f"❌ QUEUE_NOT_RESPONSIVE: recording_id={recording_id}")
                
                # Attempt to restart queue service
                restart_success = await self._attempt_queue_restart()
                if restart_success:
                    # Retry enqueuing after restart
                    logger.info(f"🔄 RETRY_AFTER_RESTART: recording_id={recording_id}")
                    retry_success = await enqueue_recording_post_processing(
                        stream_id=stream_id,
                        recording_id=recording_id,
                        ts_file_path=ts_file_path,
                        output_dir=output_dir,
                        streamer_name=streamer_name,
                        started_at=started_at,
                        cleanup_ts_file=True
                    )
                    return retry_success
                else:
                    logger.error(f"❌ QUEUE_RESTART_FAILED: recording_id={recording_id}")
                    return False
            
            # Check if our specific task is in the queue
            task_found = False
            if queue_status and 'queues' in queue_status:
                for queue_name, queue_info in queue_status['queues'].items():
                    if 'tasks' in queue_info:
                        for task in queue_info['tasks']:
                            # Check if this task matches our recording
                            if (isinstance(task, dict) and 
                                task.get('recording_id') == recording_id):
                                task_found = True
                                logger.info(f"✅ TASK_VERIFIED_IN_QUEUE: recording_id={recording_id}, queue={queue_name}")
                                break
                    if task_found:
                        break
            
            if not task_found:
                logger.warning(f"⚠️ TASK_NOT_FOUND_IN_QUEUE: recording_id={recording_id}, but enqueue returned success")
                # Still return True since enqueue reported success
                # This might be a timing issue where task started processing immediately
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error in queue verification: {e}", exc_info=True)
            return False
    
    async def _check_queue_status_via_api(self) -> Optional[dict]:
        """Check queue status via internal API call"""
        try:
            # Import here to avoid circular imports
            import aiohttp
            
            # Try to connect to the FastAPI app's queue endpoint
            api_urls = [
                "http://localhost:8000/api/admin/background-queue/status",
                "http://127.0.0.1:8000/api/admin/background-queue/status"
            ]
            
            for url in api_urls:
                try:
                    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                        async with session.get(url) as response:
                            if response.status == 200:
                                data = await response.json()
                                logger.debug(f"✅ QUEUE_API_CONNECTED: {url}")
                                return data
                            else:
                                logger.debug(f"⚠️ Queue API returned status {response.status}: {url}")
                except aiohttp.ClientError as e:
                    logger.debug(f"⚠️ Could not connect to queue API: {url} - {e}")
                    continue
            
            logger.warning("⚠️ QUEUE_API_NOT_ACCESSIBLE: All endpoints failed")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error checking queue status: {e}")
            return None
    
    async def _attempt_queue_restart(self) -> bool:
        """Attempt to restart the background queue service"""
        try:
            logger.info("🔄 ATTEMPTING_QUEUE_RESTART")
            
            # Try to restart the queue service through the background queue system
            try:
                from app.services.init.background_queue_init import restart_background_queue
                
                success = await restart_background_queue()
                if success:
                    logger.info("✅ QUEUE_RESTART_SUCCESS")
                    # Wait for service to stabilize
                    await asyncio.sleep(5)
                    return True
                else:
                    logger.error("❌ QUEUE_RESTART_FAILED")
                    return False
                    
            except ImportError:
                # If restart function doesn't exist, try alternative approach
                logger.warning("⚠️ Queue restart function not available, attempting alternative")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error attempting queue restart: {e}")
            return False
    
    async def _batch_find_recordings_by_paths(self, file_paths: List[str]) -> Dict[str, Optional[int]]:
        """Batch find recording IDs by file paths for improved performance"""
        result = {}
        try:
            with SessionLocal() as db:
                # Query all recordings with matching paths in one go
                recordings = db.query(Recording).filter(Recording.path.in_(file_paths)).all()
                
                # Create a mapping of path -> recording_id
                path_to_id = {r.path: r.id for r in recordings}
                
                # Fill result dict with all requested paths
                for path in file_paths:
                    result[path] = path_to_id.get(path)
                    
        except Exception as e:
            logger.error(f"Error in batch recording lookup: {e}")
            # Fallback to empty results
            for path in file_paths:
                result[path] = None
                
        return result
    
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
    
    async def _final_queue_verification(self, stats: RecoveryStats):
        """Final verification that triggered tasks are actually in the queue"""
        try:
            logger.info(f"🔍 FINAL_QUEUE_VERIFICATION: Checking {stats.triggered_post_processing} triggered tasks")
            
            # Wait a moment for all tasks to be registered
            await asyncio.sleep(3)
            
            queue_status = await self._check_queue_status_via_api()
            if queue_status is None:
                logger.error("❌ QUEUE_VERIFICATION_FAILED: Queue not responsive")
                return
            
            # Count total tasks in all queues
            total_tasks = 0
            active_tasks = 0
            
            if 'queues' in queue_status:
                for queue_name, queue_info in queue_status['queues'].items():
                    if 'tasks' in queue_info:
                        queue_task_count = len(queue_info['tasks'])
                        total_tasks += queue_task_count
                        logger.info(f"📊 QUEUE_STATUS: {queue_name} has {queue_task_count} tasks")
                    
                    if 'active_workers' in queue_info:
                        active_tasks += queue_info['active_workers']
            
            logger.info(f"📊 FINAL_QUEUE_STATUS: {total_tasks} total tasks, {active_tasks} active workers")
            
            if total_tasks == 0 and stats.triggered_post_processing > 0:
                logger.warning(f"⚠️ QUEUE_VERIFICATION_WARNING: Triggered {stats.triggered_post_processing} tasks but queue appears empty")
                logger.warning("⚠️ Tasks may have been processed immediately or queue service might have issues")
            else:
                logger.info(f"✅ QUEUE_VERIFICATION_OK: Queue has {total_tasks} tasks")
                
        except Exception as e:
            logger.error(f"❌ Error in final queue verification: {e}")
    
    async def _final_database_cleanup(self, stats: RecoveryStats):
        """Final database cleanup after recovery"""
        try:
            with SessionLocal() as db:
                # Remove any recordings that have no associated files and are very old
                cutoff = datetime.now() - timedelta(days=self.DATABASE_CLEANUP_DAYS)
                
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
    
    async def _concatenate_segments_util(self, segments_dir: Path, output_path: Path) -> Optional[Path]:
        """Utility method to concatenate segments using ffmpeg"""
        try:
            import subprocess
            
            # Get all segment files in order
            segment_files = sorted(segments_dir.glob('*.ts'), key=lambda x: x.name)
            if not segment_files:
                logger.error(f"No segment files found in {segments_dir}")
                return None
            
            # Create concat list file
            concat_file = segments_dir / 'concat_list.txt'
            with open(concat_file, 'w') as f:
                for segment in segment_files:
                    f.write(f"file '{segment.absolute()}'\n")
            
            # Run ffmpeg concatenation
            cmd = [
                'ffmpeg',
                '-f', 'concat',
                '-safe', '0',
                '-i', str(concat_file),
                '-c', 'copy',
                '-avoid_negative_ts', 'make_zero',
                str(output_path)
            ]
            
            logger.info(f"Running concatenation: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600  # 1 hour timeout
            )
            
            # Clean up concat file
            if concat_file.exists():
                concat_file.unlink()
            
            if result.returncode == 0 and output_path.exists():
                logger.info(f"✅ Concatenation successful: {output_path}")
                return output_path
            else:
                logger.error(f"❌ FFmpeg concatenation failed: {result.stderr}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error in segment concatenation: {e}")
            return None
    
    async def _get_active_recording_paths(self) -> set:
        """Get paths of currently active recordings to avoid processing them"""
        active_paths = set()
        try:
            # Get active recordings from the recording service with robust error handling
            try:
                from app.services.recording.recording_service import RecordingService
                recording_service = RecordingService()
                
                active_recordings = recording_service.get_active_recordings()
                for recording_data in active_recordings.values():
                    if 'file_path' in recording_data and recording_data['file_path']:
                        active_paths.add(recording_data['file_path'])
                        
                logger.debug(f"Retrieved {len(active_recordings)} active recordings from RecordingService")
                        
            except Exception as e:
                logger.error(f"❌ CRITICAL: Failed to get active recordings from RecordingService: {e}")
                # This is a critical error - we cannot safely proceed without knowing active recordings
                # Raise the exception to abort the recovery process
                raise RuntimeError(f"Cannot safely perform recovery without active recording information: {e}")
                        
            # Also check database for recordings with status 'recording' that are very recent
            with SessionLocal() as db:
                recent_cutoff = datetime.now() - timedelta(hours=self.ACTIVE_RECORDING_CHECK_HOURS)
                active_db_recordings = db.query(Recording).filter(
                    Recording.status == 'recording',
                    Recording.start_time >= recent_cutoff
                ).all()
                
                for recording in active_db_recordings:
                    if recording.path:
                        active_paths.add(recording.path)
                        
            logger.info(f"🔍 ACTIVE_RECORDINGS_CHECK: Found {len(active_paths)} active recording paths")
            return active_paths
            
        except RuntimeError:
            # Re-raise critical errors
            raise
        except Exception as e:
            logger.error(f"❌ CRITICAL: Error getting active recording paths: {e}")
            # For any other database errors, we also cannot safely proceed
            raise RuntimeError(f"Cannot safely perform recovery due to database error: {e}")

# Singleton instance
_unified_recovery_service = None

async def get_unified_recovery_service() -> UnifiedRecoveryService:
    """Get the singleton unified recovery service"""
    global _unified_recovery_service
    if _unified_recovery_service is None:
        _unified_recovery_service = UnifiedRecoveryService()
    return _unified_recovery_service
