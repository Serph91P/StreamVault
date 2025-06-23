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
from app.dependencies import websocket_manager

logger = logging.getLogger("streamvault")

# Spezieller Logger für Recording-Aktivitäten
recording_logger = logging.getLogger("streamvault.recording")

class RecordingActivityLogger:
    """Detailliertes Logging für alle Recording-Aktivitäten"""
    
    def __init__(self):
        self.session_id = str(uuid.uuid4())[:8]
    
    def log_recording_start(self, streamer_id: int, streamer_name: str, quality: str, output_path: str):
        """Log the start of a recording session"""
        recording_logger.info(f"[SESSION:{self.session_id}] RECORDING_START - Streamer: {streamer_name} (ID: {streamer_id})")
        recording_logger.info(f"[SESSION:{self.session_id}] Quality: {quality}, Output: {output_path}")
    
    def log_recording_stop(self, streamer_id: int, streamer_name: str, reason: str = "manual"):
        """Log the stop of a recording session"""
        recording_logger.info(f"[SESSION:{self.session_id}] RECORDING_STOP - Streamer: {streamer_name} (ID: {streamer_id}), Reason: {reason}")
    
    def log_recording_error(self, streamer_id: int, streamer_name: str, error: str):
        """Log recording errors"""
        recording_logger.error(f"[SESSION:{self.session_id}] RECORDING_ERROR - Streamer: {streamer_name} (ID: {streamer_id}), Error: {error}")
    
    def log_process_monitoring(self, streamer_name: str, action: str, details: str = ""):
        """Log process monitoring activities"""
        recording_logger.debug(f"[SESSION:{self.session_id}] PROCESS_MONITOR - {streamer_name}: {action} {details}")
    
    def log_file_operation(self, operation: str, file_path: str, success: bool, details: str = ""):
        """Log file operations (remux, conversion, etc.)"""
        status = "SUCCESS" if success else "FAILED"
        recording_logger.info(f"[SESSION:{self.session_id}] FILE_OP - {operation}: {file_path} - {status} {details}")
    
    def log_stream_detection(self, streamer_name: str, is_live: bool, stream_info: Optional[dict] = None):
        """Log stream detection and status"""
        status = "LIVE" if is_live else "OFFLINE"
        recording_logger.info(f"[SESSION:{self.session_id}] STREAM_STATUS - {streamer_name}: {status}")
        if stream_info:
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
            return "{streamer}/{streamer}_{year}-{month}-{day}_{hour}-{minute}_{title}_{game}"  # Default fallback

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
            self.activity_logger = RecordingActivityLogger()
            self.initialized = True
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
                        recording_info = self.active_recordings[streamer_id]                        await websocket_manager.send_notification(
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
            import aiohttp
            
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
            # Streamer erscheint offline oder API-Fehler, Standarddaten erstellen
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

            # Clean up all temporary files after successful metadata generation
            await self._cleanup_temporary_files(mp4_path)
            
        except Exception as e:
            logger.error(f"Error generating metadata for stream {stream_id}: {e}", exc_info=True)
            # Still attempt to clean up temporary files even if metadata generation failed
            try:
                await self._cleanup_temporary_files(mp4_path)
            except Exception as cleanup_error:
                logger.warning(f"Failed to clean up temporary files: {cleanup_error}")

    async def _cleanup_temporary_files(self, mp4_path: str):
        """Clean up temporary files created during recording and processing"""
        try:
            base_path = mp4_path.replace(".mp4", "")
            ts_path = base_path + ".ts"
            
            # List of potential temporary files
            temp_files = [
                ts_path,
                ts_path + ".aac",
                ts_path + ".h264", 
                mp4_path + ".repaired.mp4"
            ]
            
            cleaned_files = []
            for temp_file in temp_files:
                if os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                        cleaned_files.append(temp_file)
                        logger.debug(f"Removed temporary file: {temp_file}")
                    except Exception as e:
                        logger.warning(f"Failed to remove temporary file {temp_file}: {e}")
            
            if cleaned_files:
                logger.info(f"Cleaned up {len(cleaned_files)} temporary files for {mp4_path}")
            
        except Exception as e:
            logger.error(f"Error in temporary file cleanup: {e}")

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
                        recording_info = self.active_recordings[streamer_id]                        await websocket_manager.send_notification(
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
            import aiohttp
            
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
            # Streamer erscheint offline oder API-Fehler, Standarddaten erstellen
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

            # Clean up all temporary files after successful metadata generation
            await self._cleanup_temporary_files(mp4_path)
            
        except Exception as e:
            logger.error(f"Error generating metadata for stream {stream_id}: {e}", exc_info=True)
            # Still attempt to clean up temporary files even if metadata generation failed
            try:
                await self._cleanup_temporary_files(mp4_path)
            except Exception as cleanup_error:
                logger.warning(f"Failed to clean up temporary files: {cleanup_error}")

    async def _cleanup_temporary_files(self, mp4_path: str):
        """Clean up temporary files created during recording and processing"""
        try:
            base_path = mp4_path.replace(".mp4", "")
            ts_path = base_path + ".ts"
            
            # List of potential temporary files
            temp_files = [
                ts_path,
                ts_path + ".aac",
                ts_path + ".h264", 
                mp4_path + ".repaired.mp4"
            ]
            
            cleaned_files = []
            for temp_file in temp_files:
                if os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                        cleaned_files.append(temp_file)
                        logger.debug(f"Removed temporary file: {temp_file}")
                    except Exception as e:
                        logger.warning(f"Failed to remove temporary file {temp_file}: {e}")
            
            if cleaned_files:
                logger.info(f"Cleaned up {len(cleaned_files)} temporary files for {mp4_path}")
            
        except Exception as e:
            logger.error(f"Error in temporary file cleanup: {e}")

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
                        recording_info = self.active_recordings[streamer_id]                        await websocket_manager.send_notification(
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
            import aiohttp
            
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
            # Streamer erscheint offline oder API-Fehler, Standarddaten erstellen
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

            # Clean up all temporary files after successful metadata generation
            await self._cleanup_temporary_files(mp4_path)
            
        except Exception as e:
            logger.error(f"Error generating metadata for stream {stream_id}: {e}", exc_info=True)
            # Still attempt to clean up temporary files even if metadata generation failed
            try:
                await self._cleanup_temporary_files(mp4_path)
            except Exception as cleanup_error:
                logger.warning(f"Failed to clean up temporary files: {cleanup_error}")

    async def _cleanup_temporary_files(self, mp4_path: str):
        """Clean up temporary files created during recording and processing"""
        try:
            base_path = mp4_path.replace(".mp4", "")
            ts_path = base_path + ".ts"
            
            # List of potential temporary files
            temp_files = [
                ts_path,
                ts_path + ".aac",
                ts_path + ".h264", 
                mp4_path + ".repaired.mp4"
            ]
            
            cleaned_files = []
            for temp_file in temp_files:
                if os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                        cleaned_files.append(temp_file)
                        logger.debug(f"Removed temporary file: {temp_file}")
                    except Exception as e:
                        logger.warning(f"Failed to remove temporary file {temp_file}: {e}")
            
            if cleaned_files:
                logger.info(f"Cleaned up {len(cleaned_files)} temporary files for {mp4_path}")
            
        except Exception as e:
            logger.error(f"Error in temporary file cleanup: {e}")

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
                        recording_info = self.active_recordings[streamer_id]                        await websocket_manager.send_notification(
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
            import aiohttp
            
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
            # Streamer erscheint offline oder API-Fehler, Standarddaten erstellen
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

            # Clean up all temporary files after successful metadata generation
            await self._cleanup_temporary_files(mp4_path)
            
        except Exception as e:
            logger.error(f"Error generating metadata for stream {stream_id}: {e}", exc_info=True)
            # Still attempt to clean up temporary files even if metadata generation failed
            try:
                await self._cleanup_temporary_files(mp4_path)
            except Exception as cleanup_error:
                logger.warning(f"Failed to clean up temporary files: {cleanup_error}")

    async def _cleanup_temporary_files(self, mp4_path: str):
        """Clean up temporary files created during recording and processing"""
        try:
            base_path = mp4_path.replace(".mp4", "")
            ts_path = base_path + ".ts"
            
            # List of potential temporary files
            temp_files = [
                ts_path,
                ts_path + ".aac",
                ts_path + ".h264", 
                mp4_path + ".repaired.mp4"
            ]
            
            cleaned_files = []
            for temp_file in temp_files:
                if os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                        cleaned_files.append(temp_file)
                        logger.debug(f"Removed temporary file: {temp_file}")
                    except Exception as e:
                        logger.warning(f"Failed to remove temporary file {temp_file}: {e}")
            
            if cleaned_files:
                logger.info(f"Cleaned up {len(cleaned_files)} temporary files for {mp4_path}")
            
        except Exception as e:
            logger.error(f"Error in temporary file cleanup: {e}")

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
                        recording_info = self.active_recordings[streamer_id]                        await websocket_manager.send_notification(
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
            import aiohttp
            
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
            # Streamer erscheint offline oder API-Fehler, Standarddaten erstellen
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

            # Clean up all temporary files after successful metadata generation
            await self._cleanup_temporary_files(mp4_path)
            
        except Exception as e:
            logger.error(f"Error generating metadata for stream {stream_id}: {e}", exc_info=True)
            # Still attempt to clean up temporary files even if metadata generation failed
            try:
                await self._cleanup_temporary_files(mp4_path)
            except Exception as cleanup_error:
                logger.warning(f"Failed to clean up temporary files: {cleanup_error}")

    async def _cleanup_temporary_files(self, mp4_path: str):
        """Clean up temporary files created during recording and processing"""
        try:
            base_path = mp4_path.replace(".mp4", "")
            ts_path = base_path + ".ts"
            
            # List of potential temporary files
            temp_files = [
                ts_path,
                ts_path + ".aac",
                ts_path + ".h264", 
                mp4_path + ".repaired.mp4"
            ]
            
            cleaned_files = []
            for temp_file in temp_files:
                if os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                        cleaned_files.append(temp_file)
                        logger.debug(f"Removed temporary file: {temp_file}")
                    except Exception as e:
                        logger.warning(f"Failed to remove temporary file {temp_file}: {e}")
            
            if cleaned_files:
                logger.info(f"Cleaned up {len(cleaned_files)} temporary files for {mp4_path}")
            
        except Exception as e:
            logger.error(f"Error in temporary file cleanup: {e}")

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
            logger.info("Recording service cleanup completed")

        except Exception as e:
            logger.error(f"Error during recording service cleanup: {e}", exc_info=True)


# Filename presets


FILENAME_PRESETS = {
    "default": "{streamer}/{streamer}_{year}-{month}-{day}_{hour}-{minute}_{title}_{game}",
    "plex": "{streamer}/Season {year}{month}/{streamer} - S{year}{month}E{episode} - {title}",
    "emby": "{streamer}/S{year}{month}/{streamer} - S{year}{month}E{episode} - {title}",
    "jellyfin": "{streamer}/Season {year}{month}/{streamer} - {year}.{month}.{day} - E{episode} - {title}",
    "kodi": "{streamer}/Season {year}{month}/{streamer} - s{year}{month}e{episode} - {title}",
    "chronological": "{year}/{month}/{day}/{streamer} - E{episode} - {title} - {hour}-{minute}",
}
