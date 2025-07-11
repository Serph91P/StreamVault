"""
StreamVault Recording Service

This service handles the complete recording lifecycle for Twitch streams,
including process management, file conversion, and metadata generation.

Last updated: 2025-07-11 - Fixed metadata service integration
"""

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
import shutil
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
    Recording,
    RecordingVideo,
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
                    self._streamer_settings[streamer_id] = None
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
                    # Force kill if graceful termination doesn't work
                    process.kill()
                    await process.wait()
                
                self.active_processes.pop(process_id)
                return True
            except Exception as e:
                logger.error(f"Failed to terminate process {process_id}: {e}")
                return False
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
                    
                    # Note: Thumbnail generation is now handled after MP4 creation
                    # in _delayed_metadata_generation() method for better quality
        except Exception as e:
            logger.error(f"Error setting up stream metadata: {e}")
            
    async def stop_recording(self, streamer_id: int, reason: str = "automatic") -> bool:
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

                # The stop reason is now passed as parameter
                stop_reason = reason
                
                # Log recording stop with the correct reason
                logging_service.log_recording_stop(
                    streamer_id, 
                    recording_info['streamer_name'], 
                    duration, 
                    recording_info.get('output_path', 'Unknown'),
                    stop_reason
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
                    
                    # Also ensure cleanup happens if recording was manually stopped
                    if output_path:
                        # Schedule a cleanup in case the delayed metadata generation doesn't complete
                        asyncio.create_task(self._delayed_cleanup_on_manual_stop(output_path, 120))  # 2 minutes delay
                    
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

    async def force_start_recording_offline_test(
        self, streamer_id: int, stream_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Force start a recording even when the streamer is definitely offline.
        
        WARNING: This method is intended for testing purposes only and will likely fail
        to produce any actual recording content since the streamer is not streaming.
        
        Use force_start_recording_with_api_check() for normal force recording operations.
        
        Args:
            streamer_id: ID of the streamer
            stream_data: Optional stream data (if None, will create test data)
            
        Returns:
            bool: True if recording process started, False otherwise
        """
        try:
            with SessionLocal() as db:
                streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
                if not streamer:
                    logger.error(f"Streamer not found: {streamer_id}")
                    raise StreamerNotFoundError(f"Streamer not found: {streamer_id}")

                logger.warning(f"TESTING MODE: Starting offline recording for {streamer.username} without API check")
                logger.warning("This will likely fail to produce content since the streamer is not live")
                
                # Create test stream data if none provided
                if not stream_data:
                    stream_data = {
                        "id": f"test_{int(datetime.now().timestamp())}",
                        "broadcaster_user_id": streamer.twitch_id,
                        "broadcaster_user_name": streamer.username,
                        "started_at": datetime.now(timezone.utc).isoformat(),
                        "title": f"TEST RECORDING - {streamer.username}",
                        "category_name": "Testing",
                        "language": "en",
                    }

                # Update streamer status (for our internal tracking)
                self._update_streamer_status(streamer, stream_data, db)

                # Create stream record
                stream = await self._find_or_create_offline_stream(
                    streamer_id, streamer, stream_data, db
                )

                # Create metadata entry
                await self._ensure_stream_metadata(stream.id, db)

                # Send notification
                await self._send_stream_online_notification(streamer, stream_data)

                # Attempt recording (will likely fail)
                recording_started = await self.start_recording(streamer_id, stream_data, force_mode=True)

                if recording_started and streamer_id in self.active_recordings:
                    self.active_recordings[streamer_id]["stream_id"] = stream.id
                    self.active_recordings[streamer_id]["force_started"] = True
                    self.active_recordings[streamer_id]["test_recording"] = True
                    
                    logger.warning(f"Test offline recording started for {streamer.username}. Expect it to fail quickly.")
                    return True
                else:
                    logger.error(f"Failed to start test recording for {streamer.username}")
                    return False

        except RecordingError:
            raise
        except Exception as e:
            logger.error(f"Error in test offline recording: {e}", exc_info=True)
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

    async def force_start_recording_with_api_check(
        self, streamer_id: int, stream_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Intelligently start a recording by first checking if the streamer is actually online via API.
        
        This method will:
        1. First check the Twitch API to see if the streamer is actually live
        2. If they are live, start a normal force recording
        3. If they are offline but user still wants to force record (for testing/special cases),
           attempt an offline recording with appropriate warnings
        
        Args:
            streamer_id: ID of the streamer
            stream_data: Optional stream data (if None, will be created based on API response)
            
        Returns:
            bool: True if recording started successfully, False otherwise
        """
        try:
            with SessionLocal() as db:
                streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
                if not streamer:
                    logger.error(f"Streamer not found: {streamer_id}")
                    raise StreamerNotFoundError(f"Streamer not found: {streamer_id}")

                # FIRST: Check if the streamer is actually live via Twitch API
                logger.info(f"Checking Twitch API to see if {streamer.username} is actually live...")
                stream_info = await self._get_stream_info_from_api(streamer, db)

                if stream_info:
                    # Streamer is actually live! Use the normal force recording method
                    logger.info(f"API confirms {streamer.username} is live. Using normal force recording.")
                    return await self.force_start_recording(streamer_id)
                
                # If we get here, the streamer appears to be offline according to the API
                logger.warning(f"API indicates {streamer.username} is offline. Proceeding with offline force recording (this is unusual and may fail).")
                
                # If no stream data was provided, create default data for offline recording
                if not stream_data:
                    stream_data = self._create_stream_data(streamer, None)  # Pass None since they're offline

                # Warn about potential issues with offline recording
                logger.warning(f"Attempting to start recording for {streamer.username} while they appear offline. This may fail because:")
                logger.warning("1. Streamlink may not be able to connect to a non-existent stream")
                logger.warning("2. No actual video content may be available to record")
                logger.warning("3. This should only be used for testing or very special circumstances")

                # Update streamer status to "live" in our database (even though API says offline)
                # This is necessary for our internal logic to work
                self._update_streamer_status(streamer, stream_data, db)

                # Find existing stream or create a new one
                stream = await self._find_or_create_offline_stream(
                    streamer_id, streamer, stream_data, db
                )

                # Create metadata entry if it doesn't exist
                await self._ensure_stream_metadata(stream.id, db)

                # Send WebSocket notification (even though it's an offline recording attempt)
                await self._send_stream_online_notification(streamer, stream_data)

                # Attempt to start the recording (this will likely fail since the stream is offline)
                # Use force_mode=True to give it the best chance of working
                recording_started = await self.start_recording(streamer_id, stream_data, force_mode=True)

                if recording_started and streamer_id in self.active_recordings:
                    self.active_recordings[streamer_id]["stream_id"] = stream.id
                    self.active_recordings[streamer_id]["force_started"] = True
                    self.active_recordings[streamer_id]["offline_recording"] = True  # Mark as offline recording
                    
                    logger.warning(f"Offline force recording started for {streamer.username} (stream_id: {stream.id}). This is unusual and may produce no content.")
                    return True
                else:
                    logger.error(f"Failed to start offline recording for {streamer.username}. This is expected since they appear to be offline.")
                    return False

                return recording_started

        except RecordingError:            # Re-raise specific domain exceptions
            raise
        except Exception as e:
            logger.error(f"Error force starting offline recording: {e}", exc_info=True)
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

    async def force_start_recording_with_api_check(
        self, streamer_id: int, stream_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Intelligently start a recording by first checking if the streamer is actually online via API.
        
        This method will:
        1. First check the Twitch API to see if the streamer is actually live
        2. If they are live, start a normal force recording
        3. If they are offline but user still wants to force record (for testing/special cases),
           attempt an offline recording with appropriate warnings
        
        Args:
            streamer_id: ID of the streamer
            stream_data: Optional stream data (if None, will be created based on API response)
            
        Returns:
            bool: True if recording started successfully, False otherwise
        """
        try:
            with SessionLocal() as db:
                streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
                if not streamer:
                    logger.error(f"Streamer not found: {streamer_id}")
                    raise StreamerNotFoundError(f"Streamer not found: {streamer_id}")

                # FIRST: Check if the streamer is actually live via Twitch API
                logger.info(f"Checking Twitch API to see if {streamer.username} is actually live...")
                stream_info = await self._get_stream_info_from_api(streamer, db)

                if stream_info:
                    # Streamer is actually live! Use the normal force recording method
                    logger.info(f"API confirms {streamer.username} is live. Using normal force recording.")
                    return await self.force_start_recording(streamer_id)
                
                # If we get here, the streamer appears to be offline according to the API
                logger.warning(f"API indicates {streamer.username} is offline. Proceeding with offline force recording (this is unusual and may fail).")
                
                # If no stream data was provided, create default data for offline recording
                if not stream_data:
                    stream_data = self._create_stream_data(streamer, None)  # Pass None since they're offline

                # Warn about potential issues with offline recording
                logger.warning(f"Attempting to start recording for {streamer.username} while they appear offline. This may fail because:")
                logger.warning("1. Streamlink may not be able to connect to a non-existent stream")
                logger.warning("2. No actual video content may be available to record")
                logger.warning("3. This should only be used for testing or very special circumstances")

                # Update streamer status to "live" in our database (even though API says offline)
                # This is necessary for our internal logic to work
                self._update_streamer_status(streamer, stream_data, db)

                # Find existing stream or create a new one
                stream = await self._find_or_create_offline_stream(
                    streamer_id, streamer, stream_data, db
                )

                # Create metadata entry if it doesn't exist
                await self._ensure_stream_metadata(stream.id, db)

                # Send WebSocket notification (even though it's an offline recording attempt)
                await self._send_stream_online_notification(streamer, stream_data)

                # Attempt to start the recording (this will likely fail since the stream is offline)
                # Use force_mode=True to give it the best chance of working
                recording_started = await self.start_recording(streamer_id, stream_data, force_mode=True)

                if recording_started and streamer_id in self.active_recordings:
                    self.active_recordings[streamer_id]["stream_id"] = stream.id
                    self.active_recordings[streamer_id]["force_started"] = True
                    self.active_recordings[streamer_id]["offline_recording"] = True  # Mark as offline recording
                    
                    logger.warning(f"Offline force recording started for {streamer.username} (stream_id: {stream.id}). This is unusual and may produce no content.")
                    return True
                else:
                    logger.error(f"Failed to start offline recording for {streamer.username}. This is expected since they appear to be offline.")
                    return False

                return recording_started

        except RecordingError:            # Re-raise specific domain exceptions
            raise
        except Exception as e:
            logger.error(f"Error force starting offline recording: {e}", exc_info=True)
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

    async def force_start_recording_with_api_check(
        self, streamer_id: int, stream_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Intelligently start a recording by first checking if the streamer is actually online via API.
        
        This method will:
        1. First check the Twitch API to see if the streamer is actually live
        2. If they are live, start a normal force recording
        3. If they are offline but user still wants to force record (for testing/special cases),
           attempt an offline recording with appropriate warnings
        
        Args:
            streamer_id: ID of the streamer
            stream_data: Optional stream data (if None, will be created based on API response)
            
        Returns:
            bool: True if recording started successfully, False otherwise
        """
        try:
            with SessionLocal() as db:
                streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
                if not streamer:
                    logger.error(f"Streamer not found: {streamer_id}")
                    raise StreamerNotFoundError(f"Streamer not found: {streamer_id}")

                # FIRST: Check if the streamer is actually live via Twitch API
                logger.info(f"Checking Twitch API to see if {streamer.username} is actually live...")
                stream_info = await self._get_stream_info_from_api(streamer, db)

                if stream_info:
                    # Streamer is actually live! Use the normal force recording method
                    logger.info(f"API confirms {streamer.username} is live. Using normal force recording.")
                    return await self.force_start_recording(streamer_id)
                
                # If we get here, the streamer appears to be offline according to the API
                logger.warning(f"API indicates {streamer.username} is offline. Proceeding with offline force recording (this is unusual and may fail).")
                
                # If no stream data was provided, create default data for offline recording
                if not stream_data:
                    stream_data = self._create_stream_data(streamer, None)  # Pass None since they're offline

                # Warn about potential issues with offline recording
                logger.warning(f"Attempting to start recording for {streamer.username} while they appear offline. This may fail because:")
                logger.warning("1. Streamlink may not be able to connect to a non-existent stream")
                logger.warning("2. No actual video content may be available to record")
                logger.warning("3. This should only be used for testing or very special circumstances")

                # Update streamer status to "live" in our database (even though API says offline)
                # This is necessary for our internal logic to work
                self._update_streamer_status(streamer, stream_data, db)

                # Find existing stream or create a new one
                stream = await self._find_or_create_offline_stream(
                    streamer_id, streamer, stream_data, db
                )

                # Create metadata entry if it doesn't exist
                await self._ensure_stream_metadata(stream.id, db)

                # Send WebSocket notification (even though it's an offline recording attempt)
                await self._send_stream_online_notification(streamer, stream_data)

                # Attempt to start the recording (this will likely fail since the stream is offline)
                # Use force_mode=True to give it the best chance of working
                recording_started = await self.start_recording(streamer_id, stream_data, force_mode=True)

                if recording_started and streamer_id in self.active_recordings:
                    self.active_recordings[streamer_id]["stream_id"] = stream.id
                    self.active_recordings[streamer_id]["force_started"] = True
                    self.active_recordings[streamer_id]["offline_recording"] = True  # Mark as offline recording
                    
                    logger.warning(f"Offline force recording started for {streamer.username} (stream_id: {stream.id}). This is unusual and may produce no content.")
                    return True
                else:
                    logger.error(f"Failed to start offline recording for {streamer.username}. This is expected since they appear to be offline.")
                    return False

                return recording_started

        except RecordingError:            # Re-raise specific domain exceptions
            raise
        except Exception as e:
            logger.error(f"Error force starting offline recording: {e}", exc_info=True)
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

    async def force_start_recording_with_api_check(
        self, streamer_id: int, stream_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Intelligently start a recording by first checking if the streamer is actually online via API.
        
        This method will:
        1. First check the Twitch API to see if the streamer is actually live
        2. If they are live, start a normal force recording
        3. If they are offline but user still wants to force record (for testing/special cases),
           attempt an offline recording with appropriate warnings
        
        Args:
            streamer_id: ID of the streamer
            stream_data: Optional stream data (if None, will be created based on API response)
            
        Returns:
            bool: True if recording started successfully, False otherwise
        """
        try:
            with SessionLocal() as db:
                streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
                if not streamer:
                    logger.error(f"Streamer not found: {streamer_id}")
                    raise StreamerNotFoundError(f"Streamer not found: {streamer_id}")

                # FIRST: Check if the streamer is actually live via Twitch API
                logger.info(f"Checking Twitch API to see if {streamer.username} is actually live...")
                stream_info = await self._get_stream_info_from_api(streamer, db)

                if stream_info:
                    # Streamer is actually live! Use the normal force recording method
                    logger.info(f"API confirms {streamer.username} is live. Using normal force recording.")
                    return await self.force_start_recording(streamer_id)
                
                # If we get here, the streamer appears to be offline according to the API
                logger.warning(f"API indicates {streamer.username} is offline. Proceeding with offline force recording (this is unusual and may fail).")
                
                # If no stream data was provided, create default data for offline recording
                if not stream_data:
                    stream_data = self._create_stream_data(streamer, None)  # Pass None since they're offline

                # Warn about potential issues with offline recording
                logger.warning(f"Attempting to start recording for {streamer.username} while they appear offline. This may fail because:")
                logger.warning("1. Streamlink may not be able to connect to a non-existent stream")
                logger.warning("2. No actual video content may be available to record")
                logger.warning("3. This should only be used for testing or very special circumstances")

                # Update streamer status to "live" in our database (even though API says offline)
                # This is necessary for our internal logic to work
                self._update_streamer_status(streamer, stream_data, db)

                # Find existing stream or create a new one
                stream = await self._find_or_create_offline_stream(
                    streamer_id, streamer, stream_data, db
                )

                # Create metadata entry if it doesn't exist
                await self._ensure_stream_metadata(stream.id, db)

                # Send WebSocket notification (even though it's an offline recording attempt)
                await self._send_stream_online_notification(streamer, stream_data)

                # Attempt to start the recording (this will likely fail since the stream is offline)
                # Use force_mode=True to give it the best chance of working
                recording_started = await self.start_recording(streamer_id, stream_data, force_mode=True)

                if recording_started and streamer_id in self.active_recordings:
                    self.active_recordings[streamer_id]["stream_id"] = stream.id
                    self.active_recordings[streamer_id]["force_started"] = True
                    self.active_recordings[streamer_id]["offline_recording"] = True  # Mark as offline recording
                    
                    logger.warning(f"Offline force recording started for {streamer.username} (stream_id: {stream.id}). This is unusual and may produce no content.")
                    return True
                else:
                    logger.error(f"Failed to start offline recording for {streamer.username}. This is expected since they appear to be offline.")
                    return False

                return recording_started

        except RecordingError:            # Re-raise specific domain exceptions
            raise
        except Exception as e:
            logger.error(f"Error force starting offline recording: {e}", exc_info=True)
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

    async def force_start_recording_with_api_check(
        self, streamer_id: int, stream_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Intelligently start a recording by first checking if the streamer is actually online via API.
        
        This method will:
        1. First check the Twitch API to see if the streamer is actually live
        2. If they are live, start a normal force recording
        3. If they are offline but user still wants to force record (for testing/special cases),
           attempt an offline recording with appropriate warnings
        
        Args:
            streamer_id: ID of the streamer
            stream_data: Optional stream data (if None, will be created based on API response)
            
        Returns:
            bool: True if recording started successfully, False otherwise
        """
        try:
            with SessionLocal() as db:
                streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
                if not streamer:
                    logger.error(f"Streamer not found: {streamer_id}")
                    raise StreamerNotFoundError(f"Streamer not found: {streamer_id}")

                # FIRST: Check if the streamer is actually live via Twitch API
                logger.info(f"Checking Twitch API to see if {streamer.username} is actually live...")
                stream_info = await self._get_stream_info_from_api(streamer, db)

                if stream_info:
                    # Streamer is actually live! Use the normal force recording method
                    logger.info(f"API confirms {streamer.username} is live. Using normal force recording.")
                    return await self.force_start_recording(streamer_id)
                
                # If we get here, the streamer appears to be offline according to the API
                logger.warning(f"API indicates {streamer.username} is offline. Proceeding with offline force recording (this is unusual and may fail).")
                
                # If no stream data was provided, create default data for offline recording
                if not stream_data:
                    stream_data = self._create_stream_data(streamer, None)  # Pass None since they're offline

                # Warn about potential issues with offline recording
                logger.warning(f"Attempting to start recording for {streamer.username} while they appear offline. This may fail because:")
                logger.warning("1. Streamlink may not be able to connect to a non-existent stream")
                logger.warning("2. No actual video content may be available to record")
                logger.warning("3. This should only be used for testing or very special circumstances")

                # Update streamer status to "live" in our database (even though API says offline)
                # This is necessary for our internal logic to work
                self._update_streamer_status(streamer, stream_data, db)

                # Find existing stream or create a new one
                stream = await self._find_or_create_offline_stream(
                    streamer_id, streamer, stream_data, db
                )

                # Create metadata entry if it doesn't exist
                await self._ensure_stream_metadata(stream.id, db)

                # Send WebSocket notification (even though it's an offline recording attempt)
                await self._send_stream_online_notification(streamer, stream_data)

                # Attempt to start the recording (this will likely fail since the stream is offline)
                # Use force_mode=True to give it the best chance of working
                recording_started = await self.start_recording(streamer_id, stream_data, force_mode=True)

                if recording_started and streamer_id in self.active_recordings:
                    self.active_recordings[streamer_id]["stream_id"] = stream.id
                    self.active_recordings[streamer_id]["force_started"] = True
                    self.active_recordings[streamer_id]["offline_recording"] = True  # Mark as offline recording
                    
                    logger.warning(f"Offline force recording started for {streamer.username} (stream_id: {stream.id}). This is unusual and may produce no content.")
                    return True
                else:
                    logger.error(f"Failed to start offline recording for {streamer.username}. This is expected since they appear to be offline.")
                    return False

                return recording_started

        except RecordingError:            # Re-raise specific domain exceptions
            raise
        except Exception as e:
            logger.error(f"Error force starting offline recording: {e}", exc_info=True)
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

    async def force_start_recording_with_api_check(
        self, streamer_id: int, stream_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Intelligently start a recording by first checking if the streamer is actually online via API.
        
        This method will:
        1. First check the Twitch API to see if the streamer is actually live
        2. If they are live, start a normal force recording
        3. If they are offline but user still wants to force record (for testing/special cases),
           attempt an offline recording with appropriate warnings
        
        Args:
            streamer_id: ID of the streamer
            stream_data: Optional stream data (if None, will be created based on API response)
            
        Returns:
            bool: True if recording started successfully, False otherwise
        """
        try:
            with SessionLocal() as db:
                streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
                if not streamer:
                    logger.error(f"Streamer not found: {streamer_id}")
                    raise StreamerNotFoundError(f"Streamer not found: {streamer_id}")

                # FIRST: Check if the streamer is actually live via Twitch API
                logger.info(f"Checking Twitch API to see if {streamer.username} is actually live...")
                stream_info = await self._get_stream_info_from_api(streamer, db)

                if stream_info:
                    # Streamer is actually live! Use the normal force recording method
                    logger.info(f"API confirms {streamer.username} is live. Using normal force recording.")
                    return await self.force_start_recording(streamer_id)
                
                # If we get here, the streamer appears to be offline according to the API
                logger.warning(f"API indicates {streamer.username} is offline. Proceeding with offline force recording (this is unusual and may fail).")
                
                # If no stream data was provided, create default data for offline recording
                if not stream_data:
                    stream_data = self._create_stream_data(streamer, None)  # Pass None since they're offline

                # Warn about potential issues with offline recording
                logger.warning(f"Attempting to start recording for {streamer.username} while they appear offline. This may fail because:")
                logger.warning("1. Streamlink may not be able to connect to a non-existent stream")
                logger.warning("2. No actual video content may be available to record")
                logger.warning("3. This should only be used for testing or very special circumstances")

                # Update streamer status to "live" in our database (even though API says offline)
                # This is necessary for our internal logic to work
                self._update_streamer_status(streamer, stream_data, db)

                # Find existing stream or create a new one
                stream = await self._find_or_create_offline_stream(
                    streamer_id, streamer, stream_data, db
                )

                # Create metadata entry if it doesn't exist
                await self._ensure_stream_metadata(stream.id, db)

                # Send WebSocket notification (even though it's an offline recording attempt)
                await self._send_stream_online_notification(streamer, stream_data)

                # Attempt to start the recording (this will likely fail since the stream is offline)
                # Use force_mode=True to give it the best chance of working
                recording_started = await self.start_recording(streamer_id, stream_data, force_mode=True)

                if recording_started and streamer_id in self.active_recordings:
                    self.active_recordings[streamer_id]["stream_id"] = stream.id
                    self.active_recordings[streamer_id]["force_started"] = True
                    self.active_recordings[streamer_id]["offline_recording"] = True  # Mark as offline recording
                    
                    logger.warning(f"Offline force recording started for {streamer.username} (stream_id: {stream.id}). This is unusual and may produce no content.")
                    return True
                else:
                    logger.error(f"Failed to start offline recording for {streamer.username}. This is expected since they appear to be offline.")
                    return False

                return recording_started

        except RecordingError:            # Re-raise specific domain exceptions
            raise
        except Exception as e:
            logger.error(f"Error force starting offline recording: {e}", exc_info=True)
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


    async def force_start_recording_with_api_check(
        self, streamer_id: int, stream_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Intelligently start a recording by first checking if the streamer is actually online via API.
        
        This method will:
        1. First check the Twitch API to see if the streamer is actually live
        2. If they are live, start a normal force recording
        3. If they are offline but user still wants to force record (for testing/special cases),
           attempt an offline recording with appropriate warnings
        
        Args:
            streamer_id: ID of the streamer
            stream_data: Optional stream data (if None, will be created based on API response)
            
        Returns:
            bool: True if recording started successfully, False otherwise
        """
        try:
            with SessionLocal() as db:
                streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
                if not streamer:
                    logger.error(f"Streamer not found: {streamer_id}")
                    raise StreamerNotFoundError(f"Streamer not found: {streamer_id}")

                # FIRST: Check if the streamer is actually live via Twitch API
                logger.info(f"Checking Twitch API to see if {streamer.username} is actually live...")
                stream_info = await self._get_stream_info_from_api(streamer, db)

                if stream_info:
                    # Streamer is actually live! Use the normal force recording method
                    logger.info(f"API confirms {streamer.username} is live. Using normal force recording.")
                    return await self.force_start_recording(streamer_id)
                
                # If we get here, the streamer appears to be offline according to the API
                logger.warning(f"API indicates {streamer.username} is offline. Proceeding with offline force recording (this is unusual and may fail).")
                
                # If no stream data was provided, create default data for offline recording
                if not stream_data:
                    stream_data = self._create_stream_data(streamer, None)  # Pass None since they're offline

                # Warn about potential issues with offline recording
                logger.warning(f"Attempting to start recording for {streamer.username} while they appear offline. This may fail because:")
                logger.warning("1. Streamlink may not be able to connect to a non-existent stream")
                logger.warning("2. No actual video content may be available to record")
                logger.warning("3. This should only be used for testing or very special circumstances")

                # Update streamer status to "live" in our database (even though API says offline)
                # This is necessary for our internal logic to work
                self._update_streamer_status(streamer, stream_data, db)

                # Find existing stream or create a new one
                stream = await self._find_or_create_offline_stream(
                    streamer_id, streamer, stream_data, db
                )

                # Create metadata entry if it doesn't exist
                await self._ensure_stream_metadata(stream.id, db)

                # Send WebSocket notification (even though it's an offline recording attempt)
                await self._send_stream_online_notification(streamer, stream_data)

                # Attempt to start the recording (this will likely fail since the stream is offline)
                # Use force_mode=True to give it the best chance of working
                recording_started = await self.start_recording(streamer_id, stream_data, force_mode=True)

                if recording_started and streamer_id in self.active_recordings:
                    self.active_recordings[streamer_id]["stream_id"] = stream.id
                    self.active_recordings[streamer_id]["force_started"] = True
                    self.active_recordings[streamer_id]["offline_recording"] = True  # Mark as offline recording
                    
                    logger.warning(f"Offline force recording started for {streamer.username} (stream_id: {stream.id}). This is unusual and may produce no content.")
                    return True
                else:
                    logger.error(f"Failed to start offline recording for {streamer.username}. This is expected since they appear to be offline.")
                    return False

                return recording_started

        except RecordingError:            # Re-raise specific domain exceptions
            raise
        except Exception as e:
            logger.error(f"Error force starting offline recording: {e}", exc_info=True)
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

    async def _generate_chapters_file_for_stream(self, stream_id: int, chapters_path: str, streamer_name: str):
        """Generate FFmpeg chapters file from stream events."""
        try:
            logger.info(f"Generating chapters file for stream {stream_id}: {chapters_path}")
            
            # Get stream events from database
            with next(get_db()) as db:
                events = db.query(StreamEvent).filter(
                    StreamEvent.stream_id == stream_id
                ).order_by(StreamEvent.timestamp).all()
            
            if not events:
                logger.info(f"No events found for stream {stream_id}, creating basic chapters file")
                await self._create_basic_chapters_file(chapters_path, streamer_name)
                return
            
            logger.info(f"Found {len(events)} events for stream {stream_id}")
            
            # Create FFmpeg chapters format
            chapters_content = ";FFMETADATA1\n"
            chapters_content += f"title={streamer_name} Stream\n"
            chapters_content += f"encoder=StreamVault\n\n"
            
            # Process events to create chapters
            for i, event in enumerate(events):
                # Calculate timebase (FFmpeg uses milliseconds * 1000 for timebase)
                timestamp_ms = int(event.timestamp.timestamp() * 1000)
                timebase = timestamp_ms * 1000  # Convert to FFmpeg timebase
                
                chapters_content += "[CHAPTER]\n"
                chapters_content += "TIMEBASE=1/1000000\n"  # Microseconds
                chapters_content += f"START={timebase}\n"
                
                # Calculate end time (next event or add 30 seconds for last event)
                if i + 1 < len(events):
                    next_timestamp_ms = int(events[i + 1].timestamp.timestamp() * 1000)
                    end_timebase = next_timestamp_ms * 1000
                else:
                    # For last event, add 30 seconds
                    end_timebase = timebase + (30 * 1000 * 1000)  # 30 seconds in microseconds
                
                chapters_content += f"END={end_timebase}\n"
                chapters_content += f"title={event.event_type}: {event.event_data.get('title', 'Event')}\n\n"
            
            # Write chapters file
            with open(chapters_path, 'w', encoding='utf-8') as f:
                f.write(chapters_content)
            
            logger.info(f"Successfully generated chapters file with {len(events)} chapters: {chapters_path}")
            
        except Exception as e:
            logger.error(f"Failed to generate chapters file for stream {stream_id}: {e}")
            # Fallback to basic chapters file
            await self._create_basic_chapters_file(chapters_path, streamer_name)

    async def _create_basic_chapters_file(self, chapters_path: str, streamer_name: str):
        """Create a basic FFmpeg chapters file with minimal metadata."""
        try:
            logger.info(f"Creating basic chapters file: {chapters_path}")
            
            # Create basic FFmpeg metadata format
            chapters_content = ";FFMETADATA1\n"
            chapters_content += f"title={streamer_name} Stream\n"
            chapters_content += f"encoder=StreamVault\n"
            chapters_content += f"artist={streamer_name}\n"
            chapters_content += f"date={datetime.now().strftime('%Y-%m-%d')}\n"
            chapters_content += f"comment=Recorded by StreamVault\n\n"
            
            # Add one basic chapter for the entire stream
            chapters_content += "[CHAPTER]\n"
            chapters_content += "TIMEBASE=1/1000000\n"  # Microseconds
            chapters_content += "START=0\n"
            chapters_content += "END=9999999999\n"  # Large end time to cover entire stream
            chapters_content += f"title={streamer_name} Stream Recording\n\n"
            
            # Write chapters file
            with open(chapters_path, 'w', encoding='utf-8') as f:
                f.write(chapters_content)
            
            logger.info(f"Successfully created basic chapters file: {chapters_path}")
            
        except Exception as e:
            logger.error(f"Failed to create basic chapters file: {e}")
            # Create empty file as absolute fallback
            try:
                with open(chapters_path, 'w', encoding='utf-8') as f:
                    f.write(";FFMETADATA1\n")
                logger.info(f"Created minimal chapters file as fallback: {chapters_path}")
            except Exception as fallback_e:
                logger.error(f"Even fallback chapters file creation failed: {fallback_e}")

