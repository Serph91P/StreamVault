from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, UniqueConstraint, Text, Index, Float
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime
from typing import Optional
import json
import warnings


class Recording(Base):
    __tablename__ = "recordings"
    __table_args__ = (
        # Composite indexes for common query patterns
        Index("idx_recordings_stream_status", "stream_id", "status"),  # For finding recordings by stream and status
        Index("idx_recordings_status_time", "status", "start_time"),  # For finding recordings by status and time
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    stream_id = Column(Integer, ForeignKey("streams.id", ondelete="CASCADE"), nullable=False, index=True)
    start_time = Column(DateTime(timezone=True), nullable=False, index=True)
    end_time = Column(DateTime(timezone=True), nullable=True)
    status = Column(String, nullable=False, index=True)  # "recording", "completed", "error", "failed"
    duration = Column(Integer, nullable=True)  # Duration in seconds
    path = Column(String, nullable=True)  # Path to the recording file
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Error tracking (Migration 027)
    error_message = Column(String, nullable=True)  # Detailed error message for debugging
    failure_reason = Column(String, nullable=True)  # Short failure reason (proxy_error, streamlink_crash, etc.)
    failure_timestamp = Column(DateTime(timezone=True), nullable=True)  # When the failure occurred

    # Relationship to Stream
    stream = relationship("Stream", backref="recordings")


class Streamer(Base):
    __tablename__ = "streamers"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    twitch_id = Column(String, unique=True, nullable=False, index=True)
    username = Column(String, nullable=False, index=True)
    is_live = Column(Boolean, default=False, index=True)
    title = Column(String)
    category_name = Column(String, index=True)
    language = Column(String)
    last_updated = Column(DateTime(timezone=True))
    profile_image_url = Column(String)
    original_profile_image_url = Column(String)
    offline_image_url = Column(String)  # Twitch banner image (cached)
    original_offline_image_url = Column(String)  # Twitch banner (original URL)
    is_favorite = Column(Boolean, default=False, index=True)
    auto_record = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Test data flag - for automated tests (not shown in frontend)
    is_test_data = Column(Boolean, default=False, nullable=False, index=True)

    # Last stream information (shown when offline)
    last_stream_title = Column(String, nullable=True)
    last_stream_category_name = Column(String, nullable=True)
    last_stream_viewer_count = Column(Integer, nullable=True)
    last_stream_ended_at = Column(DateTime(timezone=True), nullable=True)

    notification_settings = relationship("NotificationSettings", back_populates="streamer")

    @property
    def display_name(self):
        """[DEPRECATED] Use `username` directly instead. This property will be removed in the future."""
        warnings.warn(
            "The `display_name` property is deprecated and will be removed in the future. Use `username` instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.username

    @property
    def is_recording(self) -> bool:
        """
        Check if this streamer currently has an active recording.
        Returns True if there's an active recording (status='recording') for any of this streamer's streams.

        This property dynamically queries the Recording table to ensure real-time accuracy.
        """
        from sqlalchemy.orm import object_session

        session = object_session(self)
        if not session:
            return False

        # Check if there's any active recording for this streamer's streams
        active_recording = (
            session.query(Recording)
            .join(Stream)
            .filter(Stream.streamer_id == self.id, Recording.status == "recording")
            .first()
        )

        return active_recording is not None

    @property
    def recording_enabled(self) -> bool:
        """
        Alias for auto_record field for backward compatibility.
        Returns True if automatic recording is enabled for this streamer.
        """
        return self.auto_record


class Stream(Base):
    __tablename__ = "streams"
    __table_args__ = (
        # Composite indexes for common query patterns
        Index("idx_streams_streamer_active", "streamer_id", "ended_at"),  # For finding active streams
        Index("idx_streams_streamer_recent", "streamer_id", "started_at"),  # For recent streams by streamer
        Index("idx_streams_category_recent", "category_name", "started_at"),  # For recent streams by category
        Index("idx_streams_time_range", "started_at", "ended_at"),  # For time-based queries
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    streamer_id = Column(Integer, ForeignKey("streamers.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String, nullable=True)
    category_name = Column(String, nullable=True, index=True)
    language = Column(String, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True, index=True)
    ended_at = Column(DateTime(timezone=True), nullable=True, index=True)
    twitch_stream_id = Column(String, nullable=True, index=True)
    recording_path = Column(String, nullable=True)  # Path to the recorded MP4 file
    episode_number = Column(Integer, nullable=True)  # Episode number for this stream
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    streamer = relationship("Streamer", backref="streams")
    stream_metadata = relationship("StreamMetadata", back_populates="stream", uselist=False)
    active_recording_state = relationship(
        "ActiveRecordingState", back_populates="stream", uselist=False, cascade="all, delete-orphan"
    )

    @property
    def is_live(self):
        return self.ended_at is None


class StreamEvent(Base):
    __tablename__ = "stream_events"
    __table_args__ = (
        # Composite indexes for common query patterns
        Index("idx_stream_events_stream_type", "stream_id", "event_type"),  # For finding events by stream and type
        Index("idx_stream_events_stream_time", "stream_id", "timestamp"),  # For chronological events by stream
        Index("idx_stream_events_type_time", "event_type", "timestamp"),  # For recent events by type
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True)
    stream_id = Column(Integer, ForeignKey("streams.id", ondelete="CASCADE"), index=True)
    event_type = Column(String, nullable=False, index=True)
    title = Column(String, nullable=True)
    category_name = Column(String, nullable=True)
    language = Column(String, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationship to Stream
    stream = relationship("Stream", backref="stream_events")


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    favorite_categories = relationship("FavoriteCategory", back_populates="user", cascade="all, delete-orphan")


class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    token = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class NotificationSettings(Base):
    __tablename__ = "notification_settings"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    streamer_id = Column(Integer, ForeignKey("streamers.id", ondelete="CASCADE"), nullable=False, index=True)
    notify_online = Column(Boolean, default=True)
    notify_offline = Column(Boolean, default=True)
    notify_update = Column(Boolean, default=True)
    notify_favorite_category = Column(Boolean, default=True)
    streamer = relationship("Streamer", back_populates="notification_settings")


class NotificationState(Base):
    """Tracks notification read/clear state per user"""

    __tablename__ = "notification_state"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    last_read_timestamp = Column(DateTime(timezone=True), nullable=True)  # Last time user marked notifications as read
    last_cleared_timestamp = Column(DateTime(timezone=True), nullable=True)  # Last time user cleared all notifications
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationship to user
    user = relationship("User", backref="notification_state")


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    twitch_id = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    box_art_url = Column(String, nullable=True)
    first_seen = Column(DateTime(timezone=True), server_default=func.now())
    last_seen = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    favorites = relationship("FavoriteCategory", back_populates="category", cascade="all, delete-orphan")


class FavoriteCategory(Base):
    __tablename__ = "favorite_categories"
    __table_args__ = (UniqueConstraint("user_id", "category_id", name="uq_user_category"), {"extend_existing": True})

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    category_id = Column(Integer, ForeignKey("categories.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user = relationship("User", back_populates="favorite_categories")
    category = relationship("Category", back_populates="favorites")


class GlobalSettings(Base):
    __tablename__ = "global_settings"
    __table_args__ = {"extend_existing": True}

    id: int = Column(Integer, primary_key=True)
    notification_url: Optional[str] = Column(String)
    notifications_enabled: bool = Column(Boolean, default=True)
    notify_online_global: bool = Column(Boolean, default=True)
    notify_offline_global: bool = Column(Boolean, default=True)
    notify_update_global: bool = Column(Boolean, default=True)
    notify_favorite_category_global: bool = Column(Boolean, default=True)
    http_proxy: Optional[str] = Column(String)
    https_proxy: Optional[str] = Column(String)

    # System notification settings (Migration 028)
    notify_recording_started: bool = Column(Boolean, default=False)  # OFF: Every stream triggers recording, too noisy
    notify_recording_failed: bool = Column(Boolean, default=True)  # ON: Critical issue, user needs to know
    notify_recording_completed: bool = Column(Boolean, default=False)  # OFF: Most recordings complete normally, noisy

    # Codec preferences (Migration 024) - H.265/AV1 Support (Streamlink 8.0.0+)
    # Default: H.264 with H.265 fallback (best compatibility/quality)
    supported_codecs: str = Column(String, default="h264,h265")
    prefer_higher_quality: bool = Column(Boolean, default=True)  # Auto-select highest available quality with h265/av1

    # Proxy encryption key (Migration 032) - Persists Fernet key for proxy credential encryption
    # Auto-generated on first use, persists across restarts
    proxy_encryption_key: Optional[str] = Column(String, nullable=True)

    # Twitch OAuth Token Refresh (Migration 033) - Automatic token refresh without manual intervention
    twitch_refresh_token: Optional[str] = Column(Text, nullable=True)  # Long-lived refresh token (encrypted)
    twitch_token_expires_at: Optional[datetime] = Column(DateTime, nullable=True)  # When current access token expires
    twitch_access_token: Optional[str] = Column(Text, nullable=True)  # Current access token (encrypted, Migration 034)


class RecordingSettings(Base):
    __tablename__ = "recording_settings"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)
    enabled = Column(Boolean, default=False)
    output_directory = Column(String, default="/recordings")
    filename_template = Column(
        String, default="{streamer}/{streamer}_{year}-{month}-{day}_{hour}-{minute}_{title}_{game}"
    )
    default_quality = Column(String, default="best")
    use_chapters = Column(Boolean, default=True)
    filename_preset = Column(String, default="default")
    use_category_as_chapter_title = Column(Boolean, default=False)
    max_streams_per_streamer = Column(Integer, default=0)  # 0 = unlimited
    cleanup_policy = Column(String, nullable=True)  # JSON string for cleanup policy

    # Multi-Proxy System Configuration (Migration 025)
    enable_proxy = Column(Boolean, default=True)  # Master switch for proxy system
    proxy_health_check_enabled = Column(Boolean, default=True)  # Enable automatic health checks
    proxy_health_check_interval_seconds = Column(Integer, default=300)  # Check interval (5 minutes)
    proxy_max_consecutive_failures = Column(Integer, default=3)  # Auto-disable threshold
    fallback_to_direct_connection = Column(Boolean, default=True)  # Use direct connection when all proxies fail


class StreamerRecordingSettings(Base):
    __tablename__ = "streamer_recording_settings"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)
    streamer_id = Column(Integer, ForeignKey("streamers.id", ondelete="CASCADE"), nullable=False, index=True)
    enabled = Column(Boolean, default=True)
    quality = Column(String, default="best")
    custom_filename = Column(String, nullable=True)
    max_streams = Column(Integer, nullable=True)  # Per-streamer override for max recordings
    cleanup_policy = Column(String, nullable=True)  # JSON string for cleanup policy
    use_global_cleanup_policy = Column(Boolean, default=True)  # Use global cleanup policy or streamer-specific

    # Per-streamer codec preferences (Migration 031)
    # NULL = use global default from GlobalSettings.supported_codecs
    # "h264" = force H.264 only (no OAuth required)
    # "h265,h264" = prefer H.265, fallback to H.264 (requires OAuth for H.265)
    # "av1,h265,h264" = prefer AV1, then H.265, then H.264 (requires OAuth)
    supported_codecs = Column(String, nullable=True)

    streamer = relationship("Streamer", back_populates="recording_settings")


Streamer.recording_settings = relationship(
    "StreamerRecordingSettings", back_populates="streamer", uselist=False, cascade="all, delete-orphan"
)


class StreamMetadata(Base):
    __tablename__ = "stream_metadata"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)
    stream_id = Column(Integer, ForeignKey("streams.id", ondelete="CASCADE"), index=True)

    # Thumbnails
    thumbnail_path = Column(String)
    thumbnail_url = Column(String)

    # Metadata files
    nfo_path = Column(String)
    json_path = Column(String)
    tvshow_nfo_path = Column(String)  # TVShow NFO file for media servers
    season_nfo_path = Column(String)  # Season NFO file for media servers

    # Kapitelmarker (all generated formats)
    chapters_vtt_path = Column(String)
    chapters_srt_path = Column(String)
    chapters_ffmpeg_path = Column(String)
    chapters_xml_path = Column(String)  # XML chapters for Emby/Jellyfin

    # Segments directory tracking (for cleanup)
    segments_dir_path = Column(String)  # Path to _segments directory during recording
    segments_removed = Column(Boolean, default=False)  # Whether segments were cleaned up

    # Stream info stats
    avg_viewers = Column(Integer)
    max_viewers = Column(Integer)
    follower_count = Column(Integer)

    # Beziehung zum Stream
    stream = relationship("Stream", back_populates="stream_metadata")


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    endpoint = Column(String, unique=True, nullable=False)
    subscription_data = Column(Text, nullable=False)  # JSON string of the subscription object
    user_agent = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SystemConfig(Base):
    __tablename__ = "system_config"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String, unique=True, nullable=False)
    value = Column(Text, nullable=False)
    description = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ActiveRecordingState(Base):
    """
    Persistent state for active recordings

    This table tracks active recording processes and survives application restarts.
    It enables recovery of running recordings after crashes or deployments.
    """

    __tablename__ = "active_recordings_state"
    __table_args__ = (
        Index("ix_active_recordings_stream_id", "stream_id"),
        Index("ix_active_recordings_status", "status"),
        Index("ix_active_recordings_heartbeat", "last_heartbeat"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    stream_id = Column(Integer, ForeignKey("streams.id", ondelete="CASCADE"), nullable=False, unique=True)
    recording_id = Column(Integer, ForeignKey("recordings.id"), nullable=False)
    process_id = Column(Integer, nullable=False)  # OS process ID
    process_identifier = Column(String(100), nullable=False)  # Internal process identifier
    streamer_name = Column(String(100), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=False)
    ts_output_path = Column(String(500), nullable=False)
    force_mode = Column(Boolean, default=False)
    quality = Column(String(50), default="best")
    status = Column(String(50), default="active")  # active, stopping, error
    last_heartbeat = Column(DateTime(timezone=True), nullable=False)
    config_json = Column(Text, nullable=True)  # Serialized config
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    stream = relationship("Stream", back_populates="active_recording_state")
    recording = relationship("Recording")

    def get_config(self):
        """Get deserialized config"""
        if self.config_json:
            return json.loads(self.config_json)
        return {}

    def set_config(self, config_dict):
        """Set serialized config"""
        self.config_json = json.dumps(config_dict) if config_dict else None

    def is_stale(self, max_age_seconds=300):
        """Check if heartbeat is stale (default 5 minutes)"""
        if not self.last_heartbeat:
            return True
        age = (datetime.now(self.last_heartbeat.tzinfo) - self.last_heartbeat).total_seconds()
        return age > max_age_seconds


class RecordingProcessingState(Base):
    """
    Persistent per-recording post-processing status.
    Tracks which steps have completed so pipelines can resume idempotently.
    """

    __tablename__ = "recording_processing_state"
    __table_args__ = (
        Index("ix_rps_recording_id", "recording_id", unique=True),
        Index("ix_rps_stream_id", "stream_id"),
        Index("ix_rps_updated_at", "updated_at"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    recording_id = Column(Integer, ForeignKey("recordings.id", ondelete="CASCADE"), nullable=False, unique=True)
    stream_id = Column(Integer, ForeignKey("streams.id", ondelete="CASCADE"), nullable=False, index=True)
    streamer_id = Column(Integer, ForeignKey("streamers.id", ondelete="CASCADE"), nullable=False, index=True)

    # Step statuses: 'pending' | 'running' | 'completed' | 'failed'
    metadata_status = Column(String(20), default="pending", nullable=False)
    chapters_status = Column(String(20), default="pending", nullable=False)
    mp4_remux_status = Column(String(20), default="pending", nullable=False)
    mp4_validation_status = Column(String(20), default="pending", nullable=False)
    thumbnail_status = Column(String(20), default="pending", nullable=False)
    cleanup_status = Column(String(20), default="pending", nullable=False)

    last_error = Column(Text, nullable=True)

    # Store created task IDs for debugging/inspection
    task_ids_json = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def set_task_ids(self, task_ids: dict):
        self.task_ids_json = json.dumps(task_ids) if task_ids else None

    def get_task_ids(self):
        try:
            return json.loads(self.task_ids_json) if self.task_ids_json else {}
        except Exception:
            return {}


class ProxySettings(Base):
    """
    Multi-Proxy Configuration System

    Stores multiple proxy configurations with health monitoring and automatic failover.
    Prevents recording failures when a single proxy goes down.

    SECURITY: Proxy credentials are encrypted in database using Fernet symmetric encryption.
    The proxy_url column stores encrypted credentials, which are automatically decrypted
    when accessed via the decrypted_proxy_url property.

    Selection Algorithm:
    1. Filter: Only enabled=TRUE proxies
    2. Prioritize: healthy > degraded > failed (by health_status)
    3. Sort: By priority field (ascending, 0 = highest)
    4. Sort: By average_response_time_ms (ascending, faster = better)
    5. Return: First match or None
    """

    __tablename__ = "proxy_settings"
    __table_args__ = (
        Index("ix_proxy_enabled", "enabled"),
        Index("ix_proxy_health_status", "health_status"),
        Index("ix_proxy_priority", "priority"),
        Index("ix_proxy_enabled_health_priority", "enabled", "health_status", "priority"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    # ENCRYPTED: Full proxy URL with credentials
    _proxy_url_encrypted = Column("proxy_url", String(1000), nullable=False)
    priority = Column(Integer, nullable=False, default=0)  # 0 = highest priority, lower number = higher priority
    enabled = Column(Boolean, nullable=False, default=True)  # Active status - disabled proxies not used

    # Health monitoring fields
    last_health_check = Column(DateTime(timezone=True), nullable=True)  # Timestamp of last health test
    health_status = Column(String(20), nullable=False, default="unknown")  # healthy/degraded/failed/unknown
    consecutive_failures = Column(Integer, nullable=False, default=0)  # Failure counter for auto-disable
    average_response_time_ms = Column(Integer, nullable=True)  # Response time in milliseconds

    # Statistics tracking
    total_recordings = Column(Integer, nullable=False, default=0)  # How many times used
    failed_recordings = Column(Integer, nullable=False, default=0)  # How many times failed
    success_rate = Column(Float, nullable=True)  # Calculated: (total - failed) / total

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    @property
    def proxy_url(self) -> str:
        """
        Get decrypted proxy URL.

        SECURITY: Automatically decrypts the stored encrypted URL when accessed.
        Use this property when passing proxy URL to Streamlink or other services.
        """
        from app.utils.proxy_encryption import get_proxy_encryption

        try:
            return get_proxy_encryption().decrypt(self._proxy_url_encrypted)
        except Exception as e:
            import logging

            logger = logging.getLogger("streamvault")
            logger.error(f"Failed to decrypt proxy URL for ID {self.id}: {e}")
            return ""  # Return empty string on decryption failure

    @proxy_url.setter
    def proxy_url(self, plaintext_url: str):
        """
        Set proxy URL (automatically encrypts before storing).

        SECURITY: Automatically encrypts the URL before storing in database.
        """
        from app.utils.proxy_encryption import get_proxy_encryption

        if plaintext_url:
            self._proxy_url_encrypted = get_proxy_encryption().encrypt(plaintext_url)
        else:
            self._proxy_url_encrypted = ""

    @property
    def masked_url(self) -> str:
        """
        Return proxy URL with password masked for security.
        Example: http://username:***@proxy-host:9999

        SECURITY: Safe to display in UI and logs.
        """
        decrypted_url = self.proxy_url

        if "@" in decrypted_url:
            parts = decrypted_url.split("@")
            if ":" in parts[0]:
                # Split protocol://username:password
                user_part = parts[0].rsplit(":", 1)[0]
                return f"{user_part}:***@{parts[1]}"
        return decrypted_url

    def calculate_success_rate(self) -> Optional[float]:
        """Calculate success rate as percentage"""
        if self.total_recordings == 0:
            return None
        return ((self.total_recordings - self.failed_recordings) / self.total_recordings) * 100.0

    def update_success_rate(self):
        """Update the success_rate column based on current statistics"""
        self.success_rate = self.calculate_success_rate()

    def to_dict(self, mask_password: bool = True) -> dict:
        """
        Serialize proxy settings to dictionary.

        Args:
            mask_password: If True, replace password with *** in URL
        """
        return {
            "id": self.id,
            "proxy_url": self.masked_url if mask_password else self.proxy_url,
            "masked_url": self.masked_url,  # Always include masked URL for display
            "priority": self.priority,
            "enabled": self.enabled,
            "last_check": self.last_health_check.isoformat() if self.last_health_check else None,  # Changed key name
            "health_status": self.health_status,
            "response_time_ms": self.average_response_time_ms,  # Changed key name
            "consecutive_failures": self.consecutive_failures,
            "last_error": None,  # TODO: Add last_error column to model if needed
            "total_requests": self.total_recordings,  # Renamed for clarity
            "successful_requests": self.total_recordings - self.failed_recordings,  # Calculated field
            "failed_requests": self.failed_recordings,  # Renamed for clarity
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
