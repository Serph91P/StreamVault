import os
import json
import logging
import shutil
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any, Set
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, func

from app.models import Stream, Streamer, RecordingSettings, StreamerRecordingSettings, FavoriteCategory
from app.database import SessionLocal
from app.services.recording_service import ConfigManager
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
        
        if streamer_settings and streamer_settings.cleanup_policy:
            policy = CleanupService._parse_cleanup_policy(streamer_settings.cleanup_policy)
            if policy:
                return policy
        
        # Fall back to global settings
        global_settings = db.query(RecordingSettings).first()
        if global_settings and global_settings.cleanup_policy:
            policy = CleanupService._parse_cleanup_policy(global_settings.cleanup_policy)
            if policy:
                return policy
                
        # If no policy is set, fall back to the max_streams setting
        config_manager = ConfigManager()
        max_streams = config_manager.get_max_streams(streamer_id)
        
        # Return default policy
        return {
            "type": CleanupPolicyType.COUNT.value,
            "threshold": max_streams if max_streams > 0 else 10,
            "preserve_favorites": True,
            "delete_silently": False
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
            
            # Get all recordings for this streamer
            streams_query = db.query(Stream).filter(
                Stream.streamer_id == streamer_id,
                Stream.recording_path.isnot(None)
            )
            
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
                logger.warning(f"Unsupported cleanup policy type: {policy_type}")
                return 0, []
                
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
                if preserve_categories and stream.category_name in preserve_categories:
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
                if preserve_categories and stream.category_name in preserve_categories:
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
                    start_hour, start_minute = map(int, start_time.split(":"))
                    end_hour, end_minute = map(int, end_time.split(":"))
                    
                    stream_hour, stream_minute = stream_time.hour, stream_time.minute
                    
                    # Convert to minutes for easy comparison
                    start_minutes = start_hour * 60 + start_minute
                    end_minutes = end_hour * 60 + end_minute
                    stream_minutes = stream_hour * 60 + stream_minute
                    
                    if not (start_minutes <= stream_minutes <= end_minutes):
                        continue
            
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
            if stream.recording_path and os.path.exists(stream.recording_path):
                try:
                    # Delete the recording file
                    os.remove(stream.recording_path)
                    deleted_paths.append(stream.recording_path)
                    
                    # Update the stream record to remove the recording path
                    stream.recording_path = None
                    db.add(stream)
                    
                    deleted_count += 1
                    logger.info(f"Deleted recording: {stream.recording_path}")
                    
                    # Check if the directory is now empty, and if so, delete it
                    directory = os.path.dirname(stream.recording_path)
                    if os.path.exists(directory) and not os.listdir(directory):
                        shutil.rmtree(directory)
                        logger.info(f"Removed empty directory: {directory}")
                except Exception as e:
                    logger.error(f"Error deleting recording {stream.recording_path}: {e}")
        
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
                oldest_recording = ""
                newest_recording = ""
                
                if streams:
                    # Get the oldest and newest recordings
                    oldest = streams[0]
                    newest = streams[-1]
                    
                    oldest_recording = oldest.started_at.isoformat() if oldest.started_at else ""
                    newest_recording = newest.started_at.isoformat() if newest.started_at else ""
                    
                    # Calculate total size
                    for stream in streams:
                        if stream.recording_path and os.path.exists(stream.recording_path):
                            try:
                                size = os.path.getsize(stream.recording_path)
                                total_size += size
                            except Exception as e:
                                logger.error(f"Error getting file size for {stream.recording_path}: {e}")
                
                return {
                    "totalSize": total_size,
                    "recordingCount": len(streams),
                    "oldestRecording": oldest_recording,
                    "newestRecording": newest_recording
                }
                
            except Exception as e:
                logger.error(f"Error getting storage usage: {e}", exc_info=True)
                return {
                    "totalSize": 0,
                    "recordingCount": 0,
                    "oldestRecording": "",
                    "newestRecording": ""
                }
