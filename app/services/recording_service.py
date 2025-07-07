import os
import asyncio
import logging
import subprocess
import re
import signal
import json
import tempfile
import copy
import uuid
import time
import functools
import aiohttp
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Optional, List, Any, Tuple, Callable
from sqlalchemy import extract
from functools import lru_cache
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models import (
    Streamer,
    RecordingSettings,
    StreamerRecordingSettings,
    Stream,
    StreamEvent,
    StreamMetadata,
)
from app.config.settings import settings
from app.services.metadata_service import MetadataService
from app.services.logging_service import logging_service
from app.services.media_server_structure_service import MediaServerStructureService
from app.dependencies import websocket_manager
from app.utils.streamlink_utils import get_streamlink_command, get_proxy_settings_from_db

logger = logging.getLogger("streamvault")

# Spezieller Logger für Recording-Aktivitäten
recording_logger = logging.getLogger("streamvault.recording")

# Filename presets for different media server structures
FILENAME_PRESETS = {
    "default": "{streamer}/{streamer}_{year}-{month}-{day}_{hour}-{minute}_{title}_{game}",
    "plex": "{streamer}/Season {year}-{month}/{streamer} - S{year}{month}E{episode:02d} - {title}",
    "emby": "{streamer}/Season {year}-{month}/{streamer} - S{year}{month}E{episode:02d} - {title}",
    "jellyfin": "{streamer}/Season {year}-{month}/{streamer} - S{year}{month}E{episode:02d} - {title}",
    "kodi": "{streamer}/Season {year}-{month}/{streamer} - S{year}{month}E{episode:02d} - {title}",
    "chronological": "{year}/{month}/{day}/{streamer} - E{episode:02d} - {title} - {hour}-{minute}"
}

class RecordingActivityLogger:
    """Detailliertes Logging für alle Recording-Aktivitäten"""
    
    def __init__(self):
        self.session_id = str(uuid.uuid4())[:8]
        self.logger = logging_service.recording_logger
    
    def log_recording_start(self, streamer_id: int, streamer_name: str, quality: str, output_path: str):
        """Log the start of a recording session"""
        self.logger.info(f"[SESSION:{self.session_id}] RECORDING_START - Streamer: {streamer_name} (ID: {streamer_id})")
        self.logger.info(f"[SESSION:{self.session_id}] Quality: {quality}, Output: {output_path}")
    
    def log_recording_stop(self, streamer_id: int, streamer_name: str, reason: str = "manual"):
        """Log the stop of a recording session"""
        self.logger.info(f"[SESSION:{self.session_id}] RECORDING_STOP - Streamer: {streamer_name} (ID: {streamer_id}), Reason: {reason}")
    
    def log_recording_error(self, streamer_id: int, streamer_name: str, error: str):
        """Log recording errors"""
        self.logger.error(f"[SESSION:{self.session_id}] RECORDING_ERROR - Streamer: {streamer_name} (ID: {streamer_id}), Error: {error}")
    
    def log_process_monitoring(self, streamer_name: str, action: str, details: str = ""):
        """Log process monitoring activities"""
        self.logger.debug(f"[SESSION:{self.session_id}] PROCESS_MONITOR - {streamer_name}: {action} {details}")
    
    def log_file_operation(self, operation: str, file_path: str, success: bool, details: str = ""):
        """Log file operations (remux, conversion, etc.)"""
        status = "SUCCESS" if success else "FAILED"
        self.logger.info(f"[SESSION:{self.session_id}] FILE_OP - {operation}: {file_path} - {status} {details}")
    
    def log_stream_detection(self, streamer_name: str, is_live: bool, stream_info: Optional[dict] = None):
        """Log stream detection and status"""
        status = "LIVE" if is_live else "OFFLINE"
        self.logger.info(f"[SESSION:{self.session_id}] STREAM_STATUS - {streamer_name}: {status}")
        if stream_info:
            title = stream_info.get('title', 'Unknown')
            category = stream_info.get('category_name', 'Unknown')
            self.logger.info(f"[SESSION:{self.session_id}] STREAM_INFO - {streamer_name}: Title='{title}', Category='{category}'")
            recording_logger.debug(f"[SESSION:{self.session_id}] STREAM_INFO - {streamer_name}: {json.dumps(stream_info, indent=2)}")
    
    def log_configuration_change(self, setting: str, old_value: Any, new_value: Any, streamer_id: Optional[int] = None):
        """Log configuration changes"""
        target = f"Global" if streamer_id is None else f"Streamer {streamer_id}"
        recording_logger.info(f"[SESSION:{self.session_id}] CONFIG_CHANGE - {target}: {setting} changed from {old_value} to {new_value}")
    
    def log_metadata_operation(self, streamer_name: str, operation: str, success: bool, details: str = ""):
        """Log metadata operations"""
        status = "SUCCESS" if success else "FAILED"
        recording_logger.info(f"[SESSION:{self.session_id}] METADATA - {streamer_name}: {operation} - {status} {details}")
    
    def log_cleanup_operation(self, streamer_name: str, files_deleted: int, space_freed: int, details: str = ""):
        """Log cleanup operations"""
        recording_logger.info(f"[SESSION:{self.session_id}] CLEANUP - {streamer_name}: Deleted {files_deleted} files, freed {space_freed} MB {details}")


# Define performance monitoring decorators
def timing_decorator(func):
    """Decorator to log execution time of functions"""

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        operation_id = kwargs.pop("operation_id", str(uuid.uuid4())[:8])
        method_name = func.__name__
        start_time = time.time()
        logger.debug(f"[{operation_id}] Starting {method_name}")

        try:
            result = await func(*args, **kwargs, operation_id=operation_id)
            elapsed = time.time() - start_time
            logger.info(f"[{operation_id}] {method_name} completed in {elapsed:.2f}s")
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(
                f"[{operation_id}] {method_name} failed after {elapsed:.2f}s: {e}"
            )
            raise

    return wrapper


def sync_timing_decorator(func):
    """Decorator to log execution time of synchronous functions"""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        operation_id = kwargs.pop("operation_id", str(uuid.uuid4())[:8])
        method_name = func.__name__
        start_time = time.time()
        logger.debug(f"[{operation_id}] Starting {method_name}")

        try:
            result = func(*args, **kwargs)
            elapsed = time.time() - start_time
            logger.info(f"[{operation_id}] {method_name} completed in {elapsed:.2f}s")
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(
                f"[{operation_id}] {method_name} failed after {elapsed:.2f}s: {e}"
            )
            raise

    return wrapper


# ContextManager for database sessions with automatic cleanup
@asynccontextmanager
async def get_db_session():
    """Context manager for database sessions with automatic commit/rollback"""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# Custom exceptions for domain-specific error cases
class RecordingError(Exception):
    """Base exception for recording-related errors"""

    pass


class StreamerNotFoundError(RecordingError):
    """Raised when a streamer is not found"""

    pass


class StreamNotFoundError(RecordingError):
    """Raised when a stream is not found"""

    pass


class RecordingAlreadyActiveError(RecordingError):
    """Raised when attempting to start a recording that's already active"""

    pass


class StreamlinkError(RecordingError):
    """Raised when streamlink process fails"""

    pass


class FFmpegError(RecordingError):
    """Raised when FFmpeg process fails"""

    pass


# Configuration manager for caching settings
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

    def get_global_settings(self) -> Optional[RecordingSettings]:
        """Get global recording settings, using cache if valid"""
        if not self._global_settings or not self._is_cache_valid():
            with SessionLocal() as db:
                self._global_settings = db.query(RecordingSettings).first()
                self.last_refresh = datetime.now()
        return self._global_settings

    def get_streamer_settings(
        self, streamer_id: int
    ) -> Optional[StreamerRecordingSettings]:
        """Get streamer-specific recording settings, using cache if valid"""
        if streamer_id not in self._streamer_settings or not self._is_cache_valid():
            with SessionLocal() as db:
                settings = (
                    db.query(StreamerRecordingSettings)
                    .filter(StreamerRecordingSettings.streamer_id == streamer_id)
                    .first()
                )
                if settings:
                    self._streamer_settings[streamer_id] = settings
                    self.last_refresh = datetime.now()
                else:
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
            return global_settings.default_quality
        else:
            return "best"  # Default fallback

    def get_filename_template(self, streamer_id: int) -> str:
        """Get the filename template for a streamer"""
        global_settings = self.get_global_settings()
        streamer_settings = self.get_streamer_settings(streamer_id)

        if streamer_settings and streamer_settings.custom_filename:
            return streamer_settings.custom_filename
        elif global_settings:
            return global_settings.filename_template
        else:
            return "{streamer}/Season {year}-{month:02d}/{streamer} - S{year}{month:02d}E{episode:02d} - {title}"  # Default media server compatible fallback

    def get_max_streams(self, streamer_id: int) -> int:
        """Get the maximum number of streams for a streamer"""
        streamer_settings = self.get_streamer_settings(streamer_id)
        if streamer_settings and streamer_settings.max_streams is not None and streamer_settings.max_streams > 0:
            return streamer_settings.max_streams
            
        global_settings = self.get_global_settings()
        if global_settings and global_settings.max_streams_per_streamer:
            return global_settings.max_streams_per_streamer
            
        return 0  # 0 means unlimited


