import os
import logging
import shutil
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models import Stream, Streamer, RecordingSettings, StreamerRecordingSettings
from app.database import SessionLocal
from app.services.recording_service import ConfigManager

logger = logging.getLogger("streamvault")

class CleanupService:
    """Service for cleaning up old recordings"""
    
    @staticmethod
    async def cleanup_old_recordings(streamer_id: int, db: Optional[Session] = None) -> Tuple[int, List[str]]:
        """
        Delete oldest recordings for a streamer if the maximum number of recordings is exceeded
        
        Args:
            streamer_id: ID of the streamer
            db: Database session
            
        Returns:
            Tuple containing (number of deleted recordings, list of deleted file paths)
        """
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True
            
        try:
            # Use the config manager to get the max streams setting
            config_manager = ConfigManager()
            max_streams = config_manager.get_max_streams(streamer_id)
            
            if max_streams <= 0:
                return 0, []  # No limit set
                
            # Get streamer's streams ordered by start time (newest first)
            streams = db.query(Stream).filter(
                Stream.streamer_id == streamer_id,
                Stream.recording_path.isnot(None)  # Only completed recordings
            ).order_by(desc(Stream.started_at)).all()
            
            # If we have fewer streams than the limit, no cleanup needed
            if len(streams) <= max_streams:
                return 0, []
                
            # Get the oldest streams to delete
            streams_to_delete = streams[max_streams:]
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
                        logger.info(f"Deleted old recording: {stream.recording_path}")
                        
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
            
        except Exception as e:
            logger.error(f"Error cleaning up old recordings: {e}", exc_info=True)
            return 0, []
        finally:
            if close_db:
                db.close()
