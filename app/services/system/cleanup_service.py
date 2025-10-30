import os
import json
import logging
import shutil
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any, Set
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, asc, func

from app.models import Stream, Streamer, RecordingSettings, StreamerRecordingSettings, FavoriteCategory, StreamMetadata
from app.database import SessionLocal
from app.services.recording.config_manager import ConfigManager
from app.schemas.recording import CleanupPolicyType

logger = logging.getLogger("streamvault")

class CleanupService:
    """Service for cleaning up old recordings with advanced policies"""
    
    @staticmethod
    def _parse_cleanup_policy(policy_str: Optional[str]) -> Optional[Dict[str, Any]]:
        """Parse the cleanup policy from JSON string"""
        if not policy_str:
            return None
            
        try:
            return json.loads(policy_str)
        except Exception as e:
            logger.error(f"Error parsing cleanup policy: {e}")
            return None
    
    @staticmethod
    def _get_effective_cleanup_policy(streamer_id: int, db: Session) -> Dict[str, Any]:
        """Get the effective cleanup policy for a streamer, considering overrides"""
        # First check streamer-specific settings
        streamer_settings = db.query(StreamerRecordingSettings).filter(
            StreamerRecordingSettings.streamer_id == streamer_id
        ).first()
        
        # If streamer has settings and explicitly wants to use custom policy
        if streamer_settings and not streamer_settings.use_global_cleanup_policy and streamer_settings.cleanup_policy:
            policy = CleanupService._parse_cleanup_policy(streamer_settings.cleanup_policy)
            if policy:
                logger.debug(f"Using streamer-specific cleanup policy for streamer {streamer_id}")
                return policy
        
        # Use global settings (default behavior)
        global_settings = db.query(RecordingSettings).first()
        if global_settings and global_settings.cleanup_policy:
            policy = CleanupService._parse_cleanup_policy(global_settings.cleanup_policy)
            if policy:
                logger.debug(f"Using global cleanup policy for streamer {streamer_id}")
                return policy
                
        # If no policy is set anywhere, fall back to the max_streams setting
        config_manager = ConfigManager()
        max_streams = config_manager.get_max_streams(streamer_id)
        
        # Return default policy
        logger.debug(f"Using default cleanup policy for streamer {streamer_id}")
        return {
            "type": CleanupPolicyType.COUNT.value,
            "threshold": max_streams if max_streams > 0 else 10,
            "preserve_favorites": True,
            "preserve_categories": []
        }
    
    @staticmethod
    def _get_favorite_categories(db: Session) -> Set[int]:
        """Get IDs of all favorite categories across all users"""
        favorite_categories = db.query(FavoriteCategory.category_id).all()
        return {fc[0] for fc in favorite_categories}
        
    @staticmethod
    async def cleanup_old_recordings(
        streamer_id: int, 
        db: Optional[Session] = None,
        custom_policy: Optional[Dict[str, Any]] = None
    ) -> Tuple[int, List[str]]:
        """
        Delete recordings based on the streamer's cleanup policy
        
        Args:
            streamer_id: ID of the streamer
            db: Database session
            custom_policy: Override the stored policy with this one
            
        Returns:
            Tuple containing (number of deleted recordings, list of deleted file paths)
        """
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True
            
        try:
            # Get the policy to apply
            policy = custom_policy or CleanupService._get_effective_cleanup_policy(streamer_id, db)
            policy_type = policy.get("type", CleanupPolicyType.COUNT.value)
            threshold = policy.get("threshold", 10)
            preserve_favorites = policy.get("preserve_favorites", True)
            preserve_categories = policy.get("preserve_categories", [])
            preserve_timeframe = policy.get("preserve_timeframe", {})
            
            # Get favorite categories if needed
            favorite_category_ids = set()
            if preserve_favorites:
                favorite_category_ids = CleanupService._get_favorite_categories(db)
            
            # Get all completed recordings for this streamer
            # Include streams with recording_path OR ended_at (completed recordings even if file deleted)
            streams_query = db.query(Stream).filter(
                Stream.streamer_id == streamer_id,
                Stream.ended_at.isnot(None)  # Only completed recordings (not currently recording)
            )
            
            # Log which policy is being applied for debugging
            logger.info(f"Applying cleanup policy for streamer {streamer_id}: type={policy_type}, threshold={threshold}")
            
            # Apply different logic based on policy type
            if policy_type == CleanupPolicyType.COUNT.value:
                return await CleanupService._apply_count_policy(
                    streamer_id, threshold, preserve_favorites, preserve_categories,
                    preserve_timeframe, favorite_category_ids, streams_query, db
                )
            elif policy_type == CleanupPolicyType.SIZE.value:
                return await CleanupService._apply_size_policy(
                    streamer_id, threshold, preserve_favorites, preserve_categories,
                    preserve_timeframe, favorite_category_ids, streams_query, db
                )
            elif policy_type == CleanupPolicyType.AGE.value:
                return await CleanupService._apply_age_policy(
                    streamer_id, threshold, preserve_favorites, preserve_categories,
                    preserve_timeframe, favorite_category_ids, streams_query, db
                )
            else:
                logger.warning(f"Unknown cleanup policy type: {policy_type}, falling back to COUNT")
                return await CleanupService._apply_count_policy(
                    streamer_id, 10, preserve_favorites, preserve_categories,
                    preserve_timeframe, favorite_category_ids, streams_query, db
                )
                
        except Exception as e:
            logger.error(f"Error cleaning up recordings: {e}", exc_info=True)
            return 0, []
        finally:
            if close_db:
                db.close()
                
    @staticmethod
    async def _apply_count_policy(
        streamer_id: int,
        threshold: int,
        preserve_favorites: bool,
        preserve_categories: List[str],
        preserve_timeframe: Dict[str, Any],
        favorite_category_ids: Set[int],
        streams_query,
        db: Session
    ) -> Tuple[int, List[str]]:
        """Apply count-based cleanup policy"""
        # First get all recordings ordered by start time (newest first)
        streams = streams_query.order_by(desc(Stream.started_at)).all()
        
        # If we have fewer streams than the threshold, no cleanup needed
        if len(streams) <= threshold:
            return 0, []
        
        # Keep track of streams to preserve
        preserved_streams = set()
        
        # Preserve streams based on category
        if preserve_favorites or preserve_categories:
            for stream in streams:
                # Check if we should preserve this stream due to category
                if preserve_favorites and hasattr(stream, 'category_id') and stream.category_id in favorite_category_ids:
                    preserved_streams.add(stream.id)
                    
                # Check if we should preserve based on specified categories
                if preserve_categories and stream.category_name in preserve_categories:
                    preserved_streams.add(stream.id)
        
        # Preserve streams based on timeframe if specified
        if preserve_timeframe:
            preserved_streams.update(
                CleanupService._get_streams_in_timeframe(streams, preserve_timeframe)
            )
        
        # Identify streams to delete (keeping at least threshold streams)
        kept_count = 0
        streams_to_delete = []
        
        for stream in streams:
            if stream.id in preserved_streams:
                # Always keep preserved streams
                continue
                
            if kept_count < threshold:
                # Keep the newest streams up to threshold
                kept_count += 1
                continue
                
            streams_to_delete.append(stream)
        
        # Delete the identified streams
        return await CleanupService._delete_streams(streams_to_delete, db)
                
    @staticmethod
    async def _apply_size_policy(
        streamer_id: int,
        threshold: int,  # In GB
        preserve_favorites: bool,
        preserve_categories: List[str],
        preserve_timeframe: Dict[str, Any],
        favorite_category_ids: Set[int],
        streams_query,
        db: Session
    ) -> Tuple[int, List[str]]:
        """Apply size-based cleanup policy"""
        # First get all recordings sorted by age (oldest first)
        streams = streams_query.order_by(asc(Stream.started_at)).all()
        
        # Calculate threshold in bytes
        threshold_bytes = threshold * 1024 * 1024 * 1024  # Convert GB to bytes
        
        # Calculate current storage usage
        total_size = 0
        for stream in streams:
            if stream.recording_path and os.path.exists(stream.recording_path):
                try:
                    size = os.path.getsize(stream.recording_path)
                    total_size += size
                except Exception as e:
                    logger.error(f"Error getting file size for {stream.recording_path}: {e}")
        
        # If we're under the threshold, no cleanup needed
        if total_size <= threshold_bytes:
            return 0, []
        
        # Keep track of streams to preserve
        preserved_streams = set()
        
        # Preserve streams based on category
        if preserve_favorites or preserve_categories:
            for stream in streams:
                # Check if we should preserve this stream due to category
                if preserve_favorites and hasattr(stream, 'category_id') and stream.category_id in favorite_category_ids:
                    preserved_streams.add(stream.id)
                    
                # Check if we should preserve based on specified categories
                if preserve_categories and hasattr(stream, 'category_name') and stream.category_name in preserve_categories:
                    preserved_streams.add(stream.id)
        
        # Preserve streams based on timeframe if specified
        if preserve_timeframe:
            preserved_streams.update(
                CleanupService._get_streams_in_timeframe(streams, preserve_timeframe)
            )
        
        # Identify streams to delete (to get under the threshold)
        streams_to_delete = []
        current_size = total_size
        
        # Start with the oldest streams
        for stream in streams:
            # Skip preserved streams
            if stream.id in preserved_streams:
                continue
                
            # Check if we're now under the threshold
            if current_size <= threshold_bytes:
                break
                
            # Add this stream to deletion list and update size
            if stream.recording_path and os.path.exists(stream.recording_path):
                try:
                    file_size = os.path.getsize(stream.recording_path)
                    streams_to_delete.append(stream)
                    current_size -= file_size
                except Exception as e:
                    logger.error(f"Error getting file size for {stream.recording_path}: {e}")
        
        # Delete the identified streams
        return await CleanupService._delete_streams(streams_to_delete, db)
    
    @staticmethod
    async def _apply_age_policy(
        streamer_id: int,
        threshold: int,  # In days
        preserve_favorites: bool,
        preserve_categories: List[str],
        preserve_timeframe: Dict[str, Any],
        favorite_category_ids: Set[int],
        streams_query,
        db: Session
    ) -> Tuple[int, List[str]]:
        """Apply age-based cleanup policy"""
        # Calculate the cutoff date
        cutoff_date = datetime.now() - timedelta(days=threshold)
        
        # Get streams older than the cutoff
        old_streams = streams_query.filter(Stream.started_at < cutoff_date).all()
        
        # If no old streams, no cleanup needed
        if not old_streams:
            return 0, []
        
        # Keep track of streams to preserve
        preserved_streams = set()
        
        # Preserve streams based on category
        if preserve_favorites or preserve_categories:
            for stream in old_streams:
                # Check if we should preserve this stream due to category
                if preserve_favorites and hasattr(stream, 'category_id') and stream.category_id in favorite_category_ids:
                    preserved_streams.add(stream.id)
                    
                # Check if we should preserve based on specified categories
                if preserve_categories and hasattr(stream, 'category_name') and stream.category_name in preserve_categories:
                    preserved_streams.add(stream.id)
        
        # Preserve streams based on timeframe if specified
        if preserve_timeframe:
            preserved_streams.update(
                CleanupService._get_streams_in_timeframe(old_streams, preserve_timeframe)
            )
        
        # Identify streams to delete
        streams_to_delete = [s for s in old_streams if s.id not in preserved_streams]
        
        # Delete the identified streams
        return await CleanupService._delete_streams(streams_to_delete, db)
    
    @staticmethod
    def _get_streams_in_timeframe(
        streams: List[Stream], 
        timeframe: Dict[str, Any]
    ) -> Set[int]:
        """
        Get IDs of streams that fall within the specified timeframe
        """
        preserved_ids = set()
        
        start_date = timeframe.get("start_date")
        end_date = timeframe.get("end_date")
        weekdays = timeframe.get("weekdays", [])
        time_of_day = timeframe.get("timeOfDay")
        
        for stream in streams:
            stream_time = stream.started_at
            if not stream_time:
                continue
                
            # Check date range
            if start_date and stream_time < datetime.fromisoformat(start_date):
                continue
                
            if end_date and stream_time > datetime.fromisoformat(end_date):
                continue
                
            # Check weekday
            if weekdays and stream_time.weekday() not in weekdays:
                continue
                
            # Check time of day
            if time_of_day:
                start_time = time_of_day.get("start")
                end_time = time_of_day.get("end")
                
                if start_time and end_time:
                    try:
                        # Parse time strings to hours and minutes
                        start_hour, start_minute = map(int, start_time.split(":"))
                        end_hour, end_minute = map(int, end_time.split(":"))
                        
                        # Create time objects for comparison
                        stream_time_of_day = stream_time.time()
                        from datetime import time
                        start_time_obj = time(start_hour, start_minute)
                        end_time_obj = time(end_hour, end_minute)
                        
                        # Check if stream time is within the range
                        if end_time_obj > start_time_obj:  # Normal case (e.g., 8:00 to 17:00)
                            if not (start_time_obj <= stream_time_of_day <= end_time_obj):
                                continue
                        else:  # Overnight case (e.g., 22:00 to 6:00)
                            if not (stream_time_of_day >= start_time_obj or stream_time_of_day <= end_time_obj):
                                continue
                    except (ValueError, IndexError) as e:
                        logger.error(f"Error parsing time of day: {e}")
            
            # If we get here, the stream is within the timeframe
            preserved_ids.add(stream.id)
            
        return preserved_ids
    
    @staticmethod
    async def _delete_streams(
        streams_to_delete: List[Stream],
        db: Session
    ) -> Tuple[int, List[str]]:
        """Delete the specified streams and return count and paths"""
        deleted_count = 0
        deleted_paths = []
        
        for stream in streams_to_delete:
            try:
                # Get all metadata files from database first
                metadata = db.query(StreamMetadata).filter(StreamMetadata.stream_id == stream.id).first()
                files_to_delete = []
                directories_to_check = set()
                base_name = None  # Initialize base_name for later use
                
                # Get the base directory for this recording
                recording_dir = None
                if stream.recording_path:
                    recording_dir = os.path.dirname(stream.recording_path)
                    if recording_dir and os.path.exists(recording_dir):
                        directories_to_check.add(recording_dir)
                elif metadata and metadata.nfo_path:
                    # If no recording_path but metadata exists, use metadata path to find directory
                    recording_dir = os.path.dirname(metadata.nfo_path)
                    if recording_dir and os.path.exists(recording_dir):
                        directories_to_check.add(recording_dir)
                
                # Add main recording file
                if stream.recording_path and os.path.exists(stream.recording_path):
                    files_to_delete.append(stream.recording_path)
                
                # Add all metadata files from database (only actually generated files)
                if metadata:
                    metadata_files = [
                        metadata.thumbnail_path,
                        metadata.json_path,
                        metadata.nfo_path,
                        metadata.tvshow_nfo_path,
                        metadata.season_nfo_path,
                        metadata.chapters_vtt_path,
                        metadata.chapters_srt_path,
                        metadata.chapters_ffmpeg_path,
                        metadata.chapters_xml_path
                    ]
                    
                    # Add existing metadata files to deletion list
                    for file_path in metadata_files:
                        if file_path and os.path.exists(file_path):
                            files_to_delete.append(file_path)
                
                # Find ALL related files in the recording directory by pattern matching
                if recording_dir and os.path.exists(recording_dir):
                    # Try to get base filename from recording_path or construct it from stream data
                    base_name = None
                    if stream.recording_path:
                        base_name = os.path.splitext(os.path.basename(stream.recording_path))[0]
                    elif metadata and metadata.nfo_path:
                        # Construct from NFO path
                        base_name = os.path.splitext(os.path.basename(metadata.nfo_path))[0]
                    elif stream.started_at:
                        # Last resort: construct from stream data (Streamer - SYYYYMME## pattern)
                        from app.models import Streamer
                        streamer = db.query(Streamer).filter(Streamer.id == stream.streamer_id).first()
                        if streamer and hasattr(stream, 'episode_number'):
                            season_num = stream.started_at.strftime("%Y%m")
                            episode_num = f"{int(stream.episode_number):02d}" if stream.episode_number else stream.started_at.strftime("%d")
                            base_name = f"{streamer.username} - S{season_num}E{episode_num}"
                    
                    if base_name:
                        # Find all files matching this recording
                        for filename in os.listdir(recording_dir):
                            file_path = os.path.join(recording_dir, filename)
                            
                            # Skip directories for now
                            if os.path.isdir(file_path):
                                # Check if it's a segment directory for this recording
                                if filename.startswith(base_name) and filename.endswith('_segments'):
                                    directories_to_check.add(file_path)
                                continue
                            
                            # Check if this file belongs to the recording
                            if filename.startswith(base_name):
                                # Include all variations: .nfo, .tbn, .jpg, -thumb.jpg, _thumbnail.jpg, etc.
                                if file_path not in files_to_delete and os.path.exists(file_path):
                                    files_to_delete.append(file_path)
                                    
                            # Also check for symlinks that point to this recording's files
                            if os.path.islink(file_path):
                                try:
                                    link_target = os.readlink(file_path)
                                    # Check if the symlink points to any of our files
                                    target_base = os.path.splitext(os.path.basename(link_target))[0]
                                    if base_name in target_base or target_base in base_name:
                                        if file_path not in files_to_delete:
                                            files_to_delete.append(file_path)
                                except (OSError, ValueError):
                                    pass
                
                # Delete all collected files
                for file_path in files_to_delete:
                    try:
                        if os.path.exists(file_path) or os.path.islink(file_path):
                            os.remove(file_path)
                            deleted_paths.append(file_path)
                            logger.info(f"Deleted file: {file_path}")
                    except Exception as e:
                        logger.error(f"Failed to delete file {file_path}: {e}")
                
                # Delete segment directories if they exist and are not actively being used
                for dir_path in directories_to_check:
                    if os.path.exists(dir_path) and os.path.isdir(dir_path):
                        # Safety check: Don't delete if this is an active recording
                        if dir_path.endswith('_segments'):
                            # Check if this stream is currently recording
                            if stream.ended_at is None:
                                logger.warning(f"Skipping deletion of segment directory for active recording: {dir_path}")
                                continue
                            
                            # Additional check: see if there's a corresponding stream that's still active
                            active_stream = db.query(Stream).filter(
                                Stream.streamer_id == stream.streamer_id,
                                Stream.ended_at.is_(None),
                                Stream.id != stream.id
                            ).first()
                            
                            if active_stream:
                                # Check if the segment directory name matches the active stream
                                if base_name and base_name in os.path.basename(dir_path):
                                    logger.warning(f"Skipping deletion of segment directory - may belong to active recording: {dir_path}")
                                    continue
                        
                        try:
                            shutil.rmtree(dir_path)
                            logger.info(f"Deleted segment directory: {dir_path}")
                        except Exception as e:
                            logger.error(f"Failed to delete directory {dir_path}: {e}")
                
                # Delete metadata record from database
                if metadata:
                    db.delete(metadata)
                    logger.debug(f"Deleted metadata record for stream {stream.id}")
                
                # Delete the stream record completely from database
                # (Cleanup should remove the entire stream record, not just clear recording_path)
                db.delete(stream)
                
                deleted_count += 1
                file_count = len(files_to_delete)
                dir_count = len(directories_to_check)
                logger.info(f"Deleted stream {stream.id} with {file_count} files and {dir_count} directories")
                
                # Check if the parent directory is now empty, and if so, delete it
                if recording_dir and os.path.exists(recording_dir):
                    try:
                        remaining_files = []
                        for root, dirs, files in os.walk(recording_dir):
                            # Ignore hidden directories like .media
                            dirs[:] = [d for d in dirs if not d.startswith('.')]
                            remaining_files.extend([os.path.join(root, f) for f in files])
                        
                        # Only delete if completely empty (ignoring system files like poster.jpg, season-poster.jpg in parent)
                        if not remaining_files:
                            shutil.rmtree(recording_dir)
                            logger.info(f"Removed empty directory: {recording_dir}")
                    except Exception as e:
                        logger.debug(f"Could not remove directory {recording_dir}: {e}")
                            
            except Exception as e:
                logger.error(f"Error deleting stream {stream.id}: {e}", exc_info=True)
        
        # Commit changes to the database
        db.commit()
        return deleted_count, deleted_paths
    
    @staticmethod
    async def get_storage_usage(streamer_id: int) -> Dict[str, Any]:
        """
        Get storage usage statistics for a streamer
        
        Args:
            streamer_id: ID of the streamer
            
        Returns:
            Dictionary with totalSize, recordingCount, oldestRecording, newestRecording
        """
        with SessionLocal() as db:
            try:
                # Get all recordings for this streamer
                streams = db.query(Stream).filter(
                    Stream.streamer_id == streamer_id,
                    Stream.recording_path.isnot(None)
                ).order_by(Stream.started_at).all()
                
                total_size = 0
                oldest_recording = None
                newest_recording = None
                recording_count = 0
                
                for stream in streams:
                    if stream.recording_path and os.path.exists(stream.recording_path):
                        recording_count += 1
                        
                        # Update oldest/newest
                        if stream.started_at:
                            if oldest_recording is None or stream.started_at < oldest_recording:
                                oldest_recording = stream.started_at
                            if newest_recording is None or stream.started_at > newest_recording:
                                newest_recording = stream.started_at
                        
                        # Calculate file size
                        try:
                            file_size = os.path.getsize(stream.recording_path)
                            total_size += file_size
                        except Exception as e:
                            logger.error(f"Error getting size for {stream.recording_path}: {e}")
                
                return {
                    "totalSize": total_size,
                    "recordingCount": recording_count,
                    "oldestRecording": oldest_recording.isoformat() if oldest_recording else "",
                    "newestRecording": newest_recording.isoformat() if newest_recording else ""
                }
                
            except Exception as e:
                logger.error(f"Error getting storage usage: {e}", exc_info=True)
                return {
                    "totalSize": 0,
                    "recordingCount": 0,
                    "oldestRecording": "",
                    "newestRecording": ""
                }
    
    @staticmethod
    async def run_scheduled_cleanup():
        """Run cleanup for all streamers with configured policies"""
        logger.info("Starting scheduled cleanup for all streamers")
        
        # Get all streamers with recording settings
        try:
            with SessionLocal() as db:
                streamers = db.query(Streamer).all()
                cleanup_count = 0
                total_deleted_count = 0
                processed_count = 0
                
                for streamer in streamers:
                    processed_count += 1
                    # Check if the streamer has a cleanup policy
                    try:
                        policy = CleanupService._get_effective_cleanup_policy(streamer.id, db)
                        if policy:
                            policy_type = policy.get("type", "count")
                            threshold = policy.get("threshold", 0)
                            logger.info(f"Processing streamer {streamer.username} ({processed_count}/{len(streamers)}) "
                                      f"with policy {policy_type} (threshold: {threshold})")
                            
                            # Get current storage stats before cleanup
                            storage_before = await CleanupService.get_storage_usage(streamer.id)
                            
                            # Run the cleanup
                            deleted_count, deleted_paths = await CleanupService.cleanup_old_recordings(streamer.id, db)
                            
                            if deleted_count > 0:
                                # Get storage stats after cleanup
                                storage_after = await CleanupService.get_storage_usage(streamer.id)
                                freed_space = storage_before["totalSize"] - storage_after["totalSize"]
                                freed_space_mb = freed_space / (1024 * 1024)  # Convert to MB
                                
                                logger.info(f"Cleaned up {deleted_count} recordings for streamer {streamer.username}, "
                                          f"freed {freed_space_mb:.2f} MB of space")
                                
                                cleanup_count += 1
                                total_deleted_count += deleted_count
                            else:
                                logger.info(f"No recordings to clean up for streamer {streamer.username}")
                    except Exception as e:
                        logger.error(f"Error during cleanup for streamer {streamer.username}: {e}", exc_info=True)
                
                logger.info(f"Scheduled cleanup completed for {cleanup_count}/{len(streamers)} streamers. "
                          f"Deleted {total_deleted_count} recordings in total.")
        except Exception as e:
            logger.error(f"Error during scheduled cleanup: {e}", exc_info=True)
    
    @staticmethod
    async def simulate_cleanup(
        streamer_id: int, 
        db: Optional[Session] = None,
        custom_policy: Optional[Dict[str, Any]] = None
    ) -> Tuple[int, List[Dict[str, Any]]]:
        """
        Simulate cleanup based on the streamer's cleanup policy without actually deleting files
        
        Args:
            streamer_id: ID of the streamer
            db: Database session
            custom_policy: Override the stored policy with this one
            
        Returns:
            Tuple containing (number of recordings that would be deleted, list of stream details)
        """
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True
            
        try:
            # Get the policy to apply
            policy = custom_policy or CleanupService._get_effective_cleanup_policy(streamer_id, db)
            policy_type = policy.get("type", CleanupPolicyType.COUNT.value)
            threshold = policy.get("threshold", 10)
            preserve_favorites = policy.get("preserve_favorites", True)
            preserve_categories = policy.get("preserve_categories", [])
            preserve_timeframe = policy.get("preserve_timeframe", {})
            
            # Get favorite categories if needed
            favorite_category_ids = set()
            if preserve_favorites:
                favorite_category_ids = CleanupService._get_favorite_categories(db)
            
            # Get all recordings for this streamer
            streams_query = db.query(Stream).filter(
                Stream.streamer_id == streamer_id,
                Stream.recording_path.isnot(None)
            )
            
            # Apply the same logic as cleanup but don't delete, just identify what would be deleted
            streams = []
            
            if policy_type == CleanupPolicyType.COUNT.value:
                # Get streams sorted by time (newest first)
                all_streams = streams_query.order_by(desc(Stream.started_at)).all()
                
                # Identify preserved streams
                preserved_streams = set()
                
                # Preserve streams based on category
                if preserve_favorites or preserve_categories:
                    for stream in all_streams:
                        # Check if we should preserve this stream due to category
                        if preserve_favorites and hasattr(stream, 'category_id') and stream.category_id in favorite_category_ids:
                            preserved_streams.add(stream.id)
                            
                        # Check if we should preserve based on specified categories
                        if preserve_categories and stream.category_name in preserve_categories:
                            preserved_streams.add(stream.id)
                
                # Preserve streams based on timeframe if specified
                if preserve_timeframe:
                    preserved_streams.update(
                        CleanupService._get_streams_in_timeframe(all_streams, preserve_timeframe)
                    )
                
                # Identify streams to delete (keeping at least threshold streams)
                kept_count = 0
                for stream in all_streams:
                    if stream.id in preserved_streams:
                        # Always keep preserved streams
                        continue
                        
                    if kept_count < threshold:
                        # Keep the newest streams up to threshold
                        kept_count += 1
                        continue
                        
                    streams.append(stream)
                    
            elif policy_type == CleanupPolicyType.SIZE.value:
                # Logic for size policy
                all_streams = streams_query.order_by(asc(Stream.started_at)).all()
                
                # Calculate threshold in bytes
                threshold_bytes = threshold * 1024 * 1024 * 1024  # Convert GB to bytes
                
                # Calculate current storage usage
                total_size = 0
                for stream in all_streams:
                    if stream.recording_path and os.path.exists(stream.recording_path):
                        try:
                            size = os.path.getsize(stream.recording_path)
                            total_size += size
                        except Exception:
                            pass
                
                # Identify preserved streams
                preserved_streams = set()
                
                # Preserve streams based on category and timeframe
                if preserve_favorites or preserve_categories:
                    for stream in all_streams:
                        if preserve_favorites and hasattr(stream, 'category_id') and stream.category_id in favorite_category_ids:
                            preserved_streams.add(stream.id)
                            
                        if preserve_categories and stream.category_name in preserve_categories:
                            preserved_streams.add(stream.id)
                
                if preserve_timeframe:
                    preserved_streams.update(
                        CleanupService._get_streams_in_timeframe(all_streams, preserve_timeframe)
                    )
                
                # Identify streams to delete (to get under the threshold)
                current_size = total_size
                
                for stream in all_streams:
                    # Skip preserved streams
                    if stream.id in preserved_streams:
                        continue
                        
                    # Check if we're now under the threshold
                    if current_size <= threshold_bytes:
                        break
                        
                    # Add this stream to deletion list and update size
                    if stream.recording_path and os.path.exists(stream.recording_path):
                        try:
                            file_size = os.path.getsize(stream.recording_path)
                            streams.append(stream)
                            current_size -= file_size
                        except Exception:
                            pass
                
            elif policy_type == CleanupPolicyType.AGE.value:
                # Logic for age policy
                cutoff_date = datetime.now() - timedelta(days=threshold)
                
                # Get streams older than the cutoff
                old_streams = streams_query.filter(Stream.started_at < cutoff_date).all()
                
                # Identify preserved streams
                preserved_streams = set()
                
                # Preserve streams based on category
                if preserve_favorites or preserve_categories:
                    for stream in old_streams:
                        if preserve_favorites and hasattr(stream, 'category_id') and stream.category_id in favorite_category_ids:
                            preserved_streams.add(stream.id)
                            
                        if preserve_categories and stream.category_name in preserve_categories:
                            preserved_streams.add(stream.id)
                
                # Preserve streams based on timeframe if specified
                if preserve_timeframe:
                    preserved_streams.update(
                        CleanupService._get_streams_in_timeframe(old_streams, preserve_timeframe)
                    )
                
                # Identify streams to delete
                streams = [s for s in old_streams if s.id not in preserved_streams]
            
            # Format the result for display
            result_streams = []
            total_size = 0
            
            for stream in streams:
                size = 0
                if stream.recording_path and os.path.exists(stream.recording_path):
                    try:
                        size = os.path.getsize(stream.recording_path)
                        total_size += size
                    except Exception:
                        pass
                
                result_streams.append({
                    "id": stream.id,
                    "title": stream.title,
                    "category": getattr(stream, 'category_name', 'Unknown'),
                    "started_at": stream.started_at.isoformat() if stream.started_at else None,
                    "path": stream.recording_path,
                    "size": size,
                    "size_formatted": CleanupService._format_size(size)
                })
            
            return (
                len(result_streams), 
                {
                    "streams": result_streams,
                    "total_size": total_size,
                    "total_size_formatted": CleanupService._format_size(total_size),
                    "policy": {
                        "type": policy_type,
                        "threshold": threshold,
                        "preserve_favorites": preserve_favorites,
                        "preserve_categories": preserve_categories
                    }
                }
            )
                
        except Exception as e:
            logger.error(f"Error simulating cleanup: {e}", exc_info=True)
            return 0, {"streams": [], "total_size": 0, "total_size_formatted": "0 B", "policy": {}}
        finally:
            if close_db:
                db.close()

    @staticmethod
    def _format_size(size_bytes):
        """Format a size in bytes to a human-readable string"""
        if size_bytes == 0:
            return "0 B"
        
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        size = float(size_bytes)
        unit_index = 0
        
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1
            
        return f"{size:.2f} {units[unit_index]}"
    
    @staticmethod
    async def cleanup_orphaned_files(recordings_root: str = "/recordings") -> Tuple[int, List[str]]:
        """
        Clean up orphaned files in the recordings directory:
        - Broken symlinks (pointing to non-existent files)
        - 0-byte NFO files (corrupt or incomplete)
        - Empty segment directories
        
        Args:
            recordings_root: Root directory for recordings
            
        Returns:
            Tuple containing (number of cleaned files, list of cleaned file paths)
        """
        cleaned_count = 0
        cleaned_paths = []
        
        try:
            if not os.path.exists(recordings_root):
                logger.warning(f"Recordings root does not exist: {recordings_root}")
                return 0, []
            
            logger.info(f"🧹 Starting orphaned files cleanup in {recordings_root}")
            
            # Walk through all directories
            for root, dirs, files in os.walk(recordings_root):
                # Skip hidden directories
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                
                # Check for broken symlinks and 0-byte files
                for filename in files:
                    file_path = os.path.join(root, filename)
                    
                    try:
                        # Check for broken symlinks
                        if os.path.islink(file_path):
                            if not os.path.exists(file_path):
                                os.unlink(file_path)
                                cleaned_paths.append(file_path)
                                cleaned_count += 1
                                logger.info(f"🧹 Removed broken symlink: {file_path}")
                                continue
                        
                        # Check for 0-byte NFO files (excluding tvshow.nfo and season.nfo which can be small)
                        if filename.endswith('.nfo') and filename not in ['tvshow.nfo', 'season.nfo']:
                            if os.path.exists(file_path) and os.path.getsize(file_path) == 0:
                                os.remove(file_path)
                                cleaned_paths.append(file_path)
                                cleaned_count += 1
                                logger.info(f"🧹 Removed 0-byte NFO file: {file_path}")
                                
                    except Exception as e:
                        logger.debug(f"Error processing file {file_path}: {e}")
                
                # Check for empty segment directories
                for dirname in dirs[:]:  # Use slice copy to allow modification during iteration
                    if dirname.endswith('_segments'):
                        dir_path = os.path.join(root, dirname)
                        try:
                            if os.path.isdir(dir_path):
                                # Check if directory is empty
                                if not os.listdir(dir_path):
                                    os.rmdir(dir_path)
                                    cleaned_count += 1
                                    logger.info(f"🧹 Removed empty segment directory: {dir_path}")
                                    dirs.remove(dirname)  # Don't walk into it
                        except Exception as e:
                            logger.debug(f"Error processing directory {dir_path}: {e}")
            
            logger.info(f"🧹 Orphaned files cleanup completed: {cleaned_count} items cleaned")
            return cleaned_count, cleaned_paths
            
        except Exception as e:
            logger.error(f"Error during orphaned files cleanup: {e}", exc_info=True)
            return cleaned_count, cleaned_paths


# Global cleanup service instance
cleanup_service = CleanupService()
