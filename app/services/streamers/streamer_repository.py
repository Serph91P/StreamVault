"""
StreamerRepository - Database operations for streamers, streams, and settings

Extracted from streamer_service.py God Class
Handles all database CRUD operations for streamers and related entities.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models import Streamer, Stream, NotificationSettings, Recording, StreamerRecordingSettings
from app.schemas.streamers import StreamerResponse

logger = logging.getLogger("streamvault")


class StreamerRepository:
    """Handles database operations for streamers and related entities"""

    def __init__(self, db: Session):
        self.db = db

    def get_all_streamers(self) -> List[StreamerResponse]:
        """Get all streamers with their current status (excludes test data)"""
        try:
            # CRITICAL: Filter out test data to prevent appearing in frontend
            streamers = self.db.query(Streamer).filter(
                (Streamer.is_test_data.is_(False)) | (Streamer.is_test_data.is_(None))
            ).all()
            result = []

            for streamer in streamers:
                # Check if recording is active by looking for active recordings
                is_recording = False
                active_stream_id = None

                # Find the most recent stream that hasn't ended
                active_stream = self.db.query(Stream).filter(
                    Stream.streamer_id == streamer.id,
                    Stream.ended_at.is_(None)
                ).order_by(Stream.started_at.desc()).first()

                # Check if this stream has an active recording
                if active_stream:
                    # Check if there's an active recording for this stream
                    active_recording = self.db.query(Recording).filter(
                        Recording.stream_id == active_stream.id,
                        Recording.end_time.is_(None)
                    ).first()

                    if active_recording:
                        is_recording = True
                        active_stream_id = active_stream.id

                # Check if recording is enabled from StreamerRecordingSettings
                recording_enabled = True  # Default
                try:
                    settings = self.db.query(StreamerRecordingSettings).filter(
                        StreamerRecordingSettings.streamer_id == streamer.id
                    ).first()
                    if settings:
                        recording_enabled = settings.enabled
                except Exception as e:
                    logger.warning(f"Could not check recording settings for streamer {streamer.id}: {e}")

                # Create StreamerResponse object
                streamer_response = StreamerResponse(
                    id=streamer.id,
                    username=streamer.username,
                    twitch_id=streamer.twitch_id,
                    profile_image_url=streamer.profile_image_url,
                    is_live=streamer.is_live,
                    is_recording=is_recording,
                    recording_enabled=recording_enabled,
                    active_stream_id=active_stream_id,
                    title=streamer.title,
                    category_name=streamer.category_name,
                    language=streamer.language,
                    last_updated=streamer.last_updated,
                    original_profile_image_url=streamer.original_profile_image_url
                )
                result.append(streamer_response)

            return result

        except Exception as e:
            logger.error(f"Error getting streamers: {e}", exc_info=True)
            # Return empty list on error to prevent frontend issues
            return []

    def get_all_streamers_raw(self) -> List[Streamer]:
        """Get all streamers as raw Streamer objects (excludes test data)"""
        return self.db.query(Streamer).filter(
            (Streamer.is_test_data.is_(False)) | (Streamer.is_test_data.is_(None))
        ).order_by(Streamer.username).all()

    def get_streamer_by_username(self, username: str) -> Optional[Streamer]:
        """Get streamer by username (case insensitive)"""
        return self.db.query(Streamer).filter(Streamer.username.ilike(username)).first()

    def get_streamer_by_id(self, streamer_id: int) -> Optional[Streamer]:
        """Get streamer by ID"""
        return self.db.query(Streamer).filter(Streamer.id == streamer_id).first()

    def get_streamer_by_twitch_id(self, twitch_id: str) -> Optional[Streamer]:
        """Get streamer by Twitch ID"""
        return self.db.query(Streamer).filter(Streamer.twitch_id == twitch_id).first()

    def create_streamer(self, user_data: Dict[str, Any], display_name: str = None,
                        cached_image_path: str = None, cached_banner_path: str = None,
                        stream_info: Dict[str, Any] = None) -> Streamer:
        """Create a new streamer with all related settings"""
        try:
            # Use display_name for better user experience, but store original for API calls
            streamer_name = display_name or user_data.get('display_name') or user_data['login']

            # Determine live status and stream info
            # stream_info will be None if the stream is offline, or contain actual data if live
            is_live = stream_info is not None
            current_title = stream_info.get('title', '') if stream_info else None
            current_category = stream_info.get('game_name', '') if stream_info else None
            current_language = stream_info.get('language', '') if stream_info else None

            # Debug logging to identify the issue
            logger.debug(f"Creating streamer {streamer_name}: stream_info={stream_info}, is_live={is_live}")

            # Create new streamer
            new_streamer = Streamer(
                twitch_id=user_data['id'],
                username=streamer_name,
                profile_image_url=cached_image_path or user_data['profile_image_url'],
                original_profile_image_url=user_data['profile_image_url'],
                offline_image_url=cached_banner_path or user_data.get('offline_image_url'),  # NEW: Banner support
                original_offline_image_url=user_data.get('offline_image_url'),  # NEW: Original Twitch banner URL
                is_live=is_live,
                title=current_title,
                category_name=current_category,
                language=current_language,
                last_updated=datetime.now(timezone.utc)
            )

            self.db.add(new_streamer)
            self.db.flush()

            # If the streamer is live, create a stream entry
            if is_live and stream_info:
                try:
                    # Check if stream already exists
                    existing_stream = self.db.query(Stream).filter(
                        Stream.twitch_stream_id == stream_info.get('id')
                    ).first()

                    if not existing_stream:
                        # Create new stream entry
                        new_stream = Stream(
                            streamer_id=new_streamer.id,
                            twitch_stream_id=stream_info.get('id'),
                            title=current_title,
                            category_name=current_category,
                            language=current_language,
                            started_at=datetime.now(timezone.utc),  # We don't know exact start time, use current time
                            ended_at=None
                        )
                        self.db.add(new_stream)
                        new_streamer.active_stream_id = new_stream.id
                        logger.info(f"Created stream entry for live streamer {streamer_name}")
                    else:
                        # Update existing stream
                        existing_stream.title = current_title
                        existing_stream.category_name = current_category
                        existing_stream.language = current_language
                        new_streamer.active_stream_id = existing_stream.id
                        logger.info(f"Updated existing stream entry for {streamer_name}")

                except Exception as e:
                    logger.warning(f"Could not create/update stream entry for {streamer_name}: {e}")

            # Create default notification settings
            notification_settings = NotificationSettings(
                streamer_id=new_streamer.id,
                notify_online=True,
                notify_offline=True,
                notify_update=True
            )
            self.db.add(notification_settings)

            # Create default recording settings
            try:
                recording_settings = StreamerRecordingSettings(
                    streamer_id=new_streamer.id,
                    enabled=True  # Enable recording by default for new streamers
                )
                self.db.add(recording_settings)
            except Exception as e:
                logger.warning(f"Could not create default recording settings: {e}")

            self.db.commit()
            self.db.refresh(new_streamer)

            return new_streamer

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating streamer: {e}", exc_info=True)
            raise

    def update_streamer(self, streamer: Streamer, **kwargs) -> Streamer:
        """Update streamer with provided fields"""
        try:
            for key, value in kwargs.items():
                if hasattr(streamer, key):
                    setattr(streamer, key, value)

            streamer.last_updated = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(streamer)

            return streamer
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating streamer {streamer.id}: {e}", exc_info=True)
            raise

    def delete_streamer(self, streamer_id: int) -> Optional[Dict[str, Any]]:
        """Delete streamer and all related data"""
        try:
            streamer = self.db.query(Streamer).filter(Streamer.id == streamer_id).first()
            if not streamer:
                return None

            streamer_data = {
                "twitch_id": streamer.twitch_id,
                "username": streamer.username
            }

            # Delete notification settings first
            self.db.query(NotificationSettings).filter(
                NotificationSettings.streamer_id == streamer_id
            ).delete()

            # Delete recording settings
            try:
                self.db.query(StreamerRecordingSettings).filter(
                    StreamerRecordingSettings.streamer_id == streamer_id
                ).delete()
            except Exception as e:
                logger.warning(f"Could not delete recording settings: {e}")

            # Delete streams (CASCADE should handle related records like stream_events, recordings, etc.)
            # But we do it manually to avoid relying on database-level CASCADE that might not be set up
            from app.models import Stream
            self.db.query(Stream).filter(Stream.streamer_id == streamer_id).delete()

            # Delete the streamer
            self.db.delete(streamer)
            self.db.commit()

            logger.info(f"Deleted streamer: {streamer_data['username']}")
            return streamer_data

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error deleting streamer: {e}", exc_info=True)
            raise

    def get_notification_settings(self, streamer_id: int) -> Optional[NotificationSettings]:
        """Get notification settings for a streamer"""
        return self.db.query(NotificationSettings).filter(
            NotificationSettings.streamer_id == streamer_id
        ).first()

    def get_recording_settings(self, streamer_id: int) -> Optional[StreamerRecordingSettings]:
        """Get recording settings for a streamer"""
        try:
            return self.db.query(StreamerRecordingSettings).filter(
                StreamerRecordingSettings.streamer_id == streamer_id
            ).first()
        except Exception as e:
            logger.warning(f"Could not get recording settings for streamer {streamer_id}: {e}")
            return None

    def update_notification_settings(self, streamer_id: int, **settings) -> NotificationSettings:
        """Update notification settings for a streamer"""
        try:
            notification_settings = self.get_notification_settings(streamer_id)
            if not notification_settings:
                # Create new settings if they don't exist
                notification_settings = NotificationSettings(streamer_id=streamer_id)
                self.db.add(notification_settings)

            for key, value in settings.items():
                if hasattr(notification_settings, key):
                    setattr(notification_settings, key, value)

            self.db.commit()
            self.db.refresh(notification_settings)

            return notification_settings
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating notification settings for streamer {streamer_id}: {e}")
            raise

    def update_recording_settings(self, streamer_id: int, **settings) -> StreamerRecordingSettings:
        """Update recording settings for a streamer"""
        try:
            recording_settings = self.get_recording_settings(streamer_id)
            if not recording_settings:
                # Create new settings if they don't exist
                recording_settings = StreamerRecordingSettings(streamer_id=streamer_id)
                self.db.add(recording_settings)

            for key, value in settings.items():
                if hasattr(recording_settings, key):
                    setattr(recording_settings, key, value)

            self.db.commit()
            self.db.refresh(recording_settings)

            return recording_settings
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating recording settings for streamer {streamer_id}: {e}")
            raise

    def get_active_streams(self) -> List[Stream]:
        """Get all currently active streams"""
        return self.db.query(Stream).filter(Stream.ended_at.is_(None)).all()

    def get_stream_by_twitch_id(self, twitch_stream_id: str) -> Optional[Stream]:
        """Get stream by Twitch stream ID"""
        return self.db.query(Stream).filter(Stream.twitch_stream_id == twitch_stream_id).first()

    def create_stream(self, streamer_id: int, twitch_stream_id: str, stream_data: Dict[str, Any]) -> Stream:
        """Create a new stream entry"""
        try:
            new_stream = Stream(
                streamer_id=streamer_id,
                twitch_stream_id=twitch_stream_id,
                title=stream_data.get('title', ''),
                category_name=stream_data.get('game_name', ''),
                language=stream_data.get('language', ''),
                started_at=datetime.now(timezone.utc),
                ended_at=None
            )

            self.db.add(new_stream)
            self.db.commit()
            self.db.refresh(new_stream)

            return new_stream
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating stream: {e}")
            raise

    def end_stream(self, stream_id: int) -> Optional[Stream]:
        """Mark a stream as ended"""
        try:
            stream = self.db.query(Stream).filter(Stream.id == stream_id).first()
            if stream:
                stream.ended_at = datetime.now(timezone.utc)
                self.db.commit()
                self.db.refresh(stream)
                return stream
            return None
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error ending stream {stream_id}: {e}")
            raise
