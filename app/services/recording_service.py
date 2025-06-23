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
                        recording_info = self.active_recordings[streamer_id]
                        await websocket_manager.send_notification(
                            {
                                "type": "recording.failed",
                                "data": {
                                    "streamer_id": streamer_id,
                                    "streamer_name": recording_info["streamer_name"],
                                    "error": str(e),
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

        except Exception as e:
            logger.error(f"Error in delayed metadata generation: {e}", exc_info=True)

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
        await asyncio.sleep(10)

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

            # Adjust the quality string for better resolution selection
            adjusted_quality = quality
            if quality == "best":
                # Use a more specific quality selection string to prioritize highest resolution
                adjusted_quality = "1080p60,1080p,best"

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
                # LiveStreamDVR-inspired parameters for better proxy compatibility
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
            
            # Enhanced remux settings optimized for sync preservation, especially for proxy recordings
            cmd = [
                "ffmpeg",
                "-fflags", "+genpts+igndts+ignidx",  # Generate PTS, ignore DTS and index for better sync recovery
                "-analyzeduration", "20M" if is_proxy_recording else "10M",     # Analyze more data for proxy recordings
                "-probesize", "20M" if is_proxy_recording else "10M",          # Probe more data for stream analysis
                "-i", ts_path,
                "-c:v", "copy",               # Copy video stream (no re-encoding)
                "-c:a", "copy",               # Copy audio stream (preserve original timing)
                "-avoid_negative_ts", "make_zero",  # Handle negative timestamps
                "-map", "0:v:0",              # Map first video stream
                "-map", "0:a:0?",             # Map first audio stream (optional)
                "-movflags", "+faststart+frag_keyframe" if is_proxy_recording else "+faststart",  # Optimize for proxy recordings
                "-ignore_unknown",            # Ignore unknown streams
                "-max_muxing_queue_size", "8192" if is_proxy_recording else "4096",  # Larger queue for proxy recordings
                "-async", "1",                # Audio sync method for better audio/video alignment
                "-vsync", "cfr",              # Constant frame rate for better sync
                "-metadata", "encoded_by=StreamVault",
                "-metadata", "encoding_tool=StreamVault",
                "-y", mp4_path,
            ]

            # Get FFmpeg log path for this operation
            ffmpeg_log_path = logging_service.get_ffmpeg_log_path("remux", streamer_name)
            
            # Add logging to FFmpeg command
            cmd.extend([
                "-report",
                "-v", "verbose",
                "-stats"
            ])
            
            # Set environment variable for FFmpeg report
            env = os.environ.copy()
            env["FFREPORT"] = f"file={ffmpeg_log_path}:level=32"

            # Log the command start
            logging_service.log_ffmpeg_start("remux", cmd, streamer_name)

            logger.debug(f"Starting enhanced FFmpeg remux: {' '.join(cmd)}")

            # Use subprocess manager for the remux process
            process_id = f"ffmpeg_remux_{streamer_name}_{int(datetime.now().timestamp())}"
            
            # Start process with custom environment
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )

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
                        return await self._repair_mp4(ts_path, mp4_path)
                else:
                    logger.error(f"MP4 file was not created or is empty: {mp4_path}")
                    return False
            else:
                logger.error(f"FFmpeg remux failed with exit code {exit_code}")
                # Try with fallback method if the first attempt failed
                return await self._remux_to_mp4_fallback(ts_path, mp4_path)
                
        except Exception as e:
            logger.error(f"Error during remux: {e}", exc_info=True)
            return False

    async def _remux_to_mp4(self, ts_path: str, mp4_path: str) -> bool:
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
                "0:v:0",  # Nur den ersten Video-Stream verwenden
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
                        return await self._repair_mp4(ts_path, mp4_path)
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
        try:
            logger.info("Using advanced fallback method for remuxing")

            # Try two-step process: extract streams then recombine
            video_path = f"{ts_path}.h264"
            audio_path = f"{ts_path}.aac"

            # Step 1: Extract streams
            extract_cmd = [
                "ffmpeg",
                "-i",
                ts_path,
                "-map",
                "0:v:0",
                "-c:v",
                "copy",
                "-f",
                "h264",
                video_path,
                "-map",
                "0:a:0",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-f",
                "adts",
                audio_path,
                "-y",
            ]

            process_id = f"ffmpeg_extract_{int(datetime.now().timestamp())}"
            process = await self.subprocess_manager.start_process(
                extract_cmd, process_id
            )
            await process.communicate()
            await self.subprocess_manager.terminate_process(process_id)

            # Step 2: Recombine to MP4
            if os.path.exists(video_path) and os.path.getsize(video_path) > 0:
                combine_cmd = ["ffmpeg", "-i", video_path]

                # Only add audio if it exists
                if os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
                    combine_cmd.extend(["-i", audio_path])

                combine_cmd.extend(
                    [
                        "-c:v",
                        "copy",
                        "-c:a",
                        "copy",
                        "-movflags",
                        "+faststart",
                        "-y",
                        mp4_path,
                    ]
                )

                process_id = f"ffmpeg_combine_{int(datetime.now().timestamp())}"
                process = await self.subprocess_manager.start_process(
                    combine_cmd, process_id
                )
                stdout, stderr = await process.communicate()
                await self.subprocess_manager.terminate_process(process_id)

                # Clean up temp files
                if os.path.exists(video_path):
                    os.remove(video_path)
                if os.path.exists(audio_path):
                    os.remove(audio_path)

                # Check if successful
                if (
                    process.returncode == 0
                    and os.path.exists(mp4_path)
                    and os.path.getsize(mp4_path) > 0
                ):
                    logger.info(
                        f"Successfully remuxed using advanced fallback method: {mp4_path}"
                    )

                    # Delete original TS file
                    if os.path.exists(ts_path):
                        os.remove(ts_path)
                    return True

            # If we're here, try the simplest possible method as last resort
            logger.warning("Advanced fallback failed, trying simple fallback method")

            simple_cmd = ["ffmpeg", "-i", ts_path, "-c:v", "copy", "-y", mp4_path]

            process_id = f"ffmpeg_simple_{int(datetime.now().timestamp())}"
            process = await self.subprocess_manager.start_process(
                simple_cmd, process_id
            )
            stdout, stderr = await process.communicate()
            await self.subprocess_manager.terminate_process(process_id)

            if (
                process.returncode == 0
                and os.path.exists(mp4_path)
                and os.path.getsize(mp4_path) > 0
            ):
                logger.info(
                    f"Successfully remuxed using simple fallback method: {mp4_path}"
                )

                # Delete original TS file
                if os.path.exists(ts_path):
                    os.remove(ts_path)
                return True

            # If all failed, keep TS file for manual recovery
            logger.error(
                "All remux methods failed, keeping TS file for manual recovery"
            )
            return False
        except Exception as e:
            logger.error(f"Error in fallback remux: {e}", exc_info=True)
            return False

    async def _validate_mp4(self, mp4_path: str) -> bool:
        """Validate that an MP4 file is properly finalized with moov atom"""
        try:
            # Check if file exists and has reasonable size
            if (
                not os.path.exists(mp4_path) or os.path.getsize(mp4_path) < 10000
            ):  # At least 10KB
                logger.warning(f"MP4 file does not exist or is too small: {mp4_path}")
                return False

            # Use ffprobe to check if the file has a valid duration (indicates proper moov atom)
            cmd = [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                mp4_path,
            ]

            process_id = f"ffprobe_validate_{int(datetime.now().timestamp())}"
            process = await self.subprocess_manager.start_process(cmd, process_id)

            stdout, stderr = await process.communicate()

            # Clean up the process
            await self.subprocess_manager.terminate_process(process_id)

            # Additional check: Make sure we can read video streams
            check_video_cmd = [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=codec_type",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                mp4_path,
            ]

            video_process_id = f"ffprobe_video_{int(datetime.now().timestamp())}"
            video_process = await self.subprocess_manager.start_process(
                check_video_cmd, video_process_id
            )

            video_stdout, video_stderr = await video_process.communicate()
            await self.subprocess_manager.terminate_process(video_process_id)

            # If we got a valid duration and can read video stream, the file is properly finalized
            has_valid_duration = (
                process.returncode == 0
                and stdout
                and float(stdout.decode("utf-8", errors="ignore").strip()) > 0
            )
            has_video_stream = (
                video_process.returncode == 0
                and video_stdout
                and "video" in video_stdout.decode("utf-8", errors="ignore").strip()
            )

            return has_valid_duration and has_video_stream
        except Exception as e:
            logger.error(f"Error validating MP4 file: {e}", exc_info=True)
            return False

    async def _repair_mp4(self, ts_path: str, mp4_path: str) -> bool:
        """Attempt to repair a damaged MP4 file"""
        try:
            # Temporary file for the repaired version
            repaired_path = mp4_path + ".repaired.mp4"

            # Extract video and audio streams separately and then combine
            cmd = [
                "ffmpeg",
                "-i",
                ts_path,
                # Extract video (copy)
                "-map",
                "0:v:0",
                "-c:v",
                "copy",
                "-f",
                "h264",
                f"{ts_path}.h264",
                # Extract audio and convert to AAC
                "-map",
                "0:a:0",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-f",
                "adts",
                f"{ts_path}.aac",
            ]

            # First pass: extract streams
            process_id = f"ffmpeg_extract_{int(datetime.now().timestamp())}"
            process = await self.subprocess_manager.start_process(cmd, process_id)
            await process.communicate()
            await self.subprocess_manager.terminate_process(process_id)

            # Second pass: combine streams into MP4
            if os.path.exists(f"{ts_path}.h264") and os.path.exists(f"{ts_path}.aac"):
                combine_cmd = [
                    "ffmpeg",
                    "-i",
                    f"{ts_path}.h264",
                    "-i",
                    f"{ts_path}.aac",
                    "-c:v",
                    "copy",
                    "-c:a",
                    "copy",
                    "-movflags",
                    "+faststart",
                    "-y",
                    repaired_path,
                ]

                process_id = f"ffmpeg_combine_{int(datetime.now().timestamp())}"
                process = await self.subprocess_manager.start_process(
                    combine_cmd, process_id
                )
                stdout, stderr = await process.communicate()
                await self.subprocess_manager.terminate_process(process_id)

                # Check if successful
                if (
                    process.returncode == 0
                    and os.path.exists(repaired_path)
                    and os.path.getsize(repaired_path) > 0
                ):
                    # Replace the original file with the repaired version
                    os.replace(repaired_path, mp4_path)
                    logger.info(f"Successfully repaired MP4 file: {mp4_path}")

                    # Clean up temporary files
                    os.remove(f"{ts_path}.h264")
                    os.remove(f"{ts_path}.aac")

                    # Delete the TS file if the repair was successful
                    if os.path.exists(ts_path):
                        os.remove(ts_path)
                    return True

            # Fallback to original repair method if the above failed
            logger.warning("Advanced repair failed, trying original repair method")

            # Original repair code follows...
            cmd = [
                "ffmpeg",
                "-i",
                ts_path,
                "-c",
                "copy",
                "-movflags",
                "+faststart+frag_keyframe+empty_moov+default_base_moof",
                "-f",
                "mp4",
                "-y",
                repaired_path,
            ]

            logger.debug(f"Attempting to repair MP4: {' '.join(cmd)}")

            # Use subprocess manager for the repair process
            process_id = f"ffmpeg_repair_{int(datetime.now().timestamp())}"
            process = await self.subprocess_manager.start_process(cmd, process_id)

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
            "episode": f"E{episode}",  # Präfix E zur Episodennummer hinzufügen
        }

        # Check if template is a preset name
        if template in FILENAME_PRESETS:
            template = FILENAME_PRESETS[template]
            
        # Replace all variables in template
        filename = template
        for key, value in values.items():
            placeholder = f"{{{key}}}"
            if placeholder in filename:  # Prüfen, ob der Platzhalter vorhanden ist
                filename = filename.replace(placeholder, str(value))

        # Ensure the filename ends with .mp4
        if not filename.lower().endswith(".mp4"):
            filename += ".mp4"
        return filename

    def _get_episode_number(self, streamer_id: int, now: datetime) -> str:
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
                return f"{episode_number:02d}"  # Format with leading zero

        except Exception as e:
            logger.error(f"Error getting episode number: {e}", exc_info=True)
            return "01"  # Default value

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