# Subprocess manager for better resource handling
class SubprocessManager:
    """Manages subprocess execution and cleanup"""

    def __init__(self):
        self.active_processes = {}
        self.lock = asyncio.Lock()

    async def start_process(
        self, cmd: List[str], process_id: str
    ) -> Optional[asyncio.subprocess.Process]:
        """Start a subprocess and track it"""
        async with self.lock:
            try:
                logger.debug(f"Starting process {process_id}: {' '.join(cmd)}")
                process = await asyncio.create_subprocess_exec(
                    *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                self.active_processes[process_id] = process
                return process
            except Exception as e:
                logger.error(
                    f"Failed to start process {process_id}: {e}", exc_info=True
                )
                return None

    async def terminate_process(self, process_id: str, timeout: int = 10) -> bool:
        """Gracefully terminate a process"""
        async with self.lock:
            if process_id not in self.active_processes:
                return False

            process = self.active_processes[process_id]
            if process.returncode is not None:
                # Process already completed
                self.active_processes.pop(process_id)
                return True

            try:
                # Try graceful termination first
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=timeout)
                except asyncio.TimeoutError:
                    # Force kill if graceful termination times out
                    logger.warning(
                        f"Process {process_id} did not terminate gracefully, killing"
                    )
                    process.kill()
                    await process.wait()

                self.active_processes.pop(process_id)
                return True
            except Exception as e:
                logger.error(
                    f"Error terminating process {process_id}: {e}", exc_info=True
                )
                return False

    async def cleanup_all(self):
        """Terminate all active processes"""
        process_ids = list(self.active_processes.keys())
        for process_id in process_ids:
            await self.terminate_process(process_id)


