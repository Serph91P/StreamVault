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
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from sqlalchemy.orm import joinedload

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

                    stats.total_size_gb += recording_info.get("size_gb", 0)

                except Exception as e:
                    logger.error(f"❌ Failed to process orphaned recording {recording_info.get('recording_id')}: {e}")

            # Step 4: Process failed post-processing (files exist but post-processing failed)
            for recording_info in failed_recordings:
                try:
                    if not dry_run:
                        success = await self._retry_post_processing(recording_info)
                        if success:
                            stats.triggered_post_processing += 1
                            logger.info(
                                f"✅ POST_PROCESSING_TRIGGERED: recording_id={recording_info.get('recording_id')}"
                            )
                        else:
                            logger.warning(
                                f"⚠️ POST_PROCESSING_TRIGGER_FAILED: recording_id={recording_info.get('recording_id')}"
                            )

                except Exception as e:
                    logger.error(
                        f"❌ Failed to retry post-processing for {recording_info.get('recording_id')}: {e}",
                        exc_info=True,
                    )

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
                f"triggered_pp={stats.triggered_post_processing}, size={stats.total_size_gb:.1f}GB",
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
                        if item.is_dir() and item.name.endswith("_segments"):
                            # Check if segments exist
                            segment_files = list(item.glob("*.ts"))
                            if not segment_files:
                                continue

                            # Check age
                            newest_segment = max(segment_files, key=lambda f: f.stat().st_mtime)
                            segment_time = datetime.fromtimestamp(newest_segment.stat().st_mtime)

                            if segment_time < cutoff_time:
                                continue

                            # Check if final files exist
                            expected_ts = season_dir / item.name.replace("_segments", ".ts")
                            expected_mp4 = season_dir / item.name.replace("_segments", ".mp4")

                            # CRITICAL: Skip if this recording is currently active
                            if str(expected_ts) in active_recording_paths:
                                logger.info(f"⚠️ SKIPPING_ACTIVE_RECORDING: {expected_ts} is currently being recorded")
                                continue

                            if not expected_ts.exists() and not expected_mp4.exists():
                                # This is orphaned - has segments but no final files
                                total_size = sum(f.stat().st_size for f in segment_files)

                                potential_orphans.append(
                                    {
                                        "streamer_name": streamer_dir.name,
                                        "segments_dir": item,
                                        "expected_ts_path": expected_ts,
                                        "expected_mp4_path": expected_mp4,
                                        "segment_files": segment_files,
                                        "size_gb": total_size / (1024**3),
                                        "segment_time": segment_time,
                                    }
                                )

            # Batch query all recording IDs at once
            if potential_orphans:
                expected_paths = [str(orphan["expected_ts_path"]) for orphan in potential_orphans]
                recording_map = await self._batch_find_recordings_by_paths(expected_paths)

                # Now combine the data
                for orphan_data in potential_orphans:
                    expected_ts_str = str(orphan_data["expected_ts_path"])
                    recording_id = recording_map.get(expected_ts_str)

                    logger.info(
                        f"🔍 FOUND_ORPHANED: streamer={orphan_data['streamer_name']}, recording_id={recording_id}, size={orphan_data['size_gb']:.1f}GB"
                    )

                    orphan_data["recording_id"] = recording_id
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
                recent_recordings = (
                    db.query(Recording)
                    .join(Stream)
                    .join(Streamer)
                    .options(joinedload(Recording.stream).joinedload(Stream.streamer))
                    .filter(Recording.status.in_(["completed", "stopped"]), Recording.start_time >= cutoff_time)
                    .all()
                )

                for recording in recent_recordings:
                    if not recording.path:
                        continue

                    # CRITICAL: Skip if this recording is currently active
                    if recording.path in active_recording_paths:
                        logger.info(f"⚠️ SKIPPING_ACTIVE_RECORDING: {recording.path} is currently being recorded")
                        continue

                    ts_path = Path(recording.path)
                    mp4_path = ts_path.with_suffix(".mp4")

                    # Case 1: TS file exists but no MP4 (post-processing never started or failed)
                    if ts_path.exists() and not mp4_path.exists():
                        logger.info(
                            f"🔍 FOUND_FAILED_PP: recording_id={recording.id}, streamer={recording.stream.streamer.username}, missing MP4"
                        )
                        failed.append(
                            {
                                "recording_id": recording.id,
                                "recording": recording,
                                "ts_path": ts_path,
                                "mp4_path": mp4_path,
                                "type": "missing_mp4",
                                "streamer_name": recording.stream.streamer.username,
                            }
                        )

                    # Case 2: Neither TS nor MP4 exists but segments might exist
                    elif not ts_path.exists() and not mp4_path.exists():
                        segments_dir = Path(str(ts_path).replace(".ts", "_segments"))
                        if segments_dir.exists() and list(segments_dir.glob("*.ts")):
                            logger.info(
                                f"🔍 FOUND_FAILED_PP: recording_id={recording.id}, streamer={recording.stream.streamer.username}, needs concatenation"
                            )
                            failed.append(
                                {
                                    "recording_id": recording.id,
                                    "recording": recording,
                                    "segments_dir": segments_dir,
                                    "ts_path": ts_path,
                                    "mp4_path": mp4_path,
                                    "type": "needs_concatenation",
                                    "streamer_name": recording.stream.streamer.username,
                                }
                            )
                        else:
                            logger.debug(
                                f"🔍 SKIP_UNRECOVERABLE: recording_id={recording.id}, no TS file and no segments found"
                            )

        except Exception as e:
            logger.error(f"Error scanning failed post-processing: {e}")

        logger.info(
            f"🔍 FAILED_PP_SCAN_COMPLETE: Found {len(failed)} failed post-processing recordings across all streamers"
        )
        return failed

    async def _process_orphaned_recording(self, recording_info: Dict[str, Any]) -> bool:
        """Process a single orphaned recording intelligently

        CRITICAL LOGIC:
        - If streamer LIVE: Resume recording (new segment) → Post-processing happens when stream ends naturally
        - If streamer OFFLINE: Only then concatenate existing segments and trigger post-processing

        This prevents premature post-processing while stream is still active!
        """
        try:
            segments_dir = recording_info["segments_dir"]
            expected_ts_path = recording_info["expected_ts_path"]
            recording_id = recording_info["recording_id"]
            streamer_name = recording_info["streamer_name"]

            logger.info(f"🔄 PROCESSING_ORPHANED: recording_id={recording_id}, streamer={streamer_name}")

            # STEP 1: Check if streamer is still live
            is_still_live = await self._check_if_streamer_still_live(recording_id)

            if is_still_live:
                # Streamer is LIVE - resume recording, let normal workflow handle post-processing
                logger.info(f"📡 Streamer {streamer_name} is still LIVE - resuming recording")
                logger.info("📌 Existing segments will be merged when stream ends (normal workflow)")

                # First check if there's already an active recording for this stream
                # If so, we should NOT try to resume - instead concatenate the old segments
                has_active_recording = await self._check_if_stream_has_active_recording(recording_id)
                
                if has_active_recording:
                    # Another recording is already running for this stream
                    # The old segments belong to a previous episode - concatenate them now
                    logger.info(f"📡 Stream already has an active recording - processing old segments separately")
                    logger.info("📌 Old segments will be concatenated as a separate episode")
                    # Fall through to concatenation logic below
                else:
                    success = await self._resume_live_recording(recording_id, segments_dir, streamer_name)
                    if success:
                        logger.info("✅ Recording resumed - segments will be handled by ProcessManager")
                        # DO NOT trigger post-processing here - it happens when recording stops!
                        return True
                    else:
                        logger.warning(f"⚠️ Failed to resume recording for {streamer_name}")
                        # If resume failed, check if maybe a recording started in the meantime
                        has_active_now = await self._check_if_stream_has_active_recording(recording_id)
                        if has_active_now:
                            logger.info("📡 Another recording started - processing old segments separately")
                            # Fall through to concatenation logic below
                        else:
                            logger.info("📌 Segments remain on disk - will retry on next recovery scan")
                            return False

            # STEP 2: Streamer is OFFLINE or has a different recording running
            # Post-process these orphaned segments NOW
            if not is_still_live:
                logger.info(f"🛑 Streamer {streamer_name} is OFFLINE - starting post-processing for orphaned segments")
            else:
                logger.info(f"🛑 Streamer {streamer_name} has active recording - processing old segments as separate episode")
            logger.info(f"📦 This will concatenate {len(list(segments_dir.glob('*.ts')))} segments in background")

            # Log to dedicated file
            logging_service.log_post_processing_activity(
                "CONCATENATION_START",
                streamer_name,
                f"Starting concatenation for orphaned recording {recording_id}: {segments_dir.name}",
            )

            # Use async FFmpeg concatenation (non-blocking)
            # This runs in background and doesn't block frontend startup
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
                    f"Successfully concatenated orphaned recording {recording_id}",
                )

                return True
            else:
                logger.error(f"❌ CONCATENATION_FAILED: {segments_dir}")
                logging_service.log_post_processing_activity(
                    "CONCATENATION_FAILED", streamer_name, f"Failed to concatenate orphaned recording {recording_id}"
                )
                return False

        except Exception as e:
            logger.error(f"❌ Error processing orphaned recording: {e}")
            return False

    async def _retry_post_processing(self, recording_info: Dict[str, Any]) -> bool:
        """Retry post-processing for a failed recording"""
        try:
            recording_id = recording_info["recording_id"]
            ts_path = recording_info["ts_path"]
            streamer_name = recording_info["streamer_name"]

            logger.info(f"🔄 RETRY_POST_PROCESSING: recording_id={recording_id}")

            # If we need concatenation first
            if recording_info["type"] == "needs_concatenation":
                segments_dir = recording_info["segments_dir"]
                result = await self._process_orphaned_recording(
                    {
                        "recording_id": recording_id,
                        "segments_dir": segments_dir,
                        "expected_ts_path": ts_path,
                        "streamer_name": streamer_name,
                    }
                )
                return result

            # Check if the TS file actually exists before triggering post-processing
            if not ts_path.exists():
                logger.warning(
                    f"⚠️ SKIP_POST_PROCESSING: recording_id={recording_id}, TS file no longer exists: {ts_path}"
                )
                return False

            # Otherwise just trigger post-processing
            return await self._trigger_post_processing(recording_id, str(ts_path), streamer_name)

        except Exception as e:
            logger.error(f"❌ Error retrying post-processing: {e}")
            return False

    async def _trigger_post_processing(
        self, recording_id: Optional[int], ts_file_path: str, streamer_name: str
    ) -> bool:
        """Trigger post-processing for a recording"""
        try:
            # Skip if no recording_id
            if recording_id is None:
                logger.warning(f"⚠️ Cannot trigger post-processing without recording_id for {ts_file_path}")
                return False

            # CRITICAL: Check if TS file exists before proceeding
            ts_path = Path(ts_file_path)
            if not ts_path.exists():
                logger.warning(
                    f"⚠️ SKIP_POST_PROCESSING: recording_id={recording_id}, TS file does not exist: {ts_file_path}"
                )
                return False

            # Check file size to ensure it's not empty/corrupted
            file_size = ts_path.stat().st_size
            if file_size < MIN_TS_FILE_SIZE_BYTES:  # Less than 1KB
                logger.warning(
                    f"⚠️ SKIP_POST_PROCESSING: recording_id={recording_id}, TS file too small ({file_size} bytes): {ts_file_path}"
                )
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
                    logger.warning(
                        f"⚠️ Recording {recording_id} has no start_time; cannot trigger post-processing accurately."
                    )
                    return False

            logger.info(
                f"🔄 TRIGGERING_POST_PROCESSING: recording_id={recording_id}, file_size={file_size / 1024 / 1024:.1f}MB"
            )

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

            # Use the background queue system directly
            success = await enqueue_recording_post_processing(
                stream_id=stream_id,
                recording_id=recording_id,
                ts_file_path=ts_file_path,
                output_dir=str(output_dir),
                streamer_name=streamer_name,
                started_at=started_at,
                cleanup_ts_file=True,
            )

            if success:
                logger.info(f"✅ POST_PROCESSING_TRIGGERED: recording_id={recording_id}")
                logging_service.log_post_processing_activity(
                    "POST_PROCESSING_START",
                    streamer_name,
                    f"Successfully triggered post-processing for recording {recording_id}",
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

    async def _batch_find_recordings_by_paths(self, file_paths: List[str]) -> Dict[str, Optional[int]]:
        """Batch find recording IDs by file paths for improved performance

        Enhanced lookup strategy:
        1. Try exact path match first
        2. If no match, try matching by filename pattern in the same directory
        3. As last resort, create a new Recording entry if we can match streamer/stream
        """
        result = {}
        try:
            with SessionLocal() as db:
                # Query all recordings with matching paths in one go (exact match)
                recordings = db.query(Recording).filter(Recording.path.in_(file_paths)).all()

                # Create a mapping of path -> recording_id
                path_to_id = {r.path: r.id for r in recordings}

                # For paths still not found, try filename-based lookup
                for path in file_paths:
                    if path in path_to_id:
                        result[path] = path_to_id[path]
                        continue

                    # Try to find by filename pattern (without extension)
                    filename_stem = Path(path).stem
                    if filename_stem:
                        # Search for recordings with similar filename in same season folder
                        parent_dir = str(Path(path).parent)
                        matching_rec = (
                            db.query(Recording)
                            .filter(
                                Recording.path.ilike(f"%{parent_dir}%"),
                                Recording.path.ilike(f"%{filename_stem}%"),
                            )
                            .first()
                        )
                        if matching_rec:
                            result[path] = matching_rec.id
                            logger.info(
                                f"Found recording {matching_rec.id} via filename pattern match for {path}"
                            )
                            continue

                    # Last resort: try to create recording from segments directory info
                    recording_id = await self._create_recording_from_orphaned_path(db, path)
                    if recording_id:
                        result[path] = recording_id
                        logger.info(f"Created new recording {recording_id} for orphaned path {path}")
                    else:
                        result[path] = None

        except Exception as e:
            logger.error(f"Error in batch recording lookup: {e}")
            # Fallback to empty results
            for path in file_paths:
                result[path] = None

        return result

    def _parse_timestamp_from_filename(self, filename: str) -> Optional[datetime]:
        """Extract stream start timestamp from filename

        Expected format: "StreamerName - S202601E19 - 2026-01-08T22-00-00.ts"
        The timestamp at the end represents when the stream started.
        """
        import re

        # Pattern for ISO-like timestamp: YYYY-MM-DDTHH-MM-SS
        pattern = r"(\d{4})-(\d{2})-(\d{2})T(\d{2})-(\d{2})-(\d{2})"
        match = re.search(pattern, filename)

        if match:
            try:
                year, month, day, hour, minute, second = map(int, match.groups())
                return datetime(year, month, day, hour, minute, second)
            except ValueError:
                pass

        return None

    def _parse_episode_info_from_filename(self, filename: str) -> Optional[Dict[str, Any]]:
        """Extract season and episode info from filename

        Expected format: "StreamerName - S202601E19 - 2026-01-08T22-00-00.ts"
        S202601 = Season (Year 2026, Month 01)
        E19 = Episode number 19

        Returns dict with: year, month, episode_number
        """
        import re

        # Pattern for season/episode: S[YYYYMM]E[number]
        pattern = r"S(\d{4})(\d{2})E(\d+)"
        match = re.search(pattern, filename)

        if match:
            try:
                year = int(match.group(1))
                month = int(match.group(2))
                episode = int(match.group(3))
                return {
                    "year": year,
                    "month": month,
                    "episode_number": episode,
                }
            except ValueError:
                pass

        return None

    async def _create_recording_from_orphaned_path(self, db, file_path: str) -> Optional[int]:
        """Create a new Recording entry for an orphaned segments directory

        This is needed when:
        - Segments exist on disk but no Recording entry in DB
        - Usually happens after server restart during recording

        Matching logic (in order of priority):
        1. BEST: Match by episode_number + year/month from filename (S202601E19)
           - If Stream with same episode_number exists in that month, use it
        2. GOOD: Match by timestamp within ±15 minutes
        3. FALLBACK: Match newest incomplete stream (if no filename info)
        4. LAST RESORT: Create new Stream entry
        """
        try:
            path = Path(file_path)
            # Extract streamer name from path: /recordings/StreamerName/Season .../filename.ts
            parts = path.parts

            # Find recordings directory in path
            rec_idx = None
            for i, part in enumerate(parts):
                if part == "recordings" and i + 1 < len(parts):
                    rec_idx = i
                    break

            if rec_idx is None or rec_idx + 1 >= len(parts):
                logger.debug(f"Cannot extract streamer from path: {file_path}")
                return None

            streamer_name = parts[rec_idx + 1]

            # Find streamer in database
            streamer = db.query(Streamer).filter(Streamer.username.ilike(streamer_name)).first()
            if not streamer:
                logger.warning(f"Streamer '{streamer_name}' not found in database for path {file_path}")
                return None

            # Extract info from filename
            filename_timestamp = self._parse_timestamp_from_filename(path.name)
            episode_info = self._parse_episode_info_from_filename(path.name)
            matched_stream = None

            # PRIORITY 1: Match by episode number (most reliable)
            if episode_info:
                episode_num = episode_info["episode_number"]
                year = episode_info["year"]
                month = episode_info["month"]

                # Find stream with matching episode number in the same month
                # The month boundaries help ensure we don't match wrong streams
                month_start = datetime(year, month, 1)
                if month == 12:
                    month_end = datetime(year + 1, 1, 1)
                else:
                    month_end = datetime(year, month + 1, 1)

                matched_stream = (
                    db.query(Stream)
                    .filter(
                        Stream.streamer_id == streamer.id,
                        Stream.episode_number == episode_num,
                        Stream.started_at >= month_start,
                        Stream.started_at < month_end,
                    )
                    .outerjoin(Recording, Recording.stream_id == Stream.id)
                    .filter(Recording.id.is_(None) | (Recording.status != "completed"))
                    .first()
                )

                if matched_stream:
                    logger.info(
                        f"✅ Matched orphaned recording by EPISODE NUMBER: Stream {matched_stream.id} "
                        f"(episode={episode_num}, month={year}-{month:02d})"
                    )

            # PRIORITY 2: Match by timestamp if episode didn't match
            if not matched_stream and filename_timestamp:
                # Look for a stream that started within ±15 minutes of the filename timestamp
                time_tolerance = timedelta(minutes=15)
                min_time = filename_timestamp - time_tolerance
                max_time = filename_timestamp + time_tolerance

                matched_stream = (
                    db.query(Stream)
                    .filter(
                        Stream.streamer_id == streamer.id,
                        Stream.started_at >= min_time,
                        Stream.started_at <= max_time,
                    )
                    .outerjoin(Recording, Recording.stream_id == Stream.id)
                    .filter(Recording.id.is_(None) | (Recording.status != "completed"))
                    .order_by(Stream.started_at.desc())
                    .first()
                )

                if matched_stream:
                    logger.info(
                        f"✅ Matched orphaned recording by TIMESTAMP: Stream {matched_stream.id} "
                        f"(filename_ts={filename_timestamp}, stream_started={matched_stream.started_at})"
                    )

            # PRIORITY 3: Fallback - newest incomplete stream (only if no info in filename)
            if not matched_stream and not filename_timestamp and not episode_info:
                logger.debug(f"No info in filename, falling back to newest incomplete stream")
                matched_stream = (
                    db.query(Stream)
                    .filter(Stream.streamer_id == streamer.id)
                    .outerjoin(Recording, Recording.stream_id == Stream.id)
                    .filter(Recording.id.is_(None) | (Recording.status != "completed"))
                    .order_by(Stream.started_at.desc())
                    .first()
                )

                if matched_stream:
                    logger.info(
                        f"⚠️ Matched orphaned recording by FALLBACK (newest incomplete): "
                        f"Stream {matched_stream.id}"
                    )

            # LAST RESORT: Create new stream
            if not matched_stream:
                stream_started_at = filename_timestamp if filename_timestamp else datetime.now()
                episode_num_for_new = episode_info["episode_number"] if episode_info else None

                logger.info(
                    f"📝 Creating NEW Stream entry for orphaned recording of {streamer_name} "
                    f"(started_at={stream_started_at}, episode={episode_num_for_new})"
                )
                matched_stream = Stream(
                    streamer_id=streamer.id,
                    title=path.stem,  # Use filename as title
                    started_at=stream_started_at,
                    episode_number=episode_num_for_new,
                    is_live=False,
                )
                db.add(matched_stream)
                db.flush()

            # Create recording entry with proper timestamp
            recording_start_time = filename_timestamp if filename_timestamp else datetime.now()

            new_recording = Recording(
                stream_id=matched_stream.id,
                path=file_path,
                status="stopped",  # Will be updated to completed after concatenation
                start_time=recording_start_time,
            )
            db.add(new_recording)
            db.commit()

            logger.info(
                f"Created Recording id={new_recording.id} for orphaned segments: "
                f"streamer={streamer_name}, stream_id={matched_stream.id}, "
                f"episode={matched_stream.episode_number}, start_time={recording_start_time}"
            )

            return new_recording.id

        except Exception as e:
            logger.error(f"Error creating recording from orphaned path: {e}", exc_info=True)
            try:
                db.rollback()
            except Exception:
                pass
            return None

    async def _update_recording_after_concatenation(self, recording_id: int, file_path: str):
        """Update recording in database after successful concatenation"""
        try:
            with SessionLocal() as db:
                recording = db.query(Recording).filter(Recording.id == recording_id).first()
                if recording:
                    recording.status = "completed"
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
                stuck_recordings = db.query(Recording).filter(Recording.status == "recording").all()

                for recording in stuck_recordings:
                    # Check if recording should be completed
                    if recording.path:
                        ts_path = Path(recording.path)
                        segments_dir = Path(str(recording.path).replace(".ts", "_segments"))

                        # If TS file exists, mark as completed
                        if ts_path.exists():
                            if not dry_run:
                                recording.status = "completed"
                                if not recording.end_time:
                                    recording.end_time = datetime.utcnow()
                                stats.updated_database_entries += 1

                        # If segments exist but no TS file, this will be handled by orphaned recovery
                        elif segments_dir.exists() and list(segments_dir.glob("*.ts")):
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
                cutoff = datetime.now() - timedelta(days=self.DATABASE_CLEANUP_DAYS)

                orphaned_db_records = (
                    db.query(Recording)
                    .filter(Recording.status == "recording", Recording.start_time < cutoff, Recording.path.is_(None))
                    .all()
                )

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
            pass

            # Get all segment files in order
            segment_files = sorted(segments_dir.glob("*.ts"), key=lambda x: x.name)
            if not segment_files:
                logger.error(f"No segment files found in {segments_dir}")
                return None

            # Create concat list file
            concat_file = segments_dir / "concat_list.txt"
            with open(concat_file, "w") as f:
                for segment in segment_files:
                    f.write(f"file '{segment.absolute()}'\n")

            # Run ffmpeg concatenation
            cmd = [
                "ffmpeg",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_file),
                "-c",
                "copy",
                "-avoid_negative_ts",
                "make_zero",
                str(output_path),
            ]

            logger.info(f"Running concatenation: {' '.join(cmd)}")

            # CRITICAL: Use async subprocess to prevent blocking the event loop
            # This prevents frontend from being blocked during startup recovery
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            try:
                # Wait for completion with 1 hour timeout
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=3600)
            except asyncio.TimeoutError:
                logger.error("❌ FFmpeg concatenation timeout (1 hour)")
                process.kill()
                await process.wait()
                return None

            # Clean up concat file
            if concat_file.exists():
                concat_file.unlink()

            if process.returncode == 0 and output_path.exists():
                logger.info(f"✅ Concatenation successful: {output_path}")
                return output_path
            else:
                logger.error(f"❌ FFmpeg concatenation failed: {stderr.decode() if stderr else 'Unknown error'}")
                return None

        except Exception as e:
            logger.error(f"❌ Error in segment concatenation: {e}")
            return None

    async def _check_if_streamer_still_live(self, recording_id: int) -> bool:
        """Check if the streamer for this recording is still live on Twitch"""
        try:
            with SessionLocal() as db:
                recording = (
                    db.query(Recording)
                    .options(joinedload(Recording.stream).joinedload(Stream.streamer))
                    .filter(Recording.id == recording_id)
                    .first()
                )

                if not recording or not recording.stream or not recording.stream.streamer:
                    return False

                streamer = recording.stream.streamer

                # Check Twitch API for live status
                from app.services.streamer_service import StreamerService
                from app.services.communication.websocket_manager import websocket_manager
                from app.events.handler_registry import EventHandlerRegistry
                from app.config.settings import settings

                event_handler_registry = EventHandlerRegistry(connection_manager=websocket_manager, settings=settings)

                streamer_service = StreamerService(db, websocket_manager, event_handler_registry)
                is_live = await streamer_service.check_streamer_live_status(streamer.twitch_id)

                logger.info(f"📡 Live status check for {streamer.username}: {'LIVE' if is_live else 'OFFLINE'}")
                return is_live

        except Exception as e:
            logger.error(f"❌ Error checking live status for recording {recording_id}: {e}")
            return False  # Assume offline on error

    async def _check_if_stream_has_active_recording(self, orphaned_recording_id: int) -> bool:
        """Check if the stream already has a different active recording running.
        
        This is important when we find orphaned segments but a new recording
        has already started for the same stream. In this case, we should NOT
        try to resume (which would fail), but instead concatenate the old
        segments immediately.
        """
        try:
            with SessionLocal() as db:
                # Get the stream_id for the orphaned recording
                orphaned_recording = db.query(Recording).filter(
                    Recording.id == orphaned_recording_id
                ).first()
                
                if not orphaned_recording:
                    return False
                
                stream_id = orphaned_recording.stream_id
                
                # Check if there's another recording with status='recording' for this stream
                # that is NOT the orphaned recording
                active_recording = db.query(Recording).filter(
                    Recording.stream_id == stream_id,
                    Recording.id != orphaned_recording_id,
                    Recording.status == "recording"
                ).first()
                
                if active_recording:
                    logger.info(
                        f"🔍 Found active recording {active_recording.id} for stream {stream_id} "
                        f"(orphaned recording: {orphaned_recording_id})"
                    )
                    return True
                
                # Also check via RecordingService for in-memory active recordings
                try:
                    from app.services.recording.recording_service import RecordingService
                    recording_service = RecordingService()
                    active_recordings = recording_service.get_active_recordings()
                    
                    for rec_id, rec_data in active_recordings.items():
                        if rec_data.get("stream_id") == stream_id and rec_id != orphaned_recording_id:
                            logger.info(
                                f"🔍 Found in-memory active recording {rec_id} for stream {stream_id} "
                                f"(orphaned recording: {orphaned_recording_id})"
                            )
                            return True
                except Exception as e:
                    logger.debug(f"Could not check in-memory recordings: {e}")
                
                return False
                
        except Exception as e:
            logger.error(f"❌ Error checking for active recording: {e}")
            return False

    async def _resume_live_recording(self, recording_id: int, segments_dir: Path, streamer_name: str) -> bool:
        """Resume a live recording that was interrupted"""
        try:
            # Get recording service to resume recording
            from app.services.recording.recording_service import RecordingService
            from datetime import datetime, timezone

            recording_service = RecordingService()

            # Resume the recording (this will create a new segment in the same directory)
            logger.info(f"🔄 Attempting to resume live recording for {streamer_name} (recording_id={recording_id})")

            # Get stream_id and streamer_id from recording
            with SessionLocal() as db:
                recording = db.query(Recording).filter(Recording.id == recording_id).first()
                if not recording:
                    logger.error(f"❌ Recording {recording_id} not found")
                    return False

                stream_id = recording.stream_id
                streamer_id = recording.streamer_id

                # CRITICAL FIX: Mark OLD recording as "stopped" BEFORE starting a new one
                # This prevents duplicate jobs appearing in the Background Jobs UI
                now_utc = datetime.now(timezone.utc)
                recording.status = "stopped"
                recording.end_time = now_utc
                if recording.start_time:
                    recording.duration_seconds = int((now_utc - recording.start_time).total_seconds())
                db.commit()
                logger.info(f"📝 Marked old recording {recording_id} as stopped before resuming")

            # Start recording - this will automatically handle segment continuation
            success = await recording_service.start_recording(stream_id, streamer_id)

            if success:
                logger.info(f"✅ Successfully resumed recording for {streamer_name}")
                logging_service.log_post_processing_activity(
                    "RECORDING_RESUMED",
                    streamer_name,
                    f"Resumed live recording {recording_id} that was interrupted during restart",
                )
                return True
            else:
                logger.error(f"❌ Failed to resume recording for {streamer_name}")
                return False

        except Exception as e:
            logger.error(f"❌ Error resuming recording: {e}")
            return False

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
                    if "file_path" in recording_data and recording_data["file_path"]:
                        active_paths.add(recording_data["file_path"])

                logger.debug(f"Retrieved {len(active_recordings)} active recordings from RecordingService")

            except Exception as e:
                logger.error(f"❌ CRITICAL: Failed to get active recordings from RecordingService: {e}")
                # This is a critical error - we cannot safely proceed without knowing active recordings
                # Raise the exception to abort the recovery process
                raise RuntimeError(f"Cannot safely perform recovery without active recording information: {e}")

            # Also check database for recordings with status 'recording' that are very recent
            with SessionLocal() as db:
                recent_cutoff = datetime.now() - timedelta(hours=self.ACTIVE_RECORDING_CHECK_HOURS)
                active_db_recordings = (
                    db.query(Recording)
                    .filter(Recording.status == "recording", Recording.start_time >= recent_cutoff)
                    .all()
                )

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
