"""
RecordingDatabaseService - Database operations and session management

Extracted from recording_service.py ULTRA-BOSS (1084 lines)
Handles all database operations, session management, and data persistence for recordings.
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.models import Recording, Stream, Streamer
from app.database import get_db, SessionLocal
from app.utils.retry_decorator import database_retry, RetryableError, NonRetryableError

logger = logging.getLogger("streamvault")


class RecordingDatabaseService:
    """Handles all database operations for recordings"""
    
    def __init__(self, db=None):
        self.db = db

    def _ensure_db_session(self):
        """Ensure we have a valid database session"""
        if not self.db:
            self.db = next(get_db())

    @database_retry
    async def update_recording_status(
        self, recording_id: int, status: str, path: str = None, duration_seconds: int = None
    ) -> None:
        """Update recording status in database
        
        Args:
            recording_id: Recording ID
            status: New status
            path: File path (optional)
            duration_seconds: Duration in seconds (optional)
        """
        try:
            self._ensure_db_session()
            recording = self.db.query(Recording).filter(Recording.id == recording_id).first()
            
            if not recording:
                logger.error(f"Recording {recording_id} not found for status update")
                raise NonRetryableError(f"Recording {recording_id} not found")
            
            old_status = recording.status
            recording.status = status
            
            if path:
                recording.file_path = path
            
            if duration_seconds is not None:
                recording.duration_seconds = duration_seconds
            
            if status == "completed":
                recording.end_time = datetime.utcnow()
            elif status == "failed":
                recording.end_time = datetime.utcnow()
                
            self.db.commit()
            logger.info(f"Recording {recording_id} status updated: {old_status} → {status}")
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to update recording {recording_id} status: {e}")
            if "not found" in str(e).lower():
                raise NonRetryableError(f"Recording not found: {e}")
            raise RetryableError(f"Database error: {e}")

    @database_retry
    async def create_recording(self, stream_id: int, file_path: str) -> Recording:
        """Create a new recording entry"""
        try:
            self._ensure_db_session()
            
            recording = Recording(
                stream_id=stream_id,
                path=file_path,
                status="recording",
                start_time=datetime.utcnow()
            )
            
            self.db.add(recording)
            self.db.commit()
            self.db.refresh(recording)
            
            logger.info(f"Created recording {recording.id} for stream {stream_id}")
            return recording
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create recording: {e}")
            raise RetryableError(f"Database error: {e}")

    @database_retry
    async def get_recording(self, recording_id: int) -> Optional[Recording]:
        """Get recording by ID"""
        try:
            self._ensure_db_session()
            return self.db.query(Recording).filter(Recording.id == recording_id).first()
        except Exception as e:
            logger.error(f"Failed to get recording {recording_id}: {e}")
            raise RetryableError(f"Database error: {e}")
    
    # Alias for compatibility
    async def get_recording_by_id(self, recording_id: int) -> Optional[Recording]:
        """Alias for get_recording - for compatibility"""
        return await self.get_recording(recording_id)

    @database_retry
    async def get_active_recordings_from_db(self) -> List[Recording]:
        """Get all active recordings from database"""
        try:
            self._ensure_db_session()
            return self.db.query(Recording).filter(
                Recording.status.in_(["recording", "processing"])
            ).all()
        except Exception as e:
            logger.error(f"Failed to get active recordings: {e}")
            raise RetryableError(f"Database error: {e}")

    @database_retry
    async def ensure_stream_ended(self, stream_id: int) -> None:
        """Ensure stream is marked as ended in database"""
        try:
            self._ensure_db_session()
            stream = self.db.query(Stream).filter(Stream.id == stream_id).first()
            
            if stream and not stream.ended_at:
                stream.ended_at = datetime.utcnow()
                self.db.commit()
                logger.info(f"Marked stream {stream_id} as ended")
                
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to end stream {stream_id}: {e}")
            raise RetryableError(f"Database error: {e}")

    @database_retry
    async def get_stream_with_streamer(self, stream_id: int) -> Optional[tuple]:
        """Get stream and associated streamer data"""
        try:
            self._ensure_db_session()
            result = self.db.query(Stream, Streamer).join(
                Streamer, Stream.streamer_id == Streamer.id
            ).filter(Stream.id == stream_id).first()
            
            return result if result else None
            
        except Exception as e:
            logger.error(f"Failed to get stream {stream_id} with streamer: {e}")
            raise RetryableError(f"Database error: {e}")

    @database_retry
    async def get_recordings_by_status(self, status: str) -> List[Recording]:
        """Get recordings by status"""
        try:
            self._ensure_db_session()
            return self.db.query(Recording).filter(Recording.status == status).all()
        except Exception as e:
            logger.error(f"Failed to get recordings by status {status}: {e}")
            raise RetryableError(f"Database error: {e}")

    @database_retry
    async def update_recording_path(self, recording_id: int, new_path: str) -> None:
        """Update recording file path"""
        try:
            self._ensure_db_session()
            recording = self.db.query(Recording).filter(Recording.id == recording_id).first()
            
            if recording:
                old_path = recording.file_path
                recording.file_path = new_path
                self.db.commit()
                logger.info(f"Updated recording {recording_id} path: {old_path} → {new_path}")
            else:
                raise NonRetryableError(f"Recording {recording_id} not found")
                
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to update recording {recording_id} path: {e}")
            if "not found" in str(e).lower():
                raise NonRetryableError(f"Recording not found: {e}")
            raise RetryableError(f"Database error: {e}")

    @database_retry
    async def mark_recording_failed(self, recording_id: int, error_message: str = None) -> None:
        """Mark recording as failed with optional error message"""
        try:
            self._ensure_db_session()
            recording = self.db.query(Recording).filter(Recording.id == recording_id).first()
            
            if recording:
                recording.status = "failed"
                recording.end_time = datetime.utcnow()
                if error_message:
                    # Store error message if recording model has such field
                    if hasattr(recording, 'error_message'):
                        recording.error_message = error_message
                
                self.db.commit()
                logger.info(f"Marked recording {recording_id} as failed")
            else:
                raise NonRetryableError(f"Recording {recording_id} not found")
                
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to mark recording {recording_id} as failed: {e}")
            if "not found" in str(e).lower():
                raise NonRetryableError(f"Recording not found: {e}")
            raise RetryableError(f"Database error: {e}")

    @database_retry
    async def get_streamer_by_id(self, streamer_id: int) -> Optional[Streamer]:
        """Get streamer by ID"""
        try:
            self._ensure_db_session()
            return self.db.query(Streamer).filter(Streamer.id == streamer_id).first()
        except Exception as e:
            logger.error(f"Failed to get streamer {streamer_id}: {e}")
            raise RetryableError(f"Database error: {e}")

    @database_retry
    async def get_stream_by_id(self, stream_id: int) -> Optional[Stream]:
        """Get stream by ID"""
        try:
            self._ensure_db_session()
            return self.db.query(Stream).filter(Stream.id == stream_id).first()
        except Exception as e:
            logger.error(f"Failed to get stream {stream_id}: {e}")
            raise RetryableError(f"Database error: {e}")

    @database_retry
    async def get_stream_by_external_id(self, external_id: str) -> Optional[Stream]:
        """Get stream by external ID"""
        try:
            self._ensure_db_session()
            return self.db.query(Stream).filter(Stream.external_id == external_id).first()
        except Exception as e:
            logger.error(f"Failed to get stream by external ID {external_id}: {e}")
            raise RetryableError(f"Database error: {e}")

    @database_retry
    async def create_stream(self, stream_data: Dict[str, Any]) -> Optional[Stream]:
        """Create a new stream record"""
        try:
            self._ensure_db_session()
            
            # Create new stream
            stream = Stream(
                streamer_id=stream_data['streamer_id'],
                title=stream_data.get('title', 'Unknown Stream'),
                category_name=stream_data.get('category_name', 'Unknown'),
                language=stream_data.get('language', 'en'),
                started_at=stream_data.get('started_at', datetime.now()),
                is_live=stream_data.get('is_live', True),
                external_id=stream_data.get('external_id', 'unknown')
            )
            
            self.db.add(stream)
            self.db.commit()
            self.db.refresh(stream)
            
            logger.info(f"Created new stream {stream.id} for streamer {stream.streamer_id}")
            return stream
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create stream: {e}")
            raise RetryableError(f"Database error: {e}")

    def close_session(self):
        """Close database session if it exists"""
        if self.db:
            try:
                self.db.close()
                logger.debug("Database session closed")
            except Exception as e:
                logger.warning(f"Error closing database session: {e}")
            finally:
                self.db = None

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close_session()