# At the top of the file, add this to make RecordingService a singleton
class RecordingService:
    _instance = None  # Make this a class attribute
    
    # Define attributes for type checking
    logger: Any
    streamlink_logger: Any
    ffmpeg_logger: Any
    active_recordings: Dict[int, Dict[str, Any]]
    lock: asyncio.Lock
    metadata_service: Any
    config_manager: Any
    subprocess_manager: Any
    media_server_service: Any
    activity_logger: Any
    initialized: bool

    def __new__(
        cls, metadata_service=None, config_manager=None, subprocess_manager=None
    ):
        if cls._instance is None:
            cls._instance = super(RecordingService, cls).__new__(cls)
            cls._instance.active_recordings = {}
            cls._instance.lock = asyncio.Lock()
            cls._instance.metadata_service = metadata_service or MetadataService()
            cls._instance.config_manager = config_manager or ConfigManager()
            cls._instance.subprocess_manager = subprocess_manager or SubprocessManager()
            cls._instance.media_server_service = MediaServerStructureService()
            cls._instance.activity_logger = RecordingActivityLogger()
            
            # Initialize logging integration
            cls._instance.logger = logging_service.recording_logger
            cls._instance.streamlink_logger = logging_service.streamlink_logger
            cls._instance.ffmpeg_logger = logging_service.ffmpeg_logger
            
            cls._instance.initialized = True
        return cls._instance

    def __init__(
        self, metadata_service=None, config_manager=None, subprocess_manager=None
    ):        # Only initialize once and allow dependency injection
        if not hasattr(self, "initialized"):
            self.active_recordings: Dict[int, Dict[str, Any]] = {}
            self.lock = asyncio.Lock()
            self.metadata_service = metadata_service or MetadataService()
            self.config_manager = config_manager or ConfigManager()
            self.subprocess_manager = subprocess_manager or SubprocessManager()
            self.media_server_service = MediaServerStructureService()
            self.activity_logger = RecordingActivityLogger()
            
            self.initialized = True
            logger.info("RecordingService initialized successfully with logging integration")
            # Dependencies are now injected in __new__

    async def get_active_recordings(self) -> List[Dict[str, Any]]:
        """Get a list of all active recordings"""
        async with self.lock:
            # Add verbose logging for debugging
            logger.debug(
                f"RECORDING STATUS: get_active_recordings called, keys: {list(self.active_recordings.keys())}"
            )

            result = [
                {
                    "streamer_id": int(streamer_id),  # Ensure integer type
                    "streamer_name": info["streamer_name"],
                    "started_at": (
                        info["started_at"].isoformat()
                        if isinstance(info["started_at"], datetime)
                        else info["started_at"]
                    ),
                    "duration": (
                        (datetime.now() - info["started_at"]).total_seconds()
                        if isinstance(info["started_at"], datetime)
                        else 0
                    ),
                    "output_path": info["output_path"],
                    "quality": info["quality"],
                }
                for streamer_id, info in self.active_recordings.items()
            ]

            logger.debug(f"RECORDING STATUS: Returning {len(result)} active recordings")
            return result

    async def start_recording(
        self, streamer_id: int, stream_data: Dict[str, Any], force_mode: bool = False
    ) -> bool:
        """Start recording a stream
        
        Args:
            streamer_id: ID of the streamer
            stream_data: Stream information from Twitch
            force_mode: If True, uses more aggressive streamlink settings (only for manual force recording)
        """
        async with self.lock:
            # Convert streamer_id to integer for consistency
            streamer_id = int(streamer_id)
            
            # Log recording attempt
            recording_logger.info(f"RECORDING_ATTEMPT - Streamer ID: {streamer_id}")
            recording_logger.debug(f"RECORDING_ATTEMPT - Stream data: {json.dumps(stream_data, indent=2)}")

            if streamer_id in self.active_recordings:
                recording_logger.warning(f"RECORDING_ALREADY_ACTIVE - Streamer ID: {streamer_id}")
                logger.debug(f"Recording already active for streamer {streamer_id}")
                raise RecordingAlreadyActiveError(
                    f"Recording already active for streamer {streamer_id}"
                )

            try:
                with SessionLocal() as db:
                    streamer = (
                        db.query(Streamer).filter(Streamer.id == streamer_id).first()
                    )
                    if not streamer:
                        logger.error(f"Streamer not found: {streamer_id}")
                        raise StreamerNotFoundError(
                            f"Streamer not found: {streamer_id}"
                        )

                    # Check if recording is enabled using config manager
                    if not self.config_manager.is_recording_enabled(streamer_id):
                        logger.debug(
                            f"Recording disabled for streamer {streamer.username}"
                        )
                        logging_service.log_recording_activity("RECORDING_DISABLED", streamer.username, f"Recording disabled in configuration")
                        return False

                    # Log stream detection
                    logging_service.log_stream_detection(streamer.username, True, stream_data)

                    # Clean up old recordings for this streamer before starting a new one
                    from app.services.cleanup_service import CleanupService
                    deleted_count, deleted_paths = await CleanupService.cleanup_old_recordings(streamer_id, db)
                    if deleted_count > 0:
                        logger.info(f"Cleaned up {deleted_count} old recordings for streamer {streamer.username}")
                        logging_service.log_file_operation("CLEANUP", f"{deleted_count} files", True, f"Freed space before recording start")

                    # Get quality setting from config manager
                    quality = self.config_manager.get_quality_setting(streamer_id)

                    # Get filename template from config manager
                    template = self.config_manager.get_filename_template(streamer_id)

                    # Generate output filename
                    filename = self._generate_filename(
                        streamer=streamer, stream_data=stream_data, template=template
                    )

                    # Get output directory from global settings
                    global_settings = self.config_manager.get_global_settings()
                    output_directory = global_settings.output_directory if global_settings else "/recordings"
                    output_path = os.path.join(
                        output_directory, filename
                    )
                    os.makedirs(os.path.dirname(output_path), exist_ok=True)

                    # Log recording start attempt
                    logging_service.log_recording_start(streamer_id, streamer.username, quality, output_path)                    
                    # Start streamlink process using subprocess manager
                    process = await self._start_streamlink(
                        streamer_name=streamer.username,
                        quality=quality,
                        output_path=output_path,
                        force_mode=force_mode,
                    )

                    if process:
                        self.active_recordings[streamer_id] = {
                            "process": process,
                            "started_at": datetime.now(),
                            "output_path": output_path,
                            "streamer_name": streamer.username,
                            "quality": quality,
                            "stream_id": None,  # Will be updated when we find/create the stream
                            "process_id": f"streamlink_{streamer_id}",  # ID for subprocess manager
                        }

                        # More verbose and consistent logging
                        logger.info(
                            f"Recording started - Added to active_recordings with key {streamer_id}"
                        )
                        logger.info(
                            f"Current active recordings: {list(self.active_recordings.keys())}"
                        )

                        logger.info(
                            f"Started recording for {streamer.username} at {quality} quality to {output_path}"
                        )
                        await websocket_manager.send_notification(
                            {
                                "type": "recording.started",
                                "data": {
                                    "streamer_id": streamer_id,
                                    "streamer_name": streamer.username,
                                    "started_at": datetime.now().isoformat(),
                                    "quality": quality,
                                    "output_path": output_path,
                                },
                            }
                        )

                        # Find or create stream record and metadata
                        await self._setup_stream_metadata(
                            streamer_id, streamer, output_path
                        )

                        return True

                    return False
            except RecordingError:
                # Re-raise specific domain exceptions
                raise
            except Exception as e:
                logger.error(f"Error starting recording: {e}", exc_info=True)
                return False

    async def _setup_stream_metadata(
        self, streamer_id: int, streamer: Streamer, output_path: str
    ):
        """Set up stream record and metadata for a recording"""
        try:
            with SessionLocal() as db:
                # Find the current stream record
                stream = (
                    db.query(Stream)
                    .filter(
                        Stream.streamer_id == streamer_id, Stream.ended_at.is_(None)
                    )
                    .order_by(Stream.started_at.desc())
                    .first()
                )

                if stream:
                    # Create metadata record if it doesn't exist
                    metadata = (
                        db.query(StreamMetadata)
                        .filter(StreamMetadata.stream_id == stream.id)
                        .first()
                    )

                    if not metadata:
                        metadata = StreamMetadata(stream_id=stream.id)
                        db.add(metadata)
                        db.commit()

                    # Update our recording info with stream ID
                    self.active_recordings[streamer_id]["stream_id"] = stream.id
                    
                    # Schedule delayed thumbnail download with video fallback
                    output_dir = os.path.dirname(output_path)
                    ts_path = output_path.replace(".mp4", ".ts")  # TS file path for fallback
                    
                    # Import thumbnail service
                    from app.services.thumbnail_service import ThumbnailService
                    thumbnail_service = ThumbnailService()
                    
                    asyncio.create_task(
                        thumbnail_service.delayed_thumbnail_download(
                            streamer.username, 
                            stream.id, 
                            output_dir,
                            video_path=ts_path,  # Use TS file for extraction
                            delay_minutes=5  # Wait 5 minutes for stream to stabilize
                        )
                    )
        except Exception as e:
            logger.error(f"Error setting up stream metadata: {e}")
            
    async def stop_recording(self, streamer_id: int) -> bool:
        """Stop an active recording and ensure metadata generation"""
        async with self.lock:
            if streamer_id not in self.active_recordings:
                logger.debug(f"No active recording for streamer {streamer_id}")
                logging_service.log_recording_activity("STOP_ATTEMPT_FAILED", f"Streamer {streamer_id}", "No active recording found", "warning")
                return False

            try:
                recording_info = self.active_recordings.pop(streamer_id)
                process_id = recording_info.get(
                    "process_id", f"streamlink_{streamer_id}"
                )
                
                # Calculate recording duration
                start_time = recording_info.get("started_at")
                duration = 0
                if start_time and isinstance(start_time, datetime):
                    duration = (datetime.now() - start_time).total_seconds()

                # Log recording stop
                logging_service.log_recording_stop(
                    streamer_id, 
                    recording_info['streamer_name'], 
                    duration, 
                    recording_info.get('output_path', 'Unknown'),
                    "manual"
                )

                # Use subprocess manager to terminate the process
                await self.subprocess_manager.terminate_process(process_id)

                logger.info(f"Stopped recording for {recording_info['streamer_name']}")

                # Send recording.stopped notification first
                await websocket_manager.send_notification(
                    {
                        "type": "recording.stopped",
                        "data": {
                            "streamer_id": streamer_id,
                            "streamer_name": recording_info["streamer_name"],
                        },
                    }
                )

                # Get stream ID and "force_started" flag
                stream_id = recording_info.get("stream_id")
                force_started = recording_info.get("force_started", False)
                output_path = recording_info.get("output_path")

                # Ensure we have a stream
                if not stream_id and force_started:
                    stream_id = await self._find_stream_for_recording(streamer_id)

                # Generate metadata after recording stops
                if stream_id:
                    # Allow some time for the remuxing process to complete
                    task = asyncio.create_task(
                        self._delayed_metadata_generation(
                            stream_id, recording_info["output_path"], force_started
                        )
                    )
                    
                    # Send recording.completed notification
                    await websocket_manager.send_notification(
                        {
                            "type": "recording.completed",
                            "data": {
                                "streamer_id": streamer_id,
                                "streamer_name": recording_info["streamer_name"],
                                "output_path": output_path,
                                "timestamp": datetime.now().isoformat(),
                                "duration": (
                                    (datetime.now() - recording_info["started_at"]).total_seconds()
                                    if isinstance(recording_info["started_at"], datetime)
                                    else 0
                                ),
                                "quality": recording_info.get("quality", "unknown")
                            },
                        }
                    )
                else:
                    logger.warning(
                        f"No stream_id available for metadata generation: {recording_info}"
                    )

                return True
            except Exception as e:
                logger.error(f"Error stopping recording: {e}", exc_info=True)
                # Send recording.failed notification
                try:
                    if streamer_id in self.active_recordings:
                        recording_info = self.active_recordings[streamer_id]
                        await websocket_manager.send_notification(
                            {
                                "type": "recording.failed",
                                "data": {
                                    "streamer_id": streamer_id,
                                    "streamer_name": recording_info["streamer_name"],
                                    "error": "Recording failed due to an internal error",
                                    "timestamp": datetime.now().isoformat(),
                                },
                            }
                        )
                except Exception as notify_error:
                    logger.error(f"Error sending recording failure notification: {notify_error}", exc_info=True)
                return False
                
    async def _find_stream_for_recording(self, streamer_id: int) -> Optional[int]:
        """Find a stream record for a recording that was force-started"""
        try:
            with SessionLocal() as db:
                streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
                if streamer:
                    # For force-recordings: Try to find a stream
                    stream = (
                        db.query(Stream)
                        .filter(Stream.streamer_id == streamer_id)
                        .order_by(Stream.started_at.desc())
                        .first()
                    )

                    if stream:
                        return stream.id
            return None
        except Exception as e:
            logger.error(f"Error finding stream for recording: {e}", exc_info=True)
            return None
            
    async def force_start_recording(self, streamer_id: int) -> bool:
        """Manually start a recording for an active stream and ensure full metadata generation"""
        try:
            stream_id = None
            stream_data = None

            with SessionLocal() as db:
                streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
                if not streamer:
                    logger.error(f"Streamer not found: {streamer_id}")
                    raise StreamerNotFoundError(f"Streamer not found: {streamer_id}")                # Check if the streamer is live via Twitch API
                stream_info = await self._get_stream_info_from_api(streamer, db)

                if not stream_info:
                    logger.warning(
                        f"Force recording requested for {streamer.username} but Twitch API indicates not live. Proceeding anyway since this is a manual force start."
                    )
                    # For force recording, we continue even if API says not live
                    # This handles cases where:
                    # 1. API might be having issues
                    # 2. There might be a delay in API updates
                    # 3. User knows better than the API in this specific case
                    
                    # Create a minimal stream_info for force recording
                    stream_info = {
                        "id": f"force_{int(datetime.now().timestamp())}",
                        "user_id": streamer.twitch_id,
                        "user_name": streamer.username,
                        "game_name": streamer.category_name or "Unknown",
                        "title": streamer.title or f"{streamer.username} Stream",
                        "started_at": datetime.now(timezone.utc).isoformat(),
                        "language": streamer.language or "en"
                    }

                # Find or create stream record
                stream = await self._find_or_create_stream(streamer_id, streamer, db)

                # IMPORTANT: Store the ID while we're still in the session
                stream_id = stream.id

                # Prepare stream data for recording
                stream_data = self._prepare_stream_data(streamer, stream)

                # Check if we already have a recording
                if streamer_id in self.active_recordings:
                    logger.info(
                        f"Recording already in progress for {streamer.username}"
                    )
                    return True

                # Get recording settings to check if this streamer has recordings enabled
                recording_enabled = self.config_manager.is_recording_enabled(
                    streamer_id
                )

                if not recording_enabled:
                    # If recordings are disabled for this streamer, temporarily enable it just for this session
                    logger.info(
                        f"Recordings are disabled for {streamer.username}, but force recording was requested. Proceeding with recording."
                    )

                    # Create a temporary copy of the actual settings for this recording session
                    streamer_settings = self.config_manager.get_streamer_settings(
                        streamer_id
                    )

                    # We'll store the original 'enabled' value to restore it later if needed
                    original_setting = False
                    if streamer_settings:
                        original_setting = streamer_settings.enabled

                    # Override recording settings for this particular session
                    temp_settings = (
                        db.query(StreamerRecordingSettings)
                        .filter(StreamerRecordingSettings.streamer_id == streamer_id)
                        .first()
                    )

                    if not temp_settings:
                        temp_settings = StreamerRecordingSettings(
                            streamer_id=streamer_id
                        )
                        db.add(temp_settings)

                    # Store the original setting for later reference
                    temp_settings.original_enabled = original_setting

                    # Temporarily enable recording for this streamer
                    temp_settings.enabled = True
                    db.commit()

                    # Invalidate the cache to ensure settings are reloaded
                    self.config_manager.invalidate_cache()
            
            # Now outside the database session, start the recording process
            if stream_data:
                try:
                    # Start recording with force_mode=True for manual force recording
                    # This uses more aggressive streamlink settings to maximize success chance
                    recording_started = await self.start_recording(streamer_id, stream_data, force_mode=True)

                    # Save the stream ID and force started flag in the recording information
                    if recording_started and streamer_id in self.active_recordings:
                        self.active_recordings[streamer_id]["stream_id"] = stream_id
                        self.active_recordings[streamer_id]["force_started"] = True

                        # Record that this was a forced recording (to handle special case on stop)
                        self.active_recordings[streamer_id]["forced_recording"] = True

                        logger.info(
                            f"Force recording started successfully for {streamer.username}, stream_id: {stream_id}"
                        )

                        return True
                    else:
                        logger.error(f"Force recording failed to start for {streamer.username}. Streamlink may have been unable to connect to the stream.")
                        return False
                        
                except Exception as start_error:
                    logger.error(f"Exception during force recording start for {streamer.username}: {start_error}", exc_info=True)
                    return False

                return recording_started

            return False

        except RecordingError:
            # Re-raise specific domain exceptions
            raise
        except Exception as e:
            logger.error(f"Error force starting recording: {e}", exc_info=True)
            return False

    async def _find_or_create_stream(
        self, streamer_id: int, streamer: Streamer, db
    ) -> Stream:
        """Find an existing stream or create a new one"""
        # Find current stream
        stream = (
            db.query(Stream)
            .filter(Stream.streamer_id == streamer_id, Stream.ended_at.is_(None))
            .order_by(Stream.started_at.desc())
            .first()
        )

        if not stream:            # Create stream entry if none exists
            logger.info(f"Creating new stream record for {streamer.username}")
            stream = Stream(
                streamer_id=streamer_id,
                twitch_stream_id=f"manual_{int(datetime.now().timestamp())}",
                title=streamer.title or f"{streamer.username} Stream",
                category_name=streamer.category_name,
                language=streamer.language,
                started_at=datetime.now(timezone.utc)
                # 'status' is not a field in the Stream model - it uses is_live property based on ended_at
            )
            db.add(stream)
            db.commit()
            db.refresh(stream)

            # Create stream event for the start
            stream_event = StreamEvent(
                stream_id=stream.id,
                event_type="stream.online",
                timestamp=stream.started_at,
                title=stream.title,
                category_name=stream.category_name,
            )
            db.add(stream_event)
            db.commit()

        return stream

    def _prepare_stream_data(
        self, streamer: Streamer, stream: Stream
    ) -> Dict[str, Any]:
        """Prepare stream data for recording"""
        return {
            "id": stream.twitch_stream_id,
            "broadcaster_user_id": streamer.twitch_id,
            "broadcaster_user_name": streamer.username,
            "started_at": (
                stream.started_at.isoformat()
                if stream.started_at
                else datetime.now().isoformat()
            ),
            "title": stream.title,
            "category_name": stream.category_name,
            "language": stream.language,
        }

    async def force_start_recording_offline(
        self, streamer_id: int, stream_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Start a recording for a stream, even if the online event wasn't detected.
        Creates all necessary database entries as if the application had received the event.
        """
        try:
            with SessionLocal() as db:
                streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
                if not streamer:
                    logger.error(f"Streamer not found: {streamer_id}")
                    raise StreamerNotFoundError(f"Streamer not found: {streamer_id}")

                # Check if the streamer is actually live (API query)
                stream_info = await self._get_stream_info_from_api(streamer, db)

                # If no stream data was provided, use the API result or create default data
                if not stream_data:
                    stream_data = self._create_stream_data(streamer, stream_info)

                # Update streamer status to "live"
                self._update_streamer_status(streamer, stream_data, db)

                # Find existing stream or create a new one
                stream = await self._find_or_create_offline_stream(
                    streamer_id, streamer, stream_data, db
                )

                # Create metadata entry if it doesn't exist
                await self._ensure_stream_metadata(stream.id, db)

                # Send WebSocket notification
                await self._send_stream_online_notification(streamer, stream_data)

                # Start the recording with the existing method
                recording_started = await self.start_recording(streamer_id, stream_data, force_mode=False)

                # Save the stream ID in the recording information
                if recording_started and streamer_id in self.active_recordings:
                    # Try to download a Twitch thumbnail
                    output_dir = os.path.dirname(
                        self.active_recordings[streamer_id]["output_path"]
                    )
                    asyncio.create_task(
                        self.metadata_service.download_twitch_thumbnail(
                            streamer.username, stream.id, output_dir
                        )
                    )

                    logger.info(
                        f"Force offline recording started for {streamer.username}, stream_id: {stream.id}"
                    )
                    return True

                return recording_started

        except RecordingError:            # Re-raise specific domain exceptions
            raise
        except Exception as e:
            logger.error(f"Error force starting offline recording: {e}", exc_info=True)
            return False
            
    async def _get_stream_info_from_api(
        self, streamer: Streamer, db
    ) -> Optional[Dict[str, Any]]:
        """Get stream information from Twitch API to verify if streamer is live"""
        try:
            # Import here to avoid circular dependencies
            from app.services.streamer_service import StreamerService

            # Query Twitch API for stream info using the API directly
            # Since we don't need websocket/event functionality, make API call directly
            from app.config.settings import settings
            
            # Get access token for API call
            async with aiohttp.ClientSession() as session:
                # First get access token
                async with session.post(
                    "https://id.twitch.tv/oauth2/token",
                    params={
                        "client_id": settings.TWITCH_APP_ID,
                        "client_secret": settings.TWITCH_APP_SECRET,
                        "grant_type": "client_credentials"
                    }
                ) as token_response:
                    if token_response.status != 200:
                        token_error = await token_response.text()
                        logger.error(f"Failed to get Twitch OAuth token: Status {token_response.status}, Response: {token_error}")
                        return None
                        
                    token_data = await token_response.json()
                    access_token = token_data["access_token"]
                    
                    # Get stream info
                    async with session.get(
                        "https://api.twitch.tv/helix/streams",
                        params={"user_id": streamer.twitch_id},
                        headers={
                            "Client-ID": settings.TWITCH_APP_ID,
                            "Authorization": f"Bearer {access_token}"
                        }
                    ) as stream_response:
                        if stream_response.status != 200:
                            stream_error = await stream_response.text()
                            logger.error(f"Twitch API error when checking if {streamer.username} is live: Status {stream_response.status}, Response: {stream_error}")
                            return None
                            
                        stream_data = await stream_response.json()
                        stream_info = stream_data["data"][0] if stream_data["data"] else None

            if stream_info:
                logger.info(f"Confirmed {streamer.username} is live via Twitch API")
                return stream_info
            else:
                logger.warning(
                    f"Streamer {streamer.username} appears to be offline according to Twitch API"
                )
                # Log the full API response for debugging
                logger.debug(f"Twitch API response for {streamer.username}: {stream_data}")
                return None

        except Exception as e:
            logger.error(f"Error checking stream status via API: {e}", exc_info=True)
            return None

    def _create_stream_data(
        self, streamer: Streamer, stream_info: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Create stream data from streamer and API info"""
        if stream_info:
            # Streamer is actually live, use API data
            return {
                "id": stream_info.get("id"),
                "broadcaster_user_id": streamer.twitch_id,
                "broadcaster_user_name": streamer.username,
                "started_at": stream_info.get("started_at")
                or datetime.now(timezone.utc).isoformat(),
                "title": stream_info.get("title") or streamer.title,
                "category_name": stream_info.get("game_name") or streamer.category_name,
                "language": stream_info.get("language") or streamer.language,
            }
        else:
            # Streamer appears offline or API failed, create default data
            return {
                "id": f"manual_{int(datetime.now().timestamp())}",
                "broadcaster_user_id": streamer.twitch_id,
                "broadcaster_user_name": streamer.username,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "title": streamer.title or f"{streamer.username} Stream",
                "category_name": streamer.category_name or "Unknown",
                "language": streamer.language or "en",
            }

    def _update_streamer_status(
        self, streamer: Streamer, stream_data: Dict[str, Any], db
    ):
        """Update streamer status and information"""
        # Update streamer status to "live"
        streamer.is_live = True
        streamer.last_updated = datetime.now(timezone.utc)

        # Update streamer information if available
        if "title" in stream_data and stream_data["title"]:
            streamer.title = stream_data["title"]
        if "category_name" in stream_data and stream_data["category_name"]:
            streamer.category_name = stream_data["category_name"]
        if "language" in stream_data and stream_data["language"]:
            streamer.language = stream_data["language"]

        db.commit()

    async def _find_or_create_offline_stream(
        self, streamer_id: int, streamer: Streamer, stream_data: Dict[str, Any], db
    ) -> Stream:
        """Find existing active stream or create a new one"""
        # Check if an active stream already exists
        existing_stream = (
            db.query(Stream)
            .filter(Stream.streamer_id == streamer_id, Stream.ended_at.is_(None))
            .order_by(Stream.started_at.desc())
            .first()
        )

        if existing_stream:
            logger.info(
                f"Found existing active stream for {streamer.username}, using it"
            )
            return existing_stream

        # Create a new stream entry        
        started_at = (
            datetime.fromisoformat(stream_data["started_at"].replace("Z", "+00:00"))
            if "started_at" in stream_data
            else datetime.now(timezone.utc)
        )
        
        stream = Stream(
            streamer_id=streamer_id,
            twitch_stream_id=stream_data.get(
                "id", f"manual_{int(datetime.now().timestamp())}"
            ),
            title=stream_data.get("title") or f"{streamer.username} Stream",
            category_name=stream_data.get("category_name"),
            language=stream_data.get("language"),
            started_at=started_at,
        )
        db.add(stream)
        db.flush()  # To get the stream ID

        # Create stream events
        # 1. Stream-Online-Event
        stream_online_event = StreamEvent(
            stream_id=stream.id,
            event_type="stream.online",
            title=stream_data.get("title"),
            category_name=stream_data.get("category_name"),
            language=stream_data.get("language"),
            timestamp=started_at,
        )
        db.add(stream_online_event)

        # 2. Category-Event (1 second before stream start)
        if stream_data.get("category_name"):
            category_event = StreamEvent(
                stream_id=stream.id,
                event_type="channel.update",
                title=stream_data.get("title"),
                category_name=stream_data.get("category_name"),
                language=stream_data.get("language"),
                timestamp=started_at - timedelta(seconds=1),
            )
            db.add(category_event)

        db.commit()
        return stream

    async def _ensure_stream_metadata(self, stream_id: int, db):
        """Ensure metadata entry exists for a stream"""
        metadata = (
            db.query(StreamMetadata)
            .filter(StreamMetadata.stream_id == stream_id)
            .first()
        )

        if not metadata:
            metadata = StreamMetadata(stream_id=stream_id)
            db.add(metadata)
            db.commit()

        return metadata

    async def _send_stream_online_notification(
        self, streamer: Streamer, stream_data: Dict[str, Any]
    ):
        """Send WebSocket notification for stream online event"""
        await websocket_manager.send_notification(
            {
                "type": "stream.online",
                "data": {
                    "streamer_id": streamer.id,
                    "twitch_id": streamer.twitch_id,
                    "streamer_name": streamer.username,
                    "started_at": stream_data.get(
                        "started_at", datetime.now(timezone.utc).isoformat()
                    ),
                    "title": stream_data.get("title"),
                    "category_name": stream_data.get("category_name"),
                    "language": stream_data.get("language"),
                },
            }
        )

    async def _delayed_metadata_generation(
        self,
        stream_id: int,
        output_path: str,
        force_started: bool = False,
        delay: int = 5,
    ):
        """Wait for remuxing to complete before generating metadata"""
        try:
            await asyncio.sleep(delay)  # Short delay to ensure remuxing has started

            # Find and validate the MP4 file
            mp4_path = await self._find_and_validate_mp4(output_path)
            if not mp4_path:
                return

            # Update Stream.recording_path
            if stream_id and mp4_path:
                db_session: Optional[Session] = None
                try:
                    logger.debug(f"Attempting to update recording_path for stream_id: {stream_id} with path: {mp4_path}")
                    db_session = SessionLocal()
                    if db_session:
                        stream_to_update = db_session.query(Stream).filter(Stream.id == stream_id).first()
                        if stream_to_update:
                            stream_to_update.recording_path = mp4_path
                            db_session.commit()
                            logger.info(f"Successfully updated stream {stream_id} with recording_path: {mp4_path}")
                        else:
                            logger.warning(f"Stream with id {stream_id} not found for recording_path update.")
                except Exception as e:
                    if db_session:
                        db_session.rollback()
                    logger.error(f"Error updating recording_path for stream {stream_id}: {e}", exc_info=True)
                finally:
                    if db_session:
                        db_session.close()

            # Ensure stream is properly marked as ended
            await self._ensure_stream_ended(stream_id, force_started)

            # Generate metadata
            logger.info(f"Generating metadata for stream {stream_id} at {mp4_path}")
            await self._generate_stream_metadata(stream_id, mp4_path)

            # Create optimized media server structure
            logger.info(f"Creating media server structure for stream {stream_id}")
            media_server_service = MediaServerStructureService()
            try:
                new_mp4_path = await media_server_service.create_media_server_structure(
                    stream_id, mp4_path
                )
                if new_mp4_path:
                    logger.info(f"Successfully created media server structure for stream {stream_id}")
                    # Update the recording path to the new location
                    await self._update_recording_path(stream_id, new_mp4_path)
                else:
                    logger.warning(f"Failed to create media server structure for stream {stream_id}")
            finally:
                await media_server_service.close()

            # Clean up all temporary files after successful metadata generation
            if mp4_path:
                await self._cleanup_temporary_files(mp4_path)
            
        except Exception as e:
            logger.error(f"Error generating metadata for stream {stream_id}: {e}", exc_info=True)
            # Still attempt to clean up temporary files even if metadata generation failed
            try:
                if mp4_path:
                    await self._cleanup_temporary_files(mp4_path)
            except Exception as cleanup_error:
                logger.warning(f"Failed to clean up temporary files: {cleanup_error}")

    async def _find_and_validate_mp4(self, output_path: str) -> Optional[str]:
        """Find and validate the MP4 file after remuxing"""
        # Check if MP4 file exists (remuxing completed)
        mp4_path = output_path
        if output_path.endswith(".ts"):
            mp4_path = output_path.replace(".ts", ".mp4")

        # Wait for the MP4 file to exist with a timeout
        start_time = datetime.now()
        while not os.path.exists(mp4_path):
            if (datetime.now() - start_time).total_seconds() > 300:  # 5 minute timeout
                logger.warning(f"Timed out waiting for MP4 file: {mp4_path}")
                return None
            await asyncio.sleep(5)

        # Additional wait time to ensure the file is completely written
        await asyncio.sleep(20)  # Longer wait to ensure file is fully written

        # Verify that the MP4 file is valid
        if mp4_path.endswith(".mp4"):
            # Use the function from ffmpeg_utils module
            from app.utils.ffmpeg_utils import validate_mp4
            is_valid = await validate_mp4(mp4_path)
            
            if not is_valid:
                logger.error(f"MP4 file validation failed: {mp4_path}")
                # No fallback or repair attempts - just fail cleanly
                return None

        return mp4_path

    async def _ensure_stream_ended(self, stream_id: int, force_started: bool):
        """Ensure stream is properly marked as ended and has events"""
        with SessionLocal() as db:
            stream = db.query(Stream).filter(Stream.id == stream_id).first()
            if not stream:
                logger.error(f"Stream {stream_id} not found for metadata generation")
                raise StreamNotFoundError(
                    f"Stream {stream_id} not found for metadata generation"
                )            # Ensure stream is marked as ended
            if force_started or not stream.ended_at:
                stream.ended_at = datetime.now(timezone.utc)
                # stream.status = "offline"  # Remove - status is not a field in the Stream model

                # Check if there are any stream events
                events_count = (
                    db.query(StreamEvent)
                    .filter(StreamEvent.stream_id == stream_id)
                    .count()
                )

                # If no events, add at least one event for the stream's category
                if events_count == 0 and stream.category_name:
                    logger.info(
                        f"No events found for stream {stream_id}, adding initial category event"
                    )

                    # Add an event for the stream's category at stream start time
                    category_event = StreamEvent(
                        stream_id=stream_id,
                        event_type="channel.update",
                        title=stream.title,
                        category_name=stream.category_name,
                        language=stream.language,
                        timestamp=stream.started_at,
                    )
                    db.add(category_event)

                    # And also add the stream.online event
                    start_event = StreamEvent(
                        stream_id=stream_id,
                        event_type="stream.online",
                        title=stream.title,
                        category_name=stream.category_name,
                        language=stream.language,
                        timestamp=stream.started_at
                        + timedelta(seconds=1),  # 1 second after start
                    )
                    db.add(start_event)
                db.commit()
                logger.info(
                    f"Stream {stream_id} marked as ended for metadata generation"
                )

    async def _generate_stream_metadata(self, stream_id: int, mp4_path: str):
        """Generate all metadata for a stream"""
        # Use a new MetadataService instance
        metadata_service = MetadataService()

        try:
            # Generate all metadata in one go
            await metadata_service.generate_metadata_for_stream(stream_id, mp4_path)

            # Wait briefly to allow all chapter files to be written
            await asyncio.sleep(2)

            # Find the FFmpeg chapters file
            ffmpeg_chapters_path = mp4_path.replace(".mp4", "-ffmpeg-chapters.txt")

            # Embed all metadata (including chapters if available) in one step
            if (
                os.path.exists(ffmpeg_chapters_path)
                and os.path.getsize(ffmpeg_chapters_path) > 0
            ):
                logger.info(
                    f"Embedding all metadata and chapters into MP4 file for stream {stream_id}"
                )
                await metadata_service.embed_all_metadata(
                    mp4_path, ffmpeg_chapters_path, stream_id
                )
            else:
                logger.warning(
                    f"FFmpeg chapters file not found or empty: {ffmpeg_chapters_path}"
                )
                logger.info(f"Embedding basic metadata without chapters")
                await metadata_service.embed_all_metadata(mp4_path, "", stream_id)

        finally:
            # Close the metadata session
            await metadata_service.close()

    async def _start_streamlink(
        self, streamer_name: str, quality: str, output_path: str, force_mode: bool = False
    ) -> Optional[asyncio.subprocess.Process]:
        """Start streamlink process for recording with TS format and post-processing to MP4
        
        Args:
            streamer_name: Name of the streamer
            quality: Video quality to record
            output_path: Path where to save the recording
            force_mode: If True, uses more aggressive streamlink settings (only for manual force recording)
                       Not used for automatic EventSub recordings
        """
        try:
            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Get proxy settings from the database
            proxy_settings = get_proxy_settings_from_db()
            
            # Generate streamlink command using our utility function
            cmd = get_streamlink_command(
                streamer_name=streamer_name,
                quality=quality,
                output_path=output_path,
                proxy_settings=proxy_settings,
                force_mode=force_mode
            )
            
            # Define ts_output_path for use in _monitor_process
            ts_output_path = output_path.replace(".mp4", ".ts") if output_path.endswith(".mp4") else output_path

            # Log the command start
            self.streamlink_logger.info(f"[STREAMLINK_START] {streamer_name} - Quality: {quality}")
            self.streamlink_logger.info(f"[STREAMLINK_CMD] {' '.join(cmd)}")
            logging_service.log_streamlink_start(streamer_name, quality, output_path, cmd)

            # Special logging for force mode
            if force_mode:
                logger.info(f"Starting streamlink in FORCE MODE for {streamer_name} with enhanced retry settings")
            
            # Use subprocess manager to start the process
            process_id = f"streamlink_{streamer_name}_{int(datetime.now().timestamp())}"
            process = await self.subprocess_manager.start_process(cmd, process_id)

            if process:
                # Start monitoring the process output in the background
                asyncio.create_task(
                    self._monitor_process(
                        process, process_id, streamer_name, ts_output_path, output_path
                    )
                )

            return process
        except Exception as e:
            logger.error(f"Failed to start streamlink: {e}", exc_info=True)
            return None

    async def _monitor_process(
        self,
        process: asyncio.subprocess.Process,
        process_id: str,
        streamer_name: str,
        ts_path: str,
        mp4_path: str,
    ) -> None:
        """Monitor recording process and convert TS to MP4 when finished"""
        try:
            logging_service.log_recording_activity("PROCESS_MONITORING", streamer_name, "Starting to monitor streamlink process", "debug")
            
            stdout, stderr = await process.communicate()
            exit_code = process.returncode or 0

            # Log the process output
            logging_service.log_streamlink_output(streamer_name, stdout, stderr, exit_code)

            if exit_code == 0 or exit_code == 130:  # 130 is SIGINT (user interruption)
                reason = "completed" if exit_code == 0 else "user_interrupted"
                logging_service.log_recording_activity("STREAMLINK_FINISHED", streamer_name, f"Exit code: {exit_code} ({reason})")
                
                logger.info(
                    f"Streamlink finished for {streamer_name}, converting TS to MP4"
                )
                # Only remux if TS file exists and has content
                if os.path.exists(ts_path) and os.path.getsize(ts_path) > 0:
                    file_size_mb = os.path.getsize(ts_path) / (1024 * 1024)
                    logging_service.log_file_operation("REMUX_START", ts_path, True, f"Starting conversion to MP4", file_size_mb)
                    await self._remux_to_mp4_with_logging(ts_path, mp4_path, streamer_name)
                else:
                    logging_service.log_recording_error(0, streamer_name, "FILE_NOT_FOUND", f"No valid TS file found at {ts_path}")
                    logger.warning(f"No valid TS file found at {ts_path} for remuxing")
            else:
                stderr_text = (
                    stderr.decode("utf-8", errors="ignore")
                    if stderr
                    else "No error output"
                )
                logging_service.log_recording_error(0, streamer_name, "STREAMLINK_FAILED", f"Exit code {exit_code}: {stderr_text}")
                logger.error(
                    f"Streamlink process for {streamer_name} exited with code {exit_code}: {stderr_text}"
                )
                
                # Note: In our new clean approach, we don't attempt to remux partial recordings
                # If streamlink failed, we fail the whole process and don't try to recover partial files
                
            # Remove the process from subprocess manager
            await self.subprocess_manager.terminate_process(process_id)
        except Exception as e:
            logger.error(f"Error monitoring process: {e}", exc_info=True)

    async def _remux_to_mp4_with_logging(self, ts_path: str, mp4_path: str, streamer_name: str) -> bool:
        """Remux TS file to MP4 using the new remux_file method without repair attempts"""
        try:
            logger.info(f"Starting remux of {ts_path} to {mp4_path} using new method")
            
            # Ensure the TS file exists and has content
            if not os.path.exists(ts_path):
                logger.error(f"TS file does not exist: {ts_path}")
                return False
                
            ts_size = os.path.getsize(ts_path)
            if ts_size == 0:
                logger.error(f"TS file is empty: {ts_path}")
                return False
                
            logger.info(f"TS file validation passed: {ts_path}, size: {ts_size} bytes")
            
            # Ensure the output directory exists
            mp4_dir = os.path.dirname(mp4_path)
            os.makedirs(mp4_dir, exist_ok=True)
            
            # Add metadata for the file
            metadata = {
                "encoded_by": "StreamVault",
                "encoding_tool": "StreamVault",
                "streamer": streamer_name,
                "original_format": "TS",
                "remux_date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            }
            
            # Create a temporary metadata file
            meta_path = None
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.txt', mode='w', encoding='utf-8') as f:
                    meta_path = f.name
                    f.write(";FFMETADATA1\n")
                    for key, value in metadata.items():
                        value_escaped = str(value).replace("=", "\\=").replace(";", "\\;").replace("#", "\\#").replace("\\", "\\\\")
                        f.write(f"{key}={value_escaped}\n")
            except Exception as e:
                logger.error(f"Failed to create metadata file: {e}")
            
            # Generate a unique timestamp for this remux operation
            remux_timestamp = int(datetime.now().timestamp())
            self.activity_logger.log_file_operation("REMUX_START", ts_path, True, 
                                                   f"Starting remux to {mp4_path} (Size: {ts_size/1024/1024:.2f} MB)")
            
            # Import the logging service
            from app.services.logging_service import logging_service
            
            # Call the remux_file method with logging service
            result = await self.remux_file(
                input_path=ts_path,
                output_path=mp4_path,
                overwrite=True,
                metadata_file=meta_path,
                streamer_name=streamer_name,
                logging_service=logging_service
            )
            
            # Clean up the temporary metadata file
            if meta_path and os.path.exists(meta_path):
                os.remove(meta_path)
                
            # If remux was successful, validate the MP4 file before deleting the TS file
            if result["success"] and os.path.exists(mp4_path):
                # Step 1: Verify MP4 file has reasonable size (at least 80% of TS size)
                ts_size = os.path.getsize(ts_path) if os.path.exists(ts_path) else 0
                mp4_size = os.path.getsize(mp4_path)
                
                if mp4_size == 0:
                    logger.error(f"MP4 file is empty: {mp4_path}")
                    self.activity_logger.log_file_operation("REMUX_FAILED", mp4_path, False, "Output file is empty")
                    return False
                    
                size_ratio = mp4_size / ts_size if ts_size > 0 else 1
                logger.info(f"Size ratio MP4/TS: {size_ratio:.2f} ({mp4_size}/{ts_size} bytes)")
                
                if size_ratio < 0.8:
                    logger.error(f"MP4 file size ({mp4_size} bytes) is too small compared to TS file ({ts_size} bytes), ratio: {size_ratio:.2f}")
                    self.activity_logger.log_file_operation("REMUX_FAILED", mp4_path, False, 
                                                          f"Output file too small: {mp4_size} bytes, ratio: {size_ratio:.2f}")
                    return False
                
                # Step 2: Verify the MP4 file is valid with ffprobe
                logger.info(f"Validating MP4 file with ffprobe: {mp4_path}")
                valid_mp4 = await self._validate_mp4_with_ffprobe(mp4_path, streamer_name)
                
                if not valid_mp4:
                    logger.error(f"MP4 file validation failed: {mp4_path}")
                    self.activity_logger.log_file_operation("REMUX_FAILED", mp4_path, False, "FFprobe validation failed")
                    return False
                
                # Step 3: Check if the MP4 has a proper duration
                duration_result = await self._check_mp4_duration(mp4_path, ts_path, streamer_name)
                
                if not duration_result["valid"]:
                    logger.error(f"MP4 duration check failed: {duration_result['message']}")
                    self.activity_logger.log_file_operation("REMUX_FAILED", mp4_path, False, duration_result["message"])
                    return False
                
                # Step 4: Additional validation to ensure MP4 is playable (check for mdat atom)
                try:
                    playability_cmd = [
                        "ffprobe", 
                        "-v", "error", 
                        "-show_entries", "format=format_name,duration", 
                        "-of", "json", 
                        mp4_path
                    ]
                    playability_process = await asyncio.create_subprocess_exec(
                        *playability_cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    play_stdout, play_stderr = await playability_process.communicate()
                    if playability_process.returncode != 0 or "Invalid data found" in play_stderr.decode('utf-8', errors='ignore'):
                        logger.error(f"MP4 file playability check failed: {mp4_path}")
                        self.activity_logger.log_file_operation("REMUX_FAILED", mp4_path, False, "MP4 playability check failed")
                        return False
                    
                    # Parse output to confirm it's an MP4 container
                    play_output = play_stdout.decode('utf-8', errors='ignore')
                    if '"format_name"' not in play_output or "mp4" not in play_output.lower():
                        logger.error(f"MP4 container validation failed: {mp4_path}")
                        self.activity_logger.log_file_operation("REMUX_FAILED", mp4_path, False, "Invalid MP4 container format")
                        return False
                        
                    logger.info(f"MP4 playability check passed: {mp4_path}")
                except Exception as e:
                    logger.error(f"Error during MP4 playability check: {e}")
                    # Don't fail the process for this check, as it's an additional safeguard
                
                # All checks passed
                logger.info(f"Successfully remuxed {ts_path} to {mp4_path}")
                self.activity_logger.log_file_operation("REMUX_SUCCESS", mp4_path, True, 
                                                       f"Size: {mp4_size/1024/1024:.2f} MB, Duration: {duration_result['duration']:.2f}s")
                
                # Log successful validation
                logging_service.ffmpeg_logger.info(f"[VALIDATION_SUCCESS] All checks passed for {mp4_path}: " +
                                                  f"Size ratio: {size_ratio:.2f}, Duration: {duration_result['duration']:.2f}s")
                
                # Only delete original TS file if all checks passed
                if os.path.exists(ts_path):
                    logger.info(f"All validation checks passed. Deleting original TS file: {ts_path}")
                    os.remove(ts_path)
                    logging_service.ffmpeg_logger.info(f"[TS_DELETE] Deleted original TS file: {ts_path}")
                    self.activity_logger.log_file_operation("TS_DELETE", ts_path, True, "TS file deleted after successful MP4 validation")
                
                return True
            else:
                error_msg = f"Failed to remux {ts_path} to {mp4_path}: {result.get('stderr', '')}"
                logger.error(error_msg)
                self.activity_logger.log_file_operation("REMUX_FAILED", mp4_path, False, result.get("stderr", "Unknown error"))
                return False
        except Exception as e:
            logger.error(f"Error during remux: {e}", exc_info=True)
            return False
        finally:
            # Clean up the process
            await self.subprocess_manager.terminate_process(
                f"ffmpeg_remux_{int(datetime.now().timestamp())}"
            )

    async def remux_file(self, input_path: str, output_path: str, overwrite: bool = False, metadata_file: Optional[str] = None, streamer_name: str = "unknown", logging_service=None) -> Dict[str, Any]:
        """Remux file with proper error handling and AAC bitstream conversion"""
        try:
            # Create output directory if it doesn't exist
            output_dir = os.path.dirname(output_path)
            os.makedirs(output_dir, exist_ok=True)
            
            # Set proper permissions on the directory to ensure we can write files
            os.chmod(output_dir, 0o755)
            
            # Delete existing output file if overwrite is True
            if os.path.exists(output_path) and overwrite:
                os.remove(output_path)
            
            # Base FFmpeg command with enhanced stability parameters
            cmd = [
                "ffmpeg",
                "-fflags", "+genpts+igndts+ignidx+discardcorrupt",
                "-err_detect", "ignore_err",
                "-analyzeduration", "50M",
                "-probesize", "50M",
                "-i", input_path,
                "-c:v", "copy",
                "-c:a", "copy",
                # AAC bitstream filter is crucial for Twitch streams
                "-bsf:a", "aac_adtstoasc",
                "-avoid_negative_ts", "make_zero",
                "-map", "0:v:0?",
                "-map", "0:a:0?",
                "-movflags", "+faststart+empty_moov+frag_keyframe",
                "-ignore_unknown",
                "-max_muxing_queue_size", "16384",
                "-max_interleave_delta", "0",
                "-fflags", "+discardcorrupt",
                "-async", "0",
                "-fps_mode", "passthrough",  # Modern replacement for -vsync
                "-metadata", f"encoded_by=StreamVault",
                "-metadata", f"encoding_tool=StreamVault",
                "-y", output_path,
                # Add reporting options for better logging
                "-report",
                "-v", "info",
                "-stats_period", "30"
            ]
            
            # Add metadata file if provided
            if metadata_file and os.path.exists(metadata_file):
                cmd.insert(cmd.index("-i"), "-i")
                cmd.insert(cmd.index("-i") + 1, metadata_file)
                cmd.insert(cmd.index("-map", 1) + 2, "-map_metadata")
                cmd.insert(cmd.index("-map_metadata") + 1, "1")
            
            # Log file path for debugging
            log_file = f"/app/logs/ffmpeg/remux_{streamer_name}_{datetime.now().strftime('%Y-%m-%d')}.log"
            logger.info(f"Command: {' '.join(cmd)}")
            if logging_service:
                logging_service.recording_logger.info(f"[REMUX_COMMAND] {streamer_name} - Command: {' '.join(cmd)}")
            
            # Start FFmpeg process
            process_id = f"ffmpeg_remux_{int(datetime.now().timestamp())}"
            process = await self.subprocess_manager.start_process(cmd, process_id)
            
            # Wait for process to complete
            stdout, stderr = await process.communicate()
            exit_code = process.returncode
            
            # Get file sizes for metrics
            input_size_mb = os.path.getsize(input_path) / (1024 * 1024) if os.path.exists(input_path) else 0
            output_size_mb = os.path.getsize(output_path) / (1024 * 1024) if os.path.exists(output_path) else 0
            
            # Log detailed performance metrics
            metrics = {
                "exit_code": exit_code,
                "input_size_mb": round(input_size_mb, 2),
                "output_size_mb": round(output_size_mb, 2),
                "compression_ratio": round(1 - (output_size_mb / input_size_mb), 3) if input_size_mb > 0 else 0,
            }
            
            # Check if output file exists and has content
            success = exit_code == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0
            
            # Additional check for truncated files
            if success and input_size_mb > 0 and output_size_mb < input_size_mb * 0.8:
                logger.error(f"FILE_SIZE_MISMATCH: MP4 size ({output_size_mb:.2f} MB) is significantly smaller than TS size ({input_size_mb:.2f} MB)")
                if logging_service:
                    logging_service.recording_logger.error(f"[REMUX_ERROR] {streamer_name} - FILE_SIZE_MISMATCH: MP4 size ({output_size_mb:.2f} MB) is significantly smaller than TS size ({input_size_mb:.2f} MB)")
                success = False
            
            # Log outcome
            operation = "REMUX_SUCCESS" if success else "REMUX_FAILURE"
            logger.info(f"{operation}: {output_path} - Remux {'completed successfully' if success else 'failed'}")
            if logging_service:
                logging_service.recording_logger.info(f"[{operation}] {streamer_name} - {output_path} - Size: {output_size_mb:.2f} MB")
            
            return {
                "success": success,
                "exit_code": exit_code,
                "stdout": stdout.decode("utf-8", errors="ignore") if stdout else "",
                "stderr": stderr.decode("utf-8", errors="ignore") if stderr else "",
                "metrics": metrics
            }
        except Exception as e:
            logger.error(f"Exception during remux operation: {e}", exc_info=True)
            return {
                "success": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": str(e),
                "metrics": {}
            }
    
    async def cleanup(self):
        """Clean up all resources when shutting down"""

        try:
            # Stop all active recordings
            streamer_ids = list(self.active_recordings.keys())
            for streamer_id in streamer_ids:
                await self.stop_recording(streamer_id)

            # Clean up all subprocess manager processes
            await self.subprocess_manager.cleanup_all()

            # Close metadata service
            await self.metadata_service.close()
            
            # Close media server structure service
            if hasattr(self, 'media_server_service'):
                await self.media_server_service.close()
                
            logger.info("Recording service cleanup completed")

        except Exception as e:
            logger.error(f"Error during recording service cleanup: {e}", exc_info=True)

    async def _cleanup_temporary_files(self, mp4_path: str):
        """Clean up temporary files after successful metadata generation"""
        # Use the function from file_utils module
        from app.utils.file_utils import cleanup_temporary_files
        await cleanup_temporary_files(mp4_path)

    async def _update_recording_path(self, stream_id: int, new_path: str):
        """Update the recording path for a stream after media server structure creation"""
        from app.utils.path_utils import update_recording_path
        await update_recording_path(stream_id, new_path)

    def _generate_filename(
        self, streamer: Streamer, stream_data: Dict[str, Any], template: str
    ) -> str:
        """Generate a filename from template with variables"""
        from app.utils.path_utils import generate_filename
        return generate_filename(
            streamer=streamer, 
            stream_data=stream_data, 
            template=template,
            sanitize_func=self._sanitize_filename
        )

    def _get_episode_number(self, streamer_id: int, now: datetime) -> str:
        """Get episode number (count of streams in current month)"""
        from app.utils.path_utils import get_episode_number
        return get_episode_number(streamer_id, now)

    def _sanitize_filename(self, name: str) -> str:
        """Remove illegal characters from filename"""
        from app.utils.file_utils import sanitize_filename
        return sanitize_filename(name)

    async def _validate_mp4_with_ffprobe(self, mp4_path: str, streamer_name: str) -> bool:
        """Validate the MP4 file using ffprobe to ensure it's not corrupted.
        
        Args:
            mp4_path: Path to the MP4 file
            streamer_name: Name of the streamer for logging
            
        Returns:
            bool: True if the MP4 file is valid, False otherwise
        """
        # First, check if the file exists to avoid creating logs for non-existent files
        if not os.path.isfile(mp4_path):
            logger.warning(f"Cannot validate MP4: File does not exist: {mp4_path}")
            return False
            
        try:
            # Import logging service if needed
            from app.services.logging_service import logging_service
            
            # Build ffprobe command
            cmd = [
                "ffprobe",
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=codec_name,width,height,duration",
                "-of", "json",
                mp4_path
            ]
            
            # Log the command
            logger.debug(f"Running ffprobe validation: {' '.join(cmd)}")
            self.activity_logger.log_process_monitoring(streamer_name, "FFPROBE_START", f"Validating {mp4_path}")
            
            # Create unique log file for this validation
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            # Make sure we have a valid streamer name
            if not streamer_name or streamer_name.lower() == "none":
                streamer_name = "unknown"
            ffprobe_log_path = logging_service.get_ffmpeg_log_path(f"validate_{timestamp_str}", streamer_name)
            
            # Set environment for logging
            env = os.environ.copy()
            if ffprobe_log_path:
                env["FFREPORT"] = f"file={ffprobe_log_path}:level=32"
            
            # Create temporary files for stdout/stderr to avoid container logs
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, prefix="ffprobe_stdout_", suffix=".log") as stdout_file, \
                 tempfile.NamedTemporaryFile(delete=False, prefix="ffprobe_stderr_", suffix=".log") as stderr_file:
                
                # Set additional environment variables to suppress console output
                env["AV_LOG_FORCE_NOCOLOR"] = "1"  # Disable ANSI color in logs
                env["AV_LOG_FORCE_STDERR"] = "0"   # Don't force stderr output
                
                # Add quiet loglevel to prevent container logs
                cmd = [cmd[0]] + ["-loglevel", "quiet"] + cmd[1:]
                
                # Run ffprobe with redirected output
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=stdout_file.fileno(),
                    stderr=stderr_file.fileno(),
                    env=env
                )
                
                # Wait for process to complete
                await process.wait()
                exit_code = process.returncode or 0
                
                # Read output from temporary files
                with open(stdout_file.name, 'r', errors='ignore') as f:
                    stdout_str = f.read()
                with open(stderr_file.name, 'r', errors='ignore') as f:
                    stderr_str = f.read()
                
                # Append output to log file
                if ffprobe_log_path:
                    with open(ffprobe_log_path, 'a', errors='ignore') as f:
                        f.write("\n\n--- STDOUT ---\n")
                        f.write(stdout_str)
                        f.write("\n\n--- STDERR ---\n")
                        f.write(stderr_str)
                
                # Clean up temporary files
                try:
                    os.unlink(stdout_file.name)
                    os.unlink(stderr_file.name)
                except Exception as e:
                    logger.warning(f"Failed to clean up temporary ffprobe files: {e}")
            
            # Log results
            if exit_code == 0 and stdout_str and len(stdout_str.strip()) > 10:  # Ensure we got meaningful output
                try:
                    # Parse JSON output
                    import json
                    data = json.loads(stdout_str)
                    
                    # Check for video stream
                    if "streams" in data and len(data["streams"]) > 0:
                        stream = data["streams"][0]
                        codec = stream.get("codec_name", "unknown")
                        width = stream.get("width", 0)
                        height = stream.get("height", 0)
                        
                        logger.info(f"MP4 validation passed: {mp4_path}, codec: {codec}, resolution: {width}x{height}")
                        self.activity_logger.log_process_monitoring(
                            streamer_name, 
                            "FFPROBE_SUCCESS", 
                            f"Codec: {codec}, Resolution: {width}x{height}"
                        )
                        return True
                    else:
                        logger.error(f"No video streams found in {mp4_path}")
                        self.activity_logger.log_process_monitoring(streamer_name, "FFPROBE_FAILED", "No video streams found")
                        return False
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse ffprobe output as JSON: {stdout_str}")
                    self.activity_logger.log_process_monitoring(streamer_name, "FFPROBE_FAILED", "Invalid JSON output")
                    return False
            else:
                logger.error(f"ffprobe validation failed with exit code {exit_code}: {stderr_str}")
                self.activity_logger.log_process_monitoring(
                    streamer_name, 
                    "FFPROBE_FAILED", 
                    f"Exit code: {exit_code}, Error: {stderr_str}"
                )
                return False
        except Exception as e:
            logger.error(f"Error validating MP4 with ffprobe: {e}", exc_info=True)
            self.activity_logger.log_process_monitoring(streamer_name, "FFPROBE_ERROR", str(e))
            return False
            
    async def _check_mp4_duration(self, mp4_path: str, ts_path: str, streamer_name: str) -> Dict[str, Any]:
        """Check if the MP4 file has a reasonable duration.
        
        Args:
            mp4_path: Path to the MP4 file
            ts_path: Path to the original TS file
            streamer_name: Name of the streamer for logging
            
        Returns:
            Dict with keys: valid (bool), duration (float), message (str)
        """
        try:
            # Get MP4 duration
            mp4_duration = await self._get_media_duration(mp4_path)
            
            # Also check TS duration if possible
            ts_duration = await self._get_media_duration(ts_path) if os.path.exists(ts_path) else None
            
            if mp4_duration is None:
                return {
                    "valid": False,
                    "duration": 0,
                    "message": f"Could not determine MP4 duration for {mp4_path}"
                }
            
            # If we have both durations, compare them
            if ts_duration and ts_duration > 0:
                # Check if proxy is enabled to determine tolerance
                proxy_settings = get_proxy_settings_from_db()
                proxy_enabled = bool(proxy_settings and (proxy_settings.get("http") or proxy_settings.get("https")))
                
                # Use different thresholds based on proxy status and stream length
                if proxy_enabled:
                    # With proxy, we expect fewer discontinuities - be more strict
                    min_ratio = 0.90 if ts_duration < 3600 else 0.85  # 90% for short streams, 85% for long streams
                else:
                    # Without proxy, expect more ad segments causing discontinuities - be more lenient
                    min_ratio = 0.60 if ts_duration < 3600 else 0.50  # 60% for short streams, 50% for long streams
                    
                ratio = mp4_duration / ts_duration
                
                if ratio < min_ratio:
                    # Only fail for extreme cases where most content is lost
                    if ratio < 0.30:  # Fail if we lost more than 70% of content
                        return {
                            "valid": False,
                            "duration": mp4_duration,
                            "message": f"MP4 duration ({mp4_duration:.2f}s) is significantly shorter than TS duration ({ts_duration:.2f}s), ratio: {ratio:.2f}"
                        }
                    else:
                        # For less extreme cases, log a warning but still pass validation
                        proxy_status = "with proxy" if proxy_enabled else "without proxy (ads expected)"
                        logger.warning(f"MP4 shorter than TS ({proxy_status}): MP4={mp4_duration:.2f}s, TS={ts_duration:.2f}s, ratio={ratio:.2f}")
            
            # If the duration is too short (less than 10 seconds), it's probably not a valid recording
            if mp4_duration < 10:
                return {
                    "valid": False,
                    "duration": mp4_duration,
                    "message": f"MP4 duration is too short: {mp4_duration:.2f}s"
                }
                
            logger.info(f"MP4 duration check passed: {mp4_duration:.2f}s")
            
            # Format the TS duration message properly with conditional
            ts_duration_msg = f"{ts_duration:.2f}s" if ts_duration is not None else "unknown"
            self.activity_logger.log_process_monitoring(
                streamer_name, 
                "DURATION_CHECK_SUCCESS", 
                f"MP4: {mp4_duration:.2f}s, TS: {ts_duration_msg}"
            )
            
            return {
                "valid": True,
                "duration": mp4_duration,
                "message": "Duration check passed"
            }
        except Exception as e:
            logger.error(f"Error checking MP4 duration: {e}", exc_info=True)
            return {
                "valid": False,
                "duration": 0,
                "message": f"Error checking duration: {str(e)}"
            }
            
    async def _get_media_duration(self, file_path: str) -> Optional[float]:
        """Get the duration of a media file using ffprobe.
        
        Args:
            file_path: Path to the media file
            
        Returns:
            Optional[float]: Duration in seconds, or None if it couldn't be determined
        """
        # First check if file exists to avoid creating logs for non-existent files
        if not os.path.isfile(file_path):
            logger.warning(f"Cannot get duration: File does not exist: {file_path}")
            return None
            
        try:
            # Extract streamer name from path if possible, fallback to system
            path_parts = file_path.split(os.sep)
            streamer_name = "system"
            for part in path_parts:
                if part and not part.startswith(".") and os.path.isdir(os.path.join("/", part)):
                    streamer_name = part
                    break
                    
            # Get a unique log file path for this ffprobe operation
            from app.services.logging_service import LoggingService
            log_service = LoggingService()
            log_path = log_service.get_ffmpeg_log_path(
                f"ffprobe_duration",
                streamer_name
            )
            
            # Ensure the log directory exists
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            
            cmd = [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                file_path
            ]
            
            with open(log_path, "a") as log_file:
                log_file.write(f"=== Duration check for {file_path} ===\n")
                log_file.write(f"Command: {' '.join(cmd)}\n")
                
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await process.communicate()
                stdout_str = stdout.decode('utf-8', errors='ignore') if stdout else ""
                stderr_str = stderr.decode('utf-8', errors='ignore') if stderr else ""
                
                # Log all output to the file
                if stdout_str:
                    log_file.write(f"STDOUT:\n{stdout_str}\n")
                if stderr_str:
                    log_file.write(f"STDERR:\n{stderr_str}\n")
                
                if process.returncode == 0 and stdout_str.strip():
                    try:
                        duration = float(stdout_str.strip())
                        log_file.write(f"SUCCESS: Duration = {duration} seconds\n")
                        return duration
                    except ValueError:
                        log_file.write(f"ERROR: Could not parse duration: {stdout_str}\n")
                        logger.error(f"Could not parse duration from ffprobe output: {stdout_str}")
                        return None
                else:
                    log_file.write(f"ERROR: ffprobe failed with return code {process.returncode}\n")
                    logger.error(f"ffprobe failed to get duration: {stderr_str}")
                    return None
        except Exception as e:
            logger.error(f"Error getting media duration: {e}")
            return None
