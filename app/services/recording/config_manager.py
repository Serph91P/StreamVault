"""
Configuration manager for the recording service.

This module handles all configuration access with efficient caching.
"""
import logging
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
import os

from app.database import SessionLocal
from app.models import RecordingSettings, StreamerRecordingSettings

logger = logging.getLogger("streamvault")

# Filename presets for different media server structures
FILENAME_PRESETS = {
    "default": "{streamer}_{year}-{month}-{day}_{hour}-{minute}_{title}_{game}",
    "plex": "Season {year}-{month}/{streamer} - S{year}{month}E{episode:02d} - {title}",
    "emby": "Season {year}-{month}/{streamer} - S{year}{month}E{episode:02d} - {title}",
    "jellyfin": "Season {year}-{month}/{streamer} - S{year}{month}E{episode:02d} - {title}",
    "kodi": "Season {year}-{month}/{streamer} - S{year}{month}E{episode:02d} - {title}",
    "chronological": "{year}/{month}/{day}/{streamer} - E{episode:02d} - {title} - {hour}-{minute}"
}

class ConfigManager:
    """Manages and caches recording configuration settings"""

    def __init__(self):
        self.cache_timeout = 300  # 5 minutes cache timeout
        self.last_refresh = datetime.min
        self._global_settings = None
        self._streamer_settings = {}

    def _is_cache_valid(self) -> bool:
        """Check if the cached settings are still valid"""
        return (datetime.now() - self.last_refresh).total_seconds() < self.cache_timeout

    def invalidate_cache(self):
        """Force invalidation of the cache"""
        self._global_settings = None
        self._streamer_settings = {}
        self.last_refresh = datetime.min

    def _categorize_database_error(self, error: Exception, table_name: str) -> Optional[str]:
        """Categorize database errors for better handling.
        
        Args:
            error: The exception that was raised
            table_name: Name of the table being accessed
            
        Returns:
            Error category string or None to continue default handling
        """
        error_msg = str(error).lower()
        
        # Check for table/relation doesn't exist
        if "relation" in error_msg and "does not exist" in error_msg:
            logger.warning(f"{table_name} table doesn't exist yet: {error}")
            logger.info(f"Using default settings - {table_name} table may not exist yet during migration")
            return "table_not_exists"
        
        # Check for connection issues
        elif "connection" in error_msg or "database" in error_msg:
            logger.error(f"Database connection error accessing {table_name}: {error}")
            return "connection_error"
        
        # Check for specific SQLAlchemy errors by type
        error_type = type(error).__name__
        if "ProgrammingError" in error_type or "OperationalError" in error_type:
            # These are typically schema/table issues
            logger.warning(f"Database schema error accessing {table_name}: {error}")
            return "schema_error"
        
        # Other unexpected errors
        logger.error(f"Unexpected error accessing {table_name}: {error}")
        return "unexpected_error"

    def _is_cache_valid(self) -> bool:
        """Check if the cached settings are still valid"""
        return (datetime.now() - self.last_refresh).total_seconds() < self.cache_timeout

    def invalidate_cache(self):
        """Force invalidation of the cache"""
        self._global_settings = None
        self._streamer_settings = {}
        self.last_refresh = datetime.min

    def get_global_settings(self) -> Optional[RecordingSettings]:
        """Get global recording settings, using cache if valid"""
        if not self._global_settings or not self._is_cache_valid():
            try:
                with SessionLocal() as db:
                    self._global_settings = db.query(RecordingSettings).first()
                    self.last_refresh = datetime.now()
            except Exception as e:
                error_category = self._categorize_database_error(e, "RecordingSettings")
                if error_category in ["table_not_exists", "connection_error", "schema_error", "unexpected_error"]:
                    return None
        return self._global_settings

    def get_streamer_settings(
        self, streamer_id: int
    ) -> Optional[StreamerRecordingSettings]:
        """Get streamer-specific recording settings, using cache if valid"""
        if streamer_id not in self._streamer_settings or not self._is_cache_valid():
            try:
                with SessionLocal() as db:
                    self._streamer_settings[streamer_id] = (
                        db.query(StreamerRecordingSettings)
                        .filter(StreamerRecordingSettings.streamer_id == streamer_id)
                        .first()
                    )
                    self.last_refresh = datetime.now()
            except Exception as e:
                error_category = self._categorize_database_error(e, "StreamerRecordingSettings")
                if error_category in ["table_not_exists", "connection_error", "schema_error", "unexpected_error"]:
                    return None
        return self._streamer_settings.get(streamer_id)

    def is_recording_enabled(self, streamer_id: int) -> bool:
        """Check if recording is enabled for a streamer"""
        global_settings = self.get_global_settings()
        if not global_settings or not global_settings.enabled:
            return False

        streamer_settings = self.get_streamer_settings(streamer_id)
        if not streamer_settings or not streamer_settings.enabled:
            return False

        return True

    def get_quality_setting(self, streamer_id: int) -> str:
        """Get the quality setting for a streamer"""
        global_settings = self.get_global_settings()
        streamer_settings = self.get_streamer_settings(streamer_id)

        if streamer_settings and streamer_settings.quality:
            return streamer_settings.quality
        elif global_settings:
            return global_settings.default_quality or "best"
        else:
            return "best"

    def get_filename_template(self, streamer_id: int) -> str:
        """Get the filename template for a streamer"""
        global_settings = self.get_global_settings()
        streamer_settings = self.get_streamer_settings(streamer_id)

        if streamer_settings and streamer_settings.custom_filename:
            return streamer_settings.custom_filename
        elif global_settings:
            return global_settings.filename_template or FILENAME_PRESETS["default"]
        else:
            return FILENAME_PRESETS["default"]

    def get_max_streams(self, streamer_id: int) -> int:
        """Get the maximum number of streams for a streamer"""
        streamer_settings = self.get_streamer_settings(streamer_id)
        if streamer_settings and streamer_settings.max_streams is not None and streamer_settings.max_streams > 0:
            return streamer_settings.max_streams
            
        global_settings = self.get_global_settings()
        if global_settings and global_settings.max_streams_per_streamer:
            return global_settings.max_streams_per_streamer
            
        return 0  # 0 means unlimited
        
    def get_output_directory(self) -> str:
        """Get output directory - hardcoded for Docker consistency"""
        return "/recordings"
    
    def get_recordings_directory(self) -> str:
        """Get recordings directory - hardcoded for Docker consistency"""
        return "/recordings"
    
    def get_max_concurrent_recordings(self) -> int:
        """Get maximum number of concurrent recordings"""
        # 1) Environment variable override takes precedence if set and valid
        try:
            env_val = os.getenv("STREAMVAULT_MAX_CONCURRENT_RECORDINGS")
            if env_val is not None:
                env_int = int(env_val)
                if env_int > 0:
                    return env_int
        except Exception:
            # Ignore malformed env var and fall back to DB/default
            pass

        # 2) Database/global settings (if column exists in schema)
        global_settings = self.get_global_settings()
        if global_settings and hasattr(global_settings, 'max_concurrent_recordings'):
            return getattr(global_settings, 'max_concurrent_recordings', 3)

        # 3) Safe default
        return 3  # Default to 3 concurrent recordings
    
    def get_check_interval(self) -> int:
        """Get check interval for recording service in seconds"""
        global_settings = self.get_global_settings()
        if global_settings and hasattr(global_settings, 'check_interval'):
            return getattr(global_settings, 'check_interval', 30)
        return 30  # Default to 30 seconds
    
    def get_config_value(self, key: str, default=None):
        """Get a configuration value by key"""
        global_settings = self.get_global_settings()
        if global_settings and hasattr(global_settings, key):
            return getattr(global_settings, key, default)
        return default
