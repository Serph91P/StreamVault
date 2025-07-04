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
                # Try using TS file directly if MP4 wasn't created
                if os.path.exists(output_path) and output_path.endswith(".ts"):
                    mp4_path = output_path
                    logger.info(f"Using TS file directly for metadata: {mp4_path}")
                    break
                return None
            await asyncio.sleep(5)

        # Additional wait time to ensure the file is completely written
        await asyncio.sleep(20)  # Longer wait to ensure file is fully written

        # Verify that the MP4 file is valid
        if mp4_path.endswith(".mp4"):
            is_valid = await self._validate_mp4(mp4_path)
            if not is_valid:
                logger.warning(f"MP4 file is not valid, attempting repair: {mp4_path}")
                repaired = await self._repair_mp4(
                    (
                        output_path.replace(".mp4", ".ts")
                        if os.path.exists(output_path.replace(".mp4", ".ts"))
                        else output_path
                    ),
                    mp4_path,
                )
                if not repaired:
                    logger.error(f"Could not repair MP4 file: {mp4_path}")
                    return None

                # Wait after repair
                await asyncio.sleep(5)

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
            force_mode: If True, uses more aggressive settings (longer timeouts, more retries)
                       Only used for manual force recording, not for automatic EventSub recordings
        """
        try:
            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Use .ts as intermediate format for better recovery
            ts_output_path = output_path.replace(".mp4", ".ts")

            # Use the quality setting as specified by the user
            adjusted_quality = quality

            # Get streamlink log path for this recording session
            streamlink_log_path = logging_service.get_streamlink_log_path(streamer_name)
            
            # Streamlink command with enhanced proxy stability parameters from LiveStreamDVR
            cmd = [
                "streamlink",
                f"twitch.tv/{streamer_name}",
                adjusted_quality,
                "-o",
                ts_output_path,
                "--twitch-disable-ads",
                "--hls-live-restart",
                "--hls-live-edge", "6",  # Start closer to live edge for better proxy stability
                "--stream-segment-threads", "5",  # Multi-threading helps with proxy connections
                "--ffmpeg-fout", "mpegts",  # Use mpegts format for better container handling
                # Preserve existing timeout parameters with enhanced values for proxy usage
                "--stream-segment-timeout", "30" if not force_mode else "45",
                "--stream-timeout", "180" if not force_mode else "240", 
                "--stream-segment-attempts", "8" if not force_mode else "12",
                "--retry-streams", "10",  # More retries for proxy stability
                "--retry-max", "5",
                "--retry-open", "5" if not force_mode else "8",
                # Buffer management for proxy connections
                "--ringbuffer-size", "256M",
                "--hls-segment-queue-threshold", "5",
                "--force",
                # Logging parameters
                "--loglevel", "debug",
                "--logfile", streamlink_log_path,
                "--logformat", "[{asctime}][{name}][{levelname}] {message}",
                "--logdateformat", "%Y-%m-%d %H:%M:%S",
            ]            # Add proxy settings if configured
            from app.models import GlobalSettings
            with SessionLocal() as proxy_db:
                global_settings = proxy_db.query(GlobalSettings).first()
                if global_settings:
                    if global_settings.http_proxy and global_settings.http_proxy.strip():
                        proxy_url = global_settings.http_proxy.strip()
                        # Validate that the proxy URL has the correct protocol prefix
                        if not proxy_url.startswith(('http://', 'https://')):
                            error_msg = f"HTTP proxy URL must start with 'http://' or 'https://'. Current value: {proxy_url}"
                            logger.error(f"[RECORDING_ERROR] {streamer_name} - PROXY_VALIDATION_FAILED: {error_msg}")
                            raise ValueError(error_msg)
                        cmd.extend(["--http-proxy", proxy_url])
                        logger.debug(f"Using HTTP proxy: {proxy_url}")
                          # Add proxy-specific optimizations for better audio sync
                        cmd.extend([
                            "--stream-segment-timeout", "60" if not force_mode else "90",  # Longer timeouts for proxy latency
                            "--stream-timeout", "300" if not force_mode else "360",       # Extended overall timeout
                            "--hls-segment-queue-threshold", "8",                         # More segments for proxy buffering
                            "--stream-segment-attempts", "15" if not force_mode else "20", # More retry attempts
                            "--hls-live-edge", "10",                                      # Stay further from live edge to avoid sync issues
                            "--ringbuffer-size", "512M",                                 # Larger internal buffer for stable data flow
                            "--hls-segment-stream-data",                                  # Write segment data immediately to reduce buffering delays
                            "--stream-segment-threads", "2",                             # Use multiple threads for segment downloads
                            "--hls-playlist-reload-time", "segment",                     # Optimize playlist reload timing
                        ])
                        
                    if global_settings.https_proxy and global_settings.https_proxy.strip():
                        proxy_url = global_settings.https_proxy.strip()
                        # Validate that the proxy URL has the correct protocol prefix
                        if not proxy_url.startswith(('http://', 'https://')):
                            error_msg = f"HTTPS proxy URL must start with 'http://' or 'https://'. Current value: {proxy_url}"
                            logger.error(f"[RECORDING_ERROR] {streamer_name} - PROXY_VALIDATION_FAILED: {error_msg}")
                            raise ValueError(error_msg)
                        cmd.extend(["--https-proxy", proxy_url])
                        logger.debug(f"Using HTTPS proxy: {proxy_url}")
                        
                        # Add proxy-specific optimizations for HTTPS connections too
                        cmd.extend([
                            "--stream-segment-timeout", "60" if not force_mode else "90",
                            "--stream-timeout", "300" if not force_mode else "360",
                            "--hls-segment-queue-threshold", "8",
                            "--stream-segment-attempts", "15" if not force_mode else "20",
                            "--hls-live-edge", "10",
                            "--ringbuffer-size", "512M",
                        ])

            # Log the command start
            self.streamlink_logger.info(f"[STREAMLINK_START] {streamer_name} - Quality: {quality}")
            self.streamlink_logger.info(f"[STREAMLINK_CMD] {' '.join(cmd)}")
            logging_service.log_streamlink_start(streamer_name, quality, output_path, cmd)

            logger.debug(f"Starting streamlink: {' '.join(cmd)}")

            # Special logging for force mode
            if force_mode:
                logger.info(f"Starting streamlink in FORCE MODE for {streamer_name} with enhanced retry settings")
                logger.info(f"Force mode uses longer timeouts and more retry attempts to increase success chance")
                
            # Log the command being executed for debugging
            logger.debug(f"Executing streamlink command: {' '.join(cmd)}")

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
                # Try to remux anyway if file exists, it might be partially usable
                if (
                    os.path.exists(ts_path) and os.path.getsize(ts_path) > 1000000
                ):  # At least 1MB
                    logging_service.log_recording_activity("PARTIAL_RECOVERY", streamer_name, "Attempting to recover partial recording")
                    logger.info(
                        f"Attempting to remux partial recording for {streamer_name}"
                    )
                    await self._remux_to_mp4_with_logging(ts_path, mp4_path, streamer_name)            # Remove the process from subprocess manager
            await self.subprocess_manager.terminate_process(process_id)
        except Exception as e:
            logger.error(f"Error monitoring process: {e}", exc_info=True)

    async def _remux_to_mp4_with_logging(self, ts_path: str, mp4_path: str, streamer_name: str) -> bool:
        """Remux TS file to MP4 with enhanced logging and sync preservation"""
        try:
            # Check if the recording was made through a proxy by looking at active recording info
            is_proxy_recording = False
            from app.models import GlobalSettings
            with SessionLocal() as proxy_db:
                global_settings = proxy_db.query(GlobalSettings).first()
                if global_settings and (global_settings.http_proxy or global_settings.https_proxy):
                    is_proxy_recording = True
            
            # Enhanced remux settings optimized for problematic TS files from proxy recordings
            cmd = [
                "ffmpeg",
                # Input handling - be more tolerant of corrupted/problematic streams
                "-fflags", "+genpts+igndts+ignidx+discardcorrupt",  # Discard corrupt packets
                "-err_detect", "ignore_err",          # Ignore decoding errors
                "-analyzeduration", "50M" if is_proxy_recording else "20M",     # Analyze much more data
                "-probesize", "50M" if is_proxy_recording else "20M",          # Probe much more data
                "-i", ts_path,
                
                # Output settings - preserve everything possible
                "-c:v", "copy",               # Copy video stream (no re-encoding)
                "-c:a", "copy",               # Copy audio stream (preserve original timing)
                "-bsf:a", "aac_adtstoasc",    # Fix AAC bitstream format for MP4 container
                "-avoid_negative_ts", "make_zero",    # Handle negative timestamps
                "-map", "0:v:0?",             # Map first video stream (optional)
                "-map", "0:a:0?",             # Map first audio stream (optional)
                
                # Container and muxing settings for problematic streams
                "-movflags", "+faststart+empty_moov+frag_keyframe" if is_proxy_recording else "+faststart",
                "-ignore_unknown",            # Ignore unknown streams
                "-max_muxing_queue_size", "16384" if is_proxy_recording else "8192",  # Much larger queue
                "-max_interleave_delta", "0", # Allow unlimited interleaving delay
                "-fflags", "+discardcorrupt", # Discard corrupt packets at container level too
                
                # Sync and timing - be more lenient
                "-async", "1" if not is_proxy_recording else "0",  # No audio sync correction for proxy recordings
                "-fps_mode", "passthrough" if is_proxy_recording else "cfr",  # Replace deprecated -vsync
                
                # Metadata and output
                "-metadata", "encoded_by=StreamVault",
                "-metadata", "encoding_tool=StreamVault",
                "-y", mp4_path,
            ]

            # Get FFmpeg log path for this operation
            ffmpeg_log_path = logging_service.get_ffmpeg_log_path("remux", streamer_name)
            
            # Add logging to FFmpeg command
            cmd.extend([
                "-report",
                "-v", "info",  # Use info level instead of verbose to reduce log spam
                "-stats_period", "30"  # Update stats every 30 seconds
            ])
            
            # Set environment variable for FFmpeg report
            env = os.environ.copy()
            env["FFREPORT"] = f"file={ffmpeg_log_path}:level=32"

            # Ensure output directory has correct permissions
            output_dir = os.path.dirname(mp4_path)
            if not os.path.exists(output_dir):
                os.makedirs(output_dir, mode=0o755, exist_ok=True)
            
            # Remove any existing partial MP4 file
            if os.path.exists(mp4_path):
                try:
                    os.remove(mp4_path)
                except OSError as e:
                    logger.warning(f"Could not remove existing MP4 file {mp4_path}: {e}")

            # Log the command start
            self.ffmpeg_logger.info(f"[FFMPEG_REMUX_START] {streamer_name} - {ts_path} -> {mp4_path}")
            self.ffmpeg_logger.info(f"[FFMPEG_CMD] {' '.join(cmd)}")
            logging_service.log_ffmpeg_start("remux", cmd, streamer_name)

            logger.info(f"Starting enhanced FFmpeg remux for {streamer_name}: {ts_path} -> {mp4_path}")
            if is_proxy_recording:
                logger.info(f"Using proxy-optimized remux settings for {streamer_name}")

            # Start process with custom environment and timeout
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )

            # Monitor the remux process with timeout (max 6 hours for very long recordings)
            max_remux_time = 21600  # 6 hours
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), 
                    timeout=max_remux_time
                )
                exit_code = process.returncode or 0
            except asyncio.TimeoutError:
                logger.error(f"FFmpeg remux timed out after {max_remux_time} seconds for {streamer_name}")
                process.kill()
                await process.wait()
                return await self._remux_to_mp4_fallback(ts_path, mp4_path)

            # Log the process output
            logging_service.log_ffmpeg_output("remux", stdout, stderr, exit_code, streamer_name)

            if exit_code == 0:
                logger.info(f"Successfully remuxed {ts_path} to {mp4_path}")

                # Verify that the MP4 file was correctly created and has reasonable size
                if os.path.exists(mp4_path) and os.path.getsize(mp4_path) > 0:
                    mp4_size_mb = os.path.getsize(mp4_path) / (1024 * 1024)
                    ts_size_mb = os.path.getsize(ts_path) / (1024 * 1024) if os.path.exists(ts_path) else 0
                    
                    # Check if MP4 is significantly smaller than TS (might indicate incomplete remux)
                    if ts_size_mb > 0 and mp4_size_mb < (ts_size_mb * 0.7):  # Less than 70% of original
                        logger.warning(f"MP4 file ({mp4_size_mb:.1f} MB) is significantly smaller than TS file ({ts_size_mb:.1f} MB) - possible incomplete remux")
                        # Try fallback method
                        return await self._remux_to_mp4_fallback(ts_path, mp4_path)
                    
                    # Check if the moov atom is present
                    is_valid = await self._validate_mp4(mp4_path)

                    if is_valid:
                        logging_service.log_file_operation("REMUX_SUCCESS", mp4_path, True, f"Remux completed successfully", mp4_size_mb)
                        logger.info(f"Remux completed: {mp4_path} ({mp4_size_mb:.1f} MB)")
                        # Delete TS file after successful conversion to save space
                        if os.path.exists(ts_path):
                            os.remove(ts_path)
                        return True
                    else:
                        logger.warning(f"MP4 validation failed, attempting repair")
                        repair_success = await self._repair_mp4(ts_path, mp4_path)
                        if repair_success:
                            # Only delete TS file after successful repair
                            if os.path.exists(ts_path):
                                os.remove(ts_path)
                        return repair_success
                else:
                    logger.error(f"MP4 file was not created or is empty: {mp4_path}")
                    return await self._remux_to_mp4_fallback(ts_path, mp4_path)
            else:
                logger.error(f"FFmpeg remux failed with exit code {exit_code}")
                stderr_text = stderr.decode("utf-8", errors="ignore") if stderr else "No error output"
                logger.error(f"FFmpeg stderr: {stderr_text[:1000]}...")  # Log first 1000 chars of stderr
                
                # Check for specific error patterns
                if "Operation not permitted" in stderr_text:
                    logger.warning("Detected 'Operation not permitted' error - trying with different approach")
                    # Wait a moment and retry with fallback
                    await asyncio.sleep(2)
                elif "Malformed AAC bitstream" in stderr_text:
                    logger.warning("Detected malformed AAC bitstream - fallback should handle this")
                
                # Try with fallback method if the first attempt failed
                return await self._remux_to_mp4_fallback(ts_path, mp4_path)
                
        except Exception as e:
            logger.error(f"Error during remux: {e}", exc_info=True)
            return False

    async def _remux_to_mp4(self, ts_path: str, mp4_path: str, streamer_name: str = "unknown") -> bool:
        """Remux TS file to MP4 without re-encoding to preserve quality"""
        try:
            # Enhanced remux settings with guaranteed working audio handling
            cmd = [
                "ffmpeg",
                "-fflags",
                "+genpts",  # Generate presentation timestamps
                "-i",
                ts_path,
                "-c:v",
                "copy",  # Copy video stream
                "-c:a",
                "aac",  # WICHTIGE ÄNDERUNG: Re-encode audio to AAC
                "-b:a",
                "160k",  # Definierter Bitrate für Audio
                "-map",
                "0:v:0?",  # Ersten Video-Stream (optional - wichtig für Audio-Only Streams)
                "-map",
                "0:a:0?",  # Ersten Audio-Stream (optional)
                "-ignore_unknown",
                "-movflags",
                "+faststart",
                "-metadata",
                "encoded_by=StreamVault",
                "-metadata",
                "encoding_tool=StreamVault",
                "-y",
                mp4_path,
            ]

            logger.debug(f"Starting enhanced FFmpeg remux: {' '.join(cmd)}")

            # Use subprocess manager for the remux process
            process_id = f"ffmpeg_remux_{int(datetime.now().timestamp())}"
            process = await self.subprocess_manager.start_process(cmd, process_id)

            if not process:
                logger.error(f"Failed to start FFmpeg remux process")
                return False

            stdout, stderr = await process.communicate()
            exit_code = process.returncode or 0

            # Log the process output
            logging_service.log_ffmpeg_output("remux", stdout, stderr, exit_code, streamer_name)

            if exit_code == 0:
                logger.info(f"Successfully remuxed {ts_path} to {mp4_path}")

                # Verify that the MP4 file was correctly created
                if os.path.exists(mp4_path) and os.path.getsize(mp4_path) > 0:
                    # Check if the moov atom is present
                    is_valid = await self._validate_mp4(mp4_path)

                    if is_valid:
                        # Delete TS file after successful conversion to save space
                        if os.path.exists(ts_path):
                            os.remove(ts_path)
                        return True
                    else:
                        logger.warning(f"MP4 validation failed, attempting repair")
                        repair_success = await self._repair_mp4(ts_path, mp4_path)
                        if repair_success:
                            # Only delete TS file after successful repair
                            if os.path.exists(ts_path):
                                os.remove(ts_path)
                        return repair_success
                else:
                    logger.error(f"MP4 file not created or empty: {mp4_path}")
                    return False
            else:
                stderr_text = (
                    stderr.decode("utf-8", errors="ignore")
                    if stderr
                    else "No error output"
                )
                logger.error(
                    f"FFmpeg remux failed with code {process.returncode}: {stderr_text}"
                )

                # Try with fallback method if the first attempt failed
                return await self._remux_to_mp4_fallback(ts_path, mp4_path)
        except Exception as e:
            logger.error(f"Error during remux: {e}", exc_info=True)
            return False
        finally:
            # Clean up the process
            await self.subprocess_manager.terminate_process(
                f"ffmpeg_remux_{int(datetime.now().timestamp())}"
            )

    async def _remux_to_mp4_fallback(self, ts_path: str, mp4_path: str) -> bool:
        """Fallback remux method with more aggressive recovery settings"""
        try:
            logger.info(f"Attempting fallback remux for {ts_path}")
            
            # Use even more aggressive settings for problematic files
            cmd = [
                "ffmpeg",
                # Very tolerant input handling
                "-fflags", "+genpts+igndts+ignidx+discardcorrupt+nobuffer",
                "-err_detect", "ignore_err",
                "-analyzeduration", "100M",  # Analyze even more data
                "-probesize", "100M",       # Probe even more data
                "-thread_queue_size", "8192",  # Larger thread queue
                "-i", ts_path,
                
                # Safe output settings
                "-c:v", "copy",
                "-c:a", "copy", 
                "-bsf:a", "aac_adtstoasc",  # Fix AAC bitstream format
                "-avoid_negative_ts", "make_zero",
                "-map", "0:v:0?",
                "-map", "0:a:0?",
                
                # Very lenient container settings
                "-movflags", "+faststart+empty_moov+separate_moof",
                "-ignore_unknown",
                "-max_muxing_queue_size", "32768",  # Very large queue
                "-max_interleave_delta", "0",
                "-fflags", "+discardcorrupt",
                
                # No sync correction - just copy everything as-is
                "-fps_mode", "passthrough",  # Replace deprecated -vsync
                "-async", "0",  # No audio sync correction
                "-copyts",      # Copy timestamps exactly
                
                "-metadata", "encoded_by=StreamVault_Fallback",
                "-y", mp4_path,
                "-v", "warning"  # Less verbose output
            ]
            
            logger.info(f"Running fallback remux: {' '.join(cmd[:10])}...")
            
            # Run with longer timeout for fallback
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), 
                    timeout=28800  # 8 hours for fallback
                )
                exit_code = process.returncode or 0
            except asyncio.TimeoutError:
                logger.error(f"Fallback remux also timed out for {ts_path}")
                process.kill()
                await process.wait()
                return False
            
            if exit_code == 0 and os.path.exists(mp4_path) and os.path.getsize(mp4_path) > 0:
                mp4_size_mb = os.path.getsize(mp4_path) / (1024 * 1024)
                logger.info(f"Fallback remux successful: {mp4_path} ({mp4_size_mb:.1f} MB)")
                
                # Delete TS file after successful fallback conversion
                if os.path.exists(ts_path):
                    os.remove(ts_path)
                return True
            else:
                stderr_text = stderr.decode("utf-8", errors="ignore") if stderr else "No error output"
                logger.error(f"Fallback remux failed with exit code {exit_code}: {stderr_text[:500]}...")
                
                # If fallback also fails, try the two-step process
                return await self._remux_to_mp4_two_step(ts_path, mp4_path)
                
        except Exception as e:
            logger.error(f"Error during fallback remux: {e}", exc_info=True)
            return await self._remux_to_mp4_two_step(ts_path, mp4_path)

    async def _remux_to_mp4_two_step(self, ts_path: str, mp4_path: str) -> bool:
        """Two-step fallback: extract streams then recombine"""
        try:
            logger.info("Using two-step method for problematic TS file")

            # Try two-step process: extract streams then recombine
            video_path = f"{ts_path}.h264"
            audio_path = f"{ts_path}.aac"

            # Step 1: Extract streams
            extract_cmd = [
                "ffmpeg",
                "-fflags", "+discardcorrupt",
                "-i", ts_path,
                "-map", "0:v:0?",
                "-c:v", "copy",
                "-f", "h264",
                video_path,
                "-map", "0:a:0?",
                "-c:a", "aac",
                "-b:a", "128k",
                "-f", "adts",
                audio_path,
                "-y", "-v", "warning"
            ]

            logger.info("Step 1: Extracting streams...")
            process = await asyncio.create_subprocess_exec(
                *extract_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            # Step 2: Recombine to MP4
            if os.path.exists(video_path) and os.path.exists(audio_path):
                logger.info("Step 2: Recombining streams...")
                
                # Ensure output directory permissions
                output_dir = os.path.dirname(mp4_path)
                if not os.path.exists(output_dir):
                    os.makedirs(output_dir, mode=0o755, exist_ok=True)
                
                combine_cmd = [
                    "ffmpeg",
                    "-i", video_path,
                    "-i", audio_path,
                    "-c:v", "copy",
                    "-c:a", "copy",
                    "-bsf:a", "aac_adtstoasc",  # Ensure proper AAC format
                    "-movflags", "+faststart",
                    "-y", mp4_path,
                    "-v", "warning"
                ]

                process = await asyncio.create_subprocess_exec(
                    *combine_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()
                
                # Clean up temporary files
                for temp_file in [video_path, audio_path]:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)

                if process.returncode == 0 and os.path.exists(mp4_path) and os.path.getsize(mp4_path) > 0:
                    mp4_size_mb = os.path.getsize(mp4_path) / (1024 * 1024)
                    logger.info(f"Two-step remux successful: {mp4_path} ({mp4_size_mb:.1f} MB)")
                    
                    # Delete TS file after successful conversion
                    if os.path.exists(ts_path):
                        os.remove(ts_path)
                    return True
                else:
                    logger.error("Two-step remux failed")
                    return False
            else:
                logger.error("Failed to extract streams in step 1")
                return False
                
        except Exception as e:
            logger.error(f"Error during two-step remux: {e}", exc_info=True)
            return False

    async def _validate_mp4(self, mp4_path: str) -> bool:
        """Validate that an MP4 file is properly created and readable"""
        try:
            # Check if file exists and has reasonable size
            if not os.path.exists(mp4_path) or os.path.getsize(mp4_path) < 10000:
                logger.warning(f"MP4 file does not exist or is too small: {mp4_path}")
                return False

            # Simple validation: Can ffprobe read the file and get basic info?
            cmd = [
                "ffprobe",
                "-v", "quiet",
                "-show_format",
                "-show_streams",
                mp4_path
            ]

            process_id = f"ffprobe_validate_{int(datetime.now().timestamp())}"
            process = await self.subprocess_manager.start_process(cmd, process_id)

            if not process:
                logger.error("Failed to start ffprobe validate process")
                return False

            stdout, stderr = await process.communicate()
            await self.subprocess_manager.terminate_process(process_id)

            # If ffprobe can read the file successfully, it's valid
            if process.returncode == 0 and stdout:
                logger.debug(f"MP4 file validation: File is readable and valid")
                return True
            else:
                logger.warning(f"MP4 file validation failed: ffprobe returned {process.returncode}")
                return False

        except Exception as e:
            logger.error(f"Error validating MP4 file: {e}", exc_info=True)
            return False

    async def _repair_mp4(self, ts_path: str, mp4_path: str) -> bool:
        """Attempt to repair a damaged MP4 file"""
        try:
            # Temporary file for the repaired version
            repaired_path = mp4_path + ".repaired.mp4"

            # First, check what streams are available in the TS file
            probe_cmd = [
                "ffprobe",
                "-v", "error",
                "-show_streams",
                "-select_streams", "v,a",
                "-of", "csv=p=0",
                ts_path
            ]
            
            probe_process_id = f"ffprobe_streams_{int(datetime.now().timestamp())}"
            probe_process = await self.subprocess_manager.start_process(probe_cmd, probe_process_id)
            
            if not probe_process:
                logger.error("Failed to start ffprobe process for stream detection")
                # Fall back to original repair method
                has_video = True  # Assume video for fallback
                has_audio = True
            else:
                probe_stdout, probe_stderr = await probe_process.communicate()
                await self.subprocess_manager.terminate_process(probe_process_id)
                
                has_video = False
                has_audio = False
                
                if probe_process.returncode == 0 and probe_stdout:
                    streams_info = probe_stdout.decode("utf-8", errors="ignore").strip()
                    has_video = "video" in streams_info.lower()
                    has_audio = "audio" in streams_info.lower()
                    logger.debug(f"Stream detection for {ts_path}: has_video={has_video}, has_audio={has_audio}")
                else:
                    # If probe failed, assume both for safety
                    has_video = True
                    has_audio = True

            # Extract streams based on what's available
            if has_video and has_audio:
                # Video + Audio stream
                extract_cmd = [
                    "ffmpeg",
                    "-i", ts_path,
                    # Extract video (copy)
                    "-map", "0:v:0",
                    "-c:v", "copy",
                    "-f", "h264",
                    f"{ts_path}.h264",
                    # Extract audio and convert to AAC
                    "-map", "0:a:0",
                    "-c:a", "aac",
                    "-b:a", "128k",
                    "-f", "adts",
                    f"{ts_path}.aac",
                ]
                
                process_id = f"ffmpeg_extract_{int(datetime.now().timestamp())}"
                process = await self.subprocess_manager.start_process(extract_cmd, process_id)
                if process:
                    await process.communicate()
                    await self.subprocess_manager.terminate_process(process_id)

                # Combine streams into MP4
                if os.path.exists(f"{ts_path}.h264") and os.path.exists(f"{ts_path}.aac"):
                    combine_cmd = [
                        "ffmpeg",
                        "-i", f"{ts_path}.h264",
                        "-i", f"{ts_path}.aac",
                        "-c:v", "copy",
                        "-c:a", "copy",
                        "-movflags", "+faststart",
                        "-y", repaired_path,
                    ]

                    process_id = f"ffmpeg_combine_{int(datetime.now().timestamp())}"
                    process = await self.subprocess_manager.start_process(combine_cmd, process_id)
                    if process:
                        stdout, stderr = await process.communicate()
                        await self.subprocess_manager.terminate_process(process_id)

                        if (process.returncode == 0 and os.path.exists(repaired_path) and os.path.getsize(repaired_path) > 0):
                            # Replace the original file with the repaired version
                            os.replace(repaired_path, mp4_path)
                            logger.info(f"Successfully repaired MP4 file (video+audio): {mp4_path}")

                            # Clean up temporary files
                            for temp_file in [f"{ts_path}.h264", f"{ts_path}.aac"]:
                                if os.path.exists(temp_file):
                                    os.remove(temp_file)

                            # Delete the TS file if the repair was successful
                            if os.path.exists(ts_path):
                                os.remove(ts_path)
                            return True
                        
            elif has_audio and not has_video:
                # Audio-only stream
                logger.info("Detected audio-only stream, creating audio-only MP4")
                audio_only_cmd = [
                    "ffmpeg",
                    "-i", ts_path,
                    "-map", "0:a:0",
                    "-c:a", "aac",
                    "-b:a", "128k",
                    "-movflags", "+faststart",
                    "-y", repaired_path,
                ]
                
                process_id = f"ffmpeg_audio_only_{int(datetime.now().timestamp())}"
                process = await self.subprocess_manager.start_process(audio_only_cmd, process_id)
                if process:
                    stdout, stderr = await process.communicate()
                    await self.subprocess_manager.terminate_process(process_id)

                    if (process.returncode == 0 and os.path.exists(repaired_path) and os.path.getsize(repaired_path) > 0):
                        # Replace the original file with the repaired version
                        os.replace(repaired_path, mp4_path)
                        logger.info(f"Successfully repaired MP4 file (audio-only): {mp4_path}")

                        # Delete the TS file if the repair was successful
                        if os.path.exists(ts_path):
                            os.remove(ts_path)
                        return True

            # Fallback to original repair method if the above failed
            logger.warning("Advanced repair failed, trying original repair method")

            # Original repair code - use flexible mapping for unknown stream types
            cmd = [
                "ffmpeg",
                "-i", ts_path,
                "-c", "copy",
                "-movflags", "+faststart+frag_keyframe+empty_moov+default_base_moof",
                "-f", "mp4",
                "-y", repaired_path,
            ]

            logger.debug(f"Attempting to repair MP4: {' '.join(cmd)}")

            # Use subprocess manager for the repair process
            process_id = f"ffmpeg_repair_{int(datetime.now().timestamp())}"
            process = await self.subprocess_manager.start_process(cmd, process_id)

            if not process:
                logger.error("Failed to start ffmpeg repair process")
                return False

            stdout, stderr = await process.communicate()

            # Clean up the process
            await self.subprocess_manager.terminate_process(process_id)

            if (
                process.returncode == 0
                and os.path.exists(repaired_path)
                and os.path.getsize(repaired_path) > 0
            ):
                # Replace the original file with the repaired version
                os.replace(repaired_path, mp4_path)
                logger.info(f"Successfully repaired MP4 file: {mp4_path}")

                # Delete the TS file if the repair was successful
                if os.path.exists(ts_path):
                    os.remove(ts_path)
                return True
            else:
                stderr_text = (
                    stderr.decode("utf-8", errors="ignore")
                    if stderr
                    else "No error output"
                )
                logger.error(f"Failed to repair MP4 file: {stderr_text}")

                # Keep the TS file for manual recovery
                logger.warning(f"Keeping original TS file at {ts_path} for recovery")
                return False
        except Exception as e:
            logger.error(f"Error repairing MP4: {e}", exc_info=True)
            return False

    async def _update_recording_path(self, stream_id: int, new_path: str):
        """Update the recording path for a stream after media server structure creation"""
        try:
            with SessionLocal() as db:
                stream = db.query(Stream).filter(Stream.id == stream_id).first()
                if stream:
                    old_path = stream.recording_path
                    stream.recording_path = new_path
                    db.commit()
                    logger.info(f"Updated recording_path for stream {stream_id}: {old_path} -> {new_path}")
                else:
                    logger.warning(f"Stream {stream_id} not found for recording_path update")
        except Exception as e:
            logger.error(f"Error updating recording_path for stream {stream_id}: {e}", exc_info=True)

    def _generate_filename(
        self, streamer: Streamer, stream_data: Dict[str, Any], template: str
    ) -> str:
        """Generate a filename from template with variables"""
        now = datetime.now()

        # Sanitize values for filesystem safety
        title = self._sanitize_filename(stream_data.get("title", "untitled"))
        game = self._sanitize_filename(stream_data.get("category_name", "unknown"))
        streamer_name = self._sanitize_filename(streamer.username)

        # Get episode number (count of streams in current month)
        episode = self._get_episode_number(streamer.id, now)

        # Create a dictionary of replaceable values
        values = {
            "streamer": streamer_name,
            "title": title,
            "game": game,
            "twitch_id": streamer.twitch_id,
            "year": now.strftime("%Y"),
            "month": now.strftime("%m"),
            "day": now.strftime("%d"),
            "hour": now.strftime("%H"),
            "minute": now.strftime("%M"),
            "second": now.strftime("%S"),
            "timestamp": now.strftime("%Y%m%d_%H%M%S"),
            "datetime": now.strftime("%Y-%m-%d_%H-%M-%S"),
            "id": stream_data.get("id", ""),
            "season": f"S{now.year}{now.month:02d}",  # Saison ohne Bindestrich
            "episode": episode,  # Nur die Nummer, ohne E-Prefix (wird im Template hinzugefügt)
        }

        # Check if template is a preset name
        if template in FILENAME_PRESETS:
            template = FILENAME_PRESETS[template]
            
        # Replace all variables in template
        filename = template
        for key, value in values.items():
            # Handle both simple placeholders {key} and formatted placeholders {key:format}
            import re
            
            # Pattern for {key} or {key:format}
            pattern = r'\{' + re.escape(key) + r'(?::[^}]*)?\}'
            
            if re.search(pattern, filename):
                # If it's a numeric value and has formatting, apply the formatting
                if key == "episode" and "{episode:" in filename:
                    # Extract the format specification
                    episode_match = re.search(r'\{episode:([^}]*)\}', filename)
                    if episode_match:
                        format_spec = episode_match.group(1)
                        try:
                            # Apply the format to the numeric episode value
                            episode_num = int(episode) if isinstance(episode, int) else int(str(episode).lstrip('E'))
                            formatted_value = f"{episode_num:{format_spec}}"  # Don't add E prefix, it's in the template
                            filename = re.sub(r'\{episode:[^}]*\}', formatted_value, filename)
                        except (ValueError, TypeError):
                            # Fallback to simple replacement
                            filename = re.sub(pattern, str(value), filename)
                else:
                    # Simple replacement for all other cases
                    filename = re.sub(pattern, str(value), filename)

        # Ensure the filename ends with .mp4
        if not filename.lower().endswith(".mp4"):
            filename += ".mp4"
        return filename

    def _get_episode_number(self, streamer_id: int, now: datetime) -> int:
        """Get episode number (count of streams in current month)"""
        try:
            with SessionLocal() as db:
                # Count streams in the current month for this streamer
                stream_count = (
                    db.query(Stream)
                    .filter(
                        Stream.streamer_id == streamer_id,
                        extract("year", Stream.started_at) == now.year,
                        extract("month", Stream.started_at) == now.month,
                    )
                    .count()
                )
                # Add 1 for the current stream
                episode_number = stream_count + 1
                logger.debug(
                    f"Episode number for streamer {streamer_id} in {now.year}-{now.month:02d}: {episode_number}"
                )
                return episode_number  # Return as integer for proper formatting

        except Exception as e:
            logger.error(f"Error getting episode number: {e}", exc_info=True)
            return 1  # Default value

    def _sanitize_filename(self, name: str) -> str:
        """Remove illegal characters from filename"""
        return re.sub(r'[<>:"/\\|?*]', "_", name)

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
        try:
            base_path = mp4_path.replace(".mp4", "")
            temp_extensions = [".ts", ".h264", ".aac", ".temp", ".processing"]
            
            cleaned_files = []
            for ext in temp_extensions:
                temp_file = base_path + ext
                if os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                        cleaned_files.append(temp_file)
                        logger.debug(f"Cleaned up temporary file: {temp_file}")
                    except Exception as e:
                        logger.warning(f"Failed to remove temporary file {temp_file}: {e}")
            
            if cleaned_files:
                logger.info(f"Cleaned up {len(cleaned_files)} temporary files for {os.path.basename(mp4_path)}")
            else:
                logger.debug(f"No temporary files to clean up for {os.path.basename(mp4_path)}")
                
        except Exception as e:
            logger.error(f"Error cleaning up temporary files: {e}", exc_info=True)
