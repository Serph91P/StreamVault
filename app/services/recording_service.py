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
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Optional, List, Any, Tuple, Callable
from sqlalchemy import extract
from functools import lru_cache
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models import Streamer, RecordingSettings, StreamerRecordingSettings, Stream, StreamEvent, StreamMetadata
from app.config.settings import settings
from app.services.metadata_service import MetadataService
from app.dependencies import websocket_manager

logger = logging.getLogger("streamvault")

# Define performance monitoring decorators
def timing_decorator(func):
    """Decorator to log execution time of functions"""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        operation_id = kwargs.pop('operation_id', str(uuid.uuid4())[:8])
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
            logger.error(f"[{operation_id}] {method_name} failed after {elapsed:.2f}s: {e}")
            raise
            
    return wrapper

def sync_timing_decorator(func):
    """Decorator to log execution time of synchronous functions"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        operation_id = kwargs.pop('operation_id', str(uuid.uuid4())[:8])
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
            logger.error(f"[{operation_id}] {method_name} failed after {elapsed:.2f}s: {e}")
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
    
    def get_streamer_settings(self, streamer_id: int) -> Optional[StreamerRecordingSettings]:
        """Get streamer-specific recording settings, using cache if valid"""
        if streamer_id not in self._streamer_settings or not self._is_cache_valid():
            with SessionLocal() as db:
                settings = db.query(StreamerRecordingSettings).filter(
                    StreamerRecordingSettings.streamer_id == streamer_id
                ).first()
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

# Subprocess manager for better resource handling
class SubprocessManager:
    """Manages subprocess execution and cleanup"""
    
    def __init__(self):
        self.active_processes = {}
        self.lock = asyncio.Lock()
        
    async def start_process(self, cmd: List[str], process_id: str) -> Optional[asyncio.subprocess.Process]:
        """Start a subprocess and track it"""
        async with self.lock:
            try:
                logger.debug(f"Starting process {process_id}: {' '.join(cmd)}")
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                self.active_processes[process_id] = process
                return process
            except Exception as e:
                logger.error(f"Failed to start process {process_id}: {e}", exc_info=True)
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
                    logger.warning(f"Process {process_id} did not terminate gracefully, killing")
                    process.kill()
                    await process.wait()
                
                self.active_processes.pop(process_id)
                return True
            except Exception as e:
                logger.error(f"Error terminating process {process_id}: {e}", exc_info=True)
                return False
    
    async def cleanup_all(self):
        """Terminate all active processes"""
        process_ids = list(self.active_processes.keys())
        for process_id in process_ids:
            await self.terminate_process(process_id)

# At the top of the file, add this to make RecordingService a singleton
class RecordingService:
    _instance = None  # Make this a class attribute
    
    def __new__(cls, metadata_service=None, config_manager=None, subprocess_manager=None):
        if cls._instance is None:
            cls._instance = super(RecordingService, cls).__new__(cls)
            cls._instance.active_recordings = {}
            cls._instance.lock = asyncio.Lock()
            cls._instance.metadata_service = metadata_service or MetadataService()
            cls._instance.config_manager = config_manager or ConfigManager()
            cls._instance.subprocess_manager = subprocess_manager or SubprocessManager()
            cls._instance.initialized = True
        return cls._instance

    def __init__(self, metadata_service=None, config_manager=None, subprocess_manager=None):
        # Only initialize once and allow dependency injection
        if not hasattr(self, 'initialized'):
            self.initialized = True
            # Dependencies are now injected in __new__

    async def get_active_recordings(self) -> List[Dict[str, Any]]:
        """Get a list of all active recordings"""
        async with self.lock:
            # Add verbose logging for debugging
            logger.debug(f"RECORDING STATUS: get_active_recordings called, keys: {list(self.active_recordings.keys())}")
            
            result = [
                {
                    "streamer_id": int(streamer_id),  # Ensure integer type
                    "streamer_name": info["streamer_name"],
                    "started_at": info["started_at"].isoformat() if isinstance(info["started_at"], datetime) else info["started_at"],
                    "duration": (datetime.now() - info["started_at"]).total_seconds() if isinstance(info["started_at"], datetime) else 0,
                    "output_path": info["output_path"],
                    "quality": info["quality"]
                }
                for streamer_id, info in self.active_recordings.items()
            ]
            
            logger.debug(f"RECORDING STATUS: Returning {len(result)} active recordings")
            return result

    async def start_recording(self, streamer_id: int, stream_data: Dict[str, Any]) -> bool:
        """Start recording a stream"""
        async with self.lock:
            # Convert streamer_id to integer for consistency
            streamer_id = int(streamer_id)
            
            if streamer_id in self.active_recordings:
                logger.debug(f"Recording already active for streamer {streamer_id}")
                raise RecordingAlreadyActiveError(f"Recording already active for streamer {streamer_id}")
                
            try:
                with SessionLocal() as db:
                    streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
                    if not streamer:
                        logger.error(f"Streamer not found: {streamer_id}")
                        raise StreamerNotFoundError(f"Streamer not found: {streamer_id}")
                    
                    # Check if recording is enabled using config manager
                    if not self.config_manager.is_recording_enabled(streamer_id):
                        logger.debug(f"Recording disabled for streamer {streamer.username}")
                        return False
                    
                    # Get quality setting from config manager
                    quality = self.config_manager.get_quality_setting(streamer_id)
                    
                    # Get filename template from config manager
                    template = self.config_manager.get_filename_template(streamer_id)
                    
                    # Generate output filename
                    filename = self._generate_filename(
                        streamer=streamer,
                        stream_data=stream_data,
                        template=template
                    )
                    
                    # Get output directory from global settings
                    global_settings = self.config_manager.get_global_settings()
                    output_path = os.path.join(global_settings.output_directory, filename)
                    os.makedirs(os.path.dirname(output_path), exist_ok=True)
                    
                    # Start streamlink process using subprocess manager
                    process = await self._start_streamlink(
                        streamer_name=streamer.username,
                        quality=quality,
                        output_path=output_path
                    )
                    
                    if process:
                        self.active_recordings[streamer_id] = {
                            "process": process,
                            "started_at": datetime.now(),
                            "output_path": output_path,
                            "streamer_name": streamer.username,
                            "quality": quality,
                            "stream_id": None,  # Will be updated when we find/create the stream
                            "process_id": f"streamlink_{streamer_id}"  # ID for subprocess manager
                        }
                        
                        # More verbose and consistent logging
                        logger.info(f"Recording started - Added to active_recordings with key {streamer_id}")
                        logger.info(f"Current active recordings: {list(self.active_recordings.keys())}")
                        
                        logger.info(f"Started recording for {streamer.username} at {quality} quality to {output_path}")
                        await websocket_manager.send_notification({
                            "type": "recording.started",
                            "data": {
                                "streamer_id": streamer_id,
                                "streamer_name": streamer.username,
                                "started_at": datetime.now().isoformat(),
                                "quality": quality,
                                "output_path": output_path
                            }
                        })
                        
                        # Find or create stream record and metadata
                        await self._setup_stream_metadata(streamer_id, streamer, output_path)
                        
                        return True
                        
                    return False
            except RecordingError:
                # Re-raise specific domain exceptions
                raise
            except Exception as e:
                logger.error(f"Error starting recording: {e}", exc_info=True)
                return False
    
    async def _setup_stream_metadata(self, streamer_id: int, streamer: Streamer, output_path: str):
        """Set up stream record and metadata for a recording"""
        try:
            with SessionLocal() as db:
                # Find the current stream record
                stream = db.query(Stream).filter(
                    Stream.streamer_id == streamer_id,
                    Stream.ended_at.is_(None)
                ).order_by(Stream.started_at.desc()).first()
                
                if stream:
                    # Create metadata record if it doesn't exist
                    metadata = db.query(StreamMetadata).filter(
                        StreamMetadata.stream_id == stream.id
                    ).first()
                    
                    if not metadata:
                        metadata = StreamMetadata(stream_id=stream.id)
                        db.add(metadata)
                        db.commit()
                    
                    # Update our recording info with stream ID
                    self.active_recordings[streamer_id]["stream_id"] = stream.id
                    
                    # Download Twitch thumbnail asynchronously
                    output_dir = os.path.dirname(output_path)
                    asyncio.create_task(
                        self.metadata_service.download_twitch_thumbnail(
                            streamer.username, 
                            stream.id, 
                            output_dir
                        )
                    )
        except Exception as e:
            logger.error(f"Error setting up stream metadata: {e}")
    
    async def stop_recording(self, streamer_id: int) -> bool:
        """Stop an active recording and ensure metadata generation"""
        async with self.lock:
            if streamer_id not in self.active_recordings:
                logger.debug(f"No active recording for streamer {streamer_id}")
                return False
            
            try:
                recording_info = self.active_recordings.pop(streamer_id)
                process_id = recording_info.get("process_id", f"streamlink_{streamer_id}")
                
                # Use subprocess manager to terminate the process
                await self.subprocess_manager.terminate_process(process_id)
                
                logger.info(f"Stopped recording for {recording_info['streamer_name']}")

                await websocket_manager.send_notification({
                    "type": "recording.stopped",
                    "data": {
                        "streamer_id": streamer_id,
                        "streamer_name": recording_info['streamer_name']
                    }
                })
                
                # Get stream ID and "force_started" flag
                stream_id = recording_info.get("stream_id")
                force_started = recording_info.get("force_started", False)
                
                # Ensure we have a stream
                if not stream_id and force_started:
                    stream_id = await self._find_stream_for_recording(streamer_id)
                
                # Generate metadata after recording stops
                if stream_id:
                    # Allow some time for the remuxing process to complete
                    asyncio.create_task(self._delayed_metadata_generation(
                        stream_id, 
                        recording_info["output_path"],
                        force_started
                    ))
                else:
                    logger.warning(f"No stream_id available for metadata generation: {recording_info}")
                
                return True
            except Exception as e:
                logger.error(f"Error stopping recording: {e}", exc_info=True)
                return False
    
    async def _find_stream_for_recording(self, streamer_id: int) -> Optional[int]:
        """Find a stream record for a recording that was force-started"""
        try:
            with SessionLocal() as db:
                streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
                if streamer:
                    # For force-recordings: Try to find a stream
                    stream = db.query(Stream).filter(
                        Stream.streamer_id == streamer_id
                    ).order_by(Stream.started_at.desc()).first()
                    
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
                    raise StreamerNotFoundError(f"Streamer not found: {streamer_id}")
                
                # Check if the streamer is live via Twitch API
                stream_info = await self._get_stream_info_from_api(streamer, db)
                
                if not stream_info:
                    logger.error(f"Streamer {streamer.username} is not live according to Twitch API")
                    return False
                
                # Find or create stream record
                stream = await self._find_or_create_stream(streamer_id, streamer, db)
                
                # IMPORTANT: Store the ID while we're still in the session
                stream_id = stream.id
                
                # Prepare stream data for recording
                stream_data = self._prepare_stream_data(streamer, stream)
                
                # Check if we already have a recording
                if streamer_id in self.active_recordings:
                    logger.info(f"Recording already in progress for {streamer.username}")
                    return True
                
                # Get recording settings to check if this streamer has recordings enabled
                recording_enabled = self.config_manager.is_recording_enabled(streamer_id)
                
                if not recording_enabled:
                    # If recordings are disabled for this streamer, temporarily enable it just for this session
                    logger.info(f"Recordings are disabled for {streamer.username}, but force recording was requested. Proceeding with recording.")
                    
                    # Create a temporary copy of the actual settings for this recording session
                    streamer_settings = self.config_manager.get_streamer_settings(streamer_id)
                    
                    # We'll store the original 'enabled' value to restore it later if needed
                    original_setting = False
                    if streamer_settings:
                        original_setting = streamer_settings.enabled
                    
                    # Override recording settings for this particular session
                    temp_settings = db.query(StreamerRecordingSettings).filter(
                        StreamerRecordingSettings.streamer_id == streamer_id
                    ).first()
                    
                    if not temp_settings:
                        temp_settings = StreamerRecordingSettings(streamer_id=streamer_id)
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
                # Start recording with existing method (which will now use the temporarily enabled setting)
                recording_started = await self.start_recording(streamer_id, stream_data)
                
                # Save the stream ID and force started flag in the recording information
                if recording_started and streamer_id in self.active_recordings:
                    self.active_recordings[streamer_id]["stream_id"] = stream_id
                    self.active_recordings[streamer_id]["force_started"] = True
                    
                    # Record that this was a forced recording (to handle special case on stop)
                    self.active_recordings[streamer_id]["forced_recording"] = True
                    
                    logger.info(f"Force recording started for {streamer.username}, stream_id: {stream_id}")
                    
                    return True
                
                return recording_started
            
            return False
            
        except RecordingError:
            # Re-raise specific domain exceptions
            raise
        except Exception as e:
            logger.error(f"Error force starting recording: {e}", exc_info=True)
            return False
    
    async def _find_or_create_stream(self, streamer_id: int, streamer: Streamer, db) -> Stream:
        """Find an existing stream or create a new one"""
        # Find current stream
        stream = db.query(Stream).filter(
            Stream.streamer_id == streamer_id,
            Stream.ended_at.is_(None)
        ).order_by(Stream.started_at.desc()).first()
        
        if not stream:
            # Create stream entry if none exists
            logger.info(f"Creating new stream record for {streamer.username}")
            stream = Stream(
                streamer_id=streamer_id,
                twitch_stream_id=f"manual_{int(datetime.now().timestamp())}",
                title=streamer.title or f"{streamer.username} Stream",
                category_name=streamer.category_name,
                language=streamer.language,
                started_at=datetime.now(timezone.utc),
                status="online"
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
                category_name=stream.category_name
            )
            db.add(stream_event)
            db.commit()
        
        return stream
    
    def _prepare_stream_data(self, streamer: Streamer, stream: Stream) -> Dict[str, Any]:
        """Prepare stream data for recording"""
        return {
            "id": stream.twitch_stream_id,
            "broadcaster_user_id": streamer.twitch_id,
            "broadcaster_user_name": streamer.username,
            "started_at": stream.started_at.isoformat() if stream.started_at else datetime.now().isoformat(),
            "title": stream.title,
            "category_name": stream.category_name,
            "language": stream.language
        }
    
    async def force_start_recording_offline(self, streamer_id: int, stream_data: dict = None) -> bool:
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
                stream = await self._find_or_create_offline_stream(streamer_id, streamer, stream_data, db)
                
                # Create metadata entry if it doesn't exist
                await self._ensure_stream_metadata(stream.id, db)
                
                # Send WebSocket notification
                await self._send_stream_online_notification(streamer, stream_data)
                
                # Start the recording with the existing method
                recording_started = await self.start_recording(streamer_id, stream_data)
                
                # Save the stream ID in the recording information
                if recording_started and streamer_id in self.active_recordings:
                    # Try to download a Twitch thumbnail
                    output_dir = os.path.dirname(self.active_recordings[streamer_id]["output_path"])
                    asyncio.create_task(
                        self.metadata_service.download_twitch_thumbnail(
                            streamer.username, 
                            stream.id, 
                            output_dir
                        )
                    )
                
                    logger.info(f"Force offline recording started for {streamer.username}, stream_id: {stream.id}")
                    return True
            
                return recording_started
            
        except RecordingError:
            # Re-raise specific domain exceptions
            raise
        except Exception as e:
            logger.error(f"Error force starting offline recording: {e}", exc_info=True)
            return False
    
    async def _get_stream_info_from_api(self, streamer: Streamer, db) -> Optional[Dict[str, Any]]:
        """Get stream information from Twitch API to verify if streamer is live"""
        try:
            # Import here to avoid circular dependencies
            from app.services.streamer_service import StreamerService
            
            # Create streamer service for API query
            streamer_service = StreamerService(
                db=db, 
                websocket_manager=None,  # Not needed for this specific call
                event_registry=None      # Not needed for this specific call
            )
            
            # Query Twitch API for stream info using the new method
            stream_info = await streamer_service.get_stream_info(streamer.twitch_id)
            
            if stream_info:
                logger.info(f"Confirmed {streamer.username} is live via Twitch API")
                return stream_info
            else:
                logger.warning(f"Streamer {streamer.username} appears to be offline according to Twitch API")
                return None
                
        except Exception as e:
            logger.error(f"Error checking stream status via API: {e}")
            return None
    
    def _create_stream_data(self, streamer: Streamer, stream_info: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Create stream data from streamer and API info"""
        if stream_info:
            # Streamer is actually live, use API data
            return {
                "id": stream_info.get("id"),
                "broadcaster_user_id": streamer.twitch_id,
                "broadcaster_user_name": streamer.username,
                "started_at": stream_info.get("started_at") or datetime.now(timezone.utc).isoformat(),
                "title": stream_info.get("title") or streamer.title,
                "category_name": stream_info.get("game_name") or streamer.category_name,
                "language": stream_info.get("language") or streamer.language
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
                "language": streamer.language or "en"
            }
    
    def _update_streamer_status(self, streamer: Streamer, stream_data: Dict[str, Any], db):
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
    
    async def _find_or_create_offline_stream(self, streamer_id: int, streamer: Streamer, 
                                            stream_data: Dict[str, Any], db) -> Stream:
        """Find existing active stream or create a new one"""
        # Check if an active stream already exists
        existing_stream = db.query(Stream).filter(
            Stream.streamer_id == streamer_id,
            Stream.ended_at.is_(None)
        ).order_by(Stream.started_at.desc()).first()
        
        if existing_stream:
            logger.info(f"Found existing active stream for {streamer.username}, using it")
            return existing_stream
        
        # Create a new stream entry
        started_at = datetime.fromisoformat(stream_data["started_at"].replace('Z', '+00:00')) \
                    if "started_at" in stream_data else datetime.now(timezone.utc)
        
        stream = Stream(
            streamer_id=streamer_id,
            twitch_stream_id=stream_data.get("id", f"manual_{int(datetime.now().timestamp())}"),
            title=stream_data.get("title") or f"{streamer.username} Stream",
            category_name=stream_data.get("category_name"),
            language=stream_data.get("language"),
            started_at=started_at,
            status="online"
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
            timestamp=started_at
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
                timestamp=started_at - timedelta(seconds=1)
            )
            db.add(category_event)
        
        db.commit()
        return stream
    
    async def _ensure_stream_metadata(self, stream_id: int, db):
        """Ensure metadata entry exists for a stream"""
        metadata = db.query(StreamMetadata).filter(
            StreamMetadata.stream_id == stream_id
        ).first()
        
        if not metadata:
            metadata = StreamMetadata(stream_id=stream_id)
            db.add(metadata)
            db.commit()
        
        return metadata
    
    async def _send_stream_online_notification(self, streamer: Streamer, stream_data: Dict[str, Any]):
        """Send WebSocket notification for stream online event"""
        await websocket_manager.send_notification({
            "type": "stream.online",
            "data": {
                "streamer_id": streamer.id,
                "twitch_id": streamer.twitch_id,
                "streamer_name": streamer.username,
                "started_at": stream_data.get("started_at", datetime.now(timezone.utc).isoformat()),
                "title": stream_data.get("title"),
                "category_name": stream_data.get("category_name"),
                "language": stream_data.get("language")
            }
        })
    
    async def _delayed_metadata_generation(self, stream_id: int, output_path: str, force_started: bool = False, delay: int = 5):
        """Wait for remuxing to complete before generating metadata"""
        try:
            await asyncio.sleep(delay)  # Short delay to ensure remuxing has started
            
            # Find and validate the MP4 file
            mp4_path = await self._find_and_validate_mp4(output_path)
            if not mp4_path:
                return
            
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
        if output_path.endswith('.ts'):
            mp4_path = output_path.replace('.ts', '.mp4')
        
        # Wait for the MP4 file to exist with a timeout
        start_time = datetime.now()
        while not os.path.exists(mp4_path):
            if (datetime.now() - start_time).total_seconds() > 300:  # 5 minute timeout
                logger.warning(f"Timed out waiting for MP4 file: {mp4_path}")
                # Try using TS file directly if MP4 wasn't created
                if os.path.exists(output_path) and output_path.endswith('.ts'):
                    mp4_path = output_path
                    logger.info(f"Using TS file directly for metadata: {mp4_path}")
                    break
                return None
            await asyncio.sleep(5)
        
        # Additional wait time to ensure the file is completely written
        await asyncio.sleep(10)
        
        # Verify that the MP4 file is valid
        if mp4_path.endswith('.mp4'):
            is_valid = await self._validate_mp4(mp4_path)
            if not is_valid:
                logger.warning(f"MP4 file is not valid, attempting repair: {mp4_path}")
                repaired = await self._repair_mp4(
                    output_path.replace('.mp4', '.ts') if os.path.exists(output_path.replace('.mp4', '.ts')) else output_path, 
                    mp4_path
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
                raise StreamNotFoundError(f"Stream {stream_id} not found for metadata generation")
            
            # Ensure stream is marked as ended
            if force_started or not stream.ended_at:
                stream.ended_at = datetime.now(timezone.utc)
                stream.status = "offline"
                
                # Check if there are any stream events
                events_count = db.query(StreamEvent).filter(StreamEvent.stream_id == stream_id).count()
                
                # If no events, add at least one event for the stream's category
                if events_count == 0 and stream.category_name:
                    logger.info(f"No events found for stream {stream_id}, adding initial category event")
                    
                    # Add an event for the stream's category at stream start time
                    category_event = StreamEvent(
                        stream_id=stream_id,
                        event_type="channel.update",
                        title=stream.title,
                        category_name=stream.category_name,
                        language=stream.language,
                        timestamp=stream.started_at
                    )
                    db.add(category_event)
                    
                    # And also add the stream.online event
                    start_event = StreamEvent(
                        stream_id=stream_id,
                        event_type="stream.online",
                        title=stream.title,
                        category_name=stream.category_name,
                        language=stream.language,
                        timestamp=stream.started_at + timedelta(seconds=1)  # 1 second after start
                    )
                    db.add(start_event)
                db.commit()
                logger.info(f"Stream {stream_id} marked as ended for metadata generation")
    
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
            ffmpeg_chapters_path = mp4_path.replace('.mp4', '-ffmpeg-chapters.txt')
            
            # Embed all metadata (including chapters if available) in one step
            if os.path.exists(ffmpeg_chapters_path) and os.path.getsize(ffmpeg_chapters_path) > 0:
                logger.info(f"Embedding all metadata and chapters into MP4 file for stream {stream_id}")
                await metadata_service.embed_all_metadata(mp4_path, ffmpeg_chapters_path, stream_id)
            else:
                logger.warning(f"FFmpeg chapters file not found or empty: {ffmpeg_chapters_path}")
                logger.info(f"Embedding basic metadata without chapters")
                await metadata_service.embed_all_metadata(mp4_path, "", stream_id)
            
        finally:
            # Close the metadata session
            await metadata_service.close()
    
    async def _start_streamlink(self, streamer_name: str, quality: str, output_path: str) -> Optional[asyncio.subprocess.Process]:
        """Start streamlink process for recording with TS format and post-processing to MP4"""
        try:
            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
            # Use .ts as intermediate format for better recovery
            ts_output_path = output_path.replace('.mp4', '.ts')
    
            # Adjust the quality string for better resolution selection
            adjusted_quality = quality
            if quality == "best":
                # Use a more specific quality selection string to prioritize highest resolution
                adjusted_quality = "1080p60,1080p,best"
        
            # Streamlink command with optimized settings based on current documentation
            cmd = [
                "streamlink",
                f"twitch.tv/{streamer_name}",
                quality,
                "-o", ts_output_path,
                "--twitch-disable-ads",
                "--hls-live-restart",
                "--stream-segment-threads", "4",
                "--ringbuffer-size", "128M",
                "--stream-segment-timeout", "20",
                "--stream-segment-attempts", "10",
                "--stream-timeout", "120",
                "--retry-streams", "5",
                "--retry-max", "10",
                "--retry-open", "10",
                "--hls-segment-stream-data",
                "--force"
            ]
                    
            logger.debug(f"Starting streamlink: {' '.join(cmd)}")
            
            # Use subprocess manager to start the process
            process_id = f"streamlink_{streamer_name}_{int(datetime.now().timestamp())}"
            process = await self.subprocess_manager.start_process(cmd, process_id)
            
            if process:
                # Start monitoring the process output in the background
                asyncio.create_task(self._monitor_process(process, process_id, streamer_name, ts_output_path, output_path))
            
            return process
        except Exception as e:
            logger.error(f"Failed to start streamlink: {e}", exc_info=True)
            return None
    
    async def _monitor_process(self, process: asyncio.subprocess.Process, process_id: str, 
                    streamer_name: str, ts_path: str, mp4_path: str) -> None:
        """Monitor recording process and convert TS to MP4 when finished"""
        try:
            stdout, stderr = await process.communicate()
            exit_code = process.returncode
        
            if exit_code == 0 or exit_code == 130:  # 130 is SIGINT (user interruption)
                logger.info(f"Streamlink finished for {streamer_name}, converting TS to MP4")
                # Only remux if TS file exists and has content
                if os.path.exists(ts_path) and os.path.getsize(ts_path) > 0:
                    await self._remux_to_mp4(ts_path, mp4_path)
                else:
                    logger.warning(f"No valid TS file found at {ts_path} for remuxing")
            else:
                stderr_text = stderr.decode('utf-8', errors='ignore') if stderr else "No error output"
                logger.error(f"Streamlink process for {streamer_name} exited with code {exit_code}: {stderr_text}")
                # Try to remux anyway if file exists, it might be partially usable
                if os.path.exists(ts_path) and os.path.getsize(ts_path) > 1000000:  # At least 1MB
                    logger.info(f"Attempting to remux partial recording for {streamer_name}")
                    await self._remux_to_mp4(ts_path, mp4_path)
            
            # Remove the process from subprocess manager
            await self.subprocess_manager.terminate_process(process_id)
        except Exception as e:
            logger.error(f"Error monitoring process: {e}", exc_info=True)

    async def _remux_to_mp4(self, ts_path: str, mp4_path: str) -> bool:
        """Remux TS file to MP4 without re-encoding to preserve quality"""
        try:
            # Enhanced remux settings with guaranteed working audio handling
            cmd = [
                "ffmpeg",
                "-fflags", "+genpts",  # Generate presentation timestamps
                "-i", ts_path,
                "-c:v", "copy",        # Copy video stream
                "-c:a", "aac",         # WICHTIGE ÄNDERUNG: Re-encode audio to AAC
                "-b:a", "160k",        # Definierter Bitrate für Audio
                "-map", "0:v:0",       # Nur den ersten Video-Stream verwenden
                "-map", "0:a:0?",      # Ersten Audio-Stream (optional)
                "-ignore_unknown",     
                "-movflags", "+faststart",
                "-metadata", "encoded_by=StreamVault",
                "-metadata", "encoding_tool=StreamVault",
                "-y",
                mp4_path
            ]

            logger.debug(f"Starting enhanced FFmpeg remux: {' '.join(cmd)}")
            
            # Use subprocess manager for the remux process
            process_id = f"ffmpeg_remux_{int(datetime.now().timestamp())}"
            process = await self.subprocess_manager.start_process(cmd, process_id)
        
            stdout, stderr = await process.communicate()
        
            if process.returncode == 0:
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
                stderr_text = stderr.decode('utf-8', errors='ignore') if stderr else "No error output"
                logger.error(f"FFmpeg remux failed with code {process.returncode}: {stderr_text}")
            
                # Try with fallback method if the first attempt failed
                return await self._remux_to_mp4_fallback(ts_path, mp4_path)
        except Exception as e:
            logger.error(f"Error during remux: {e}", exc_info=True)
            return False
        finally:
            # Clean up the process
            await self.subprocess_manager.terminate_process(f"ffmpeg_remux_{int(datetime.now().timestamp())}")

    async def _remux_to_mp4_fallback(self, ts_path: str, mp4_path: str) -> bool:
        try:
            logger.info("Using advanced fallback method for remuxing")
        
            # Try two-step process: extract streams then recombine
            video_path = f"{ts_path}.h264"
            audio_path = f"{ts_path}.aac"
        
            # Step 1: Extract streams
            extract_cmd = [
                "ffmpeg",
                "-i", ts_path,
                "-map", "0:v:0", "-c:v", "copy", "-f", "h264", video_path,
                "-map", "0:a:0", "-c:a", "aac", "-b:a", "128k", "-f", "adts", audio_path,
                "-y"
            ]
        
            process_id = f"ffmpeg_extract_{int(datetime.now().timestamp())}"
            process = await self.subprocess_manager.start_process(extract_cmd, process_id)
            await process.communicate()
            await self.subprocess_manager.terminate_process(process_id)
        
            # Step 2: Recombine to MP4
            if os.path.exists(video_path) and os.path.getsize(video_path) > 0:
                combine_cmd = [
                    "ffmpeg",
                    "-i", video_path
                ]
            
                # Only add audio if it exists
                if os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
                    combine_cmd.extend(["-i", audio_path])
            
                combine_cmd.extend([
                    "-c:v", "copy",
                    "-c:a", "copy",
                    "-movflags", "+faststart",
                    "-y",
                    mp4_path
                ])
            
                process_id = f"ffmpeg_combine_{int(datetime.now().timestamp())}"
                process = await self.subprocess_manager.start_process(combine_cmd, process_id)
                stdout, stderr = await process.communicate()
                await self.subprocess_manager.terminate_process(process_id)
            
                # Clean up temp files
                if os.path.exists(video_path):
                    os.remove(video_path)
                if os.path.exists(audio_path):
                    os.remove(audio_path)
            
                # Check if successful
                if process.returncode == 0 and os.path.exists(mp4_path) and os.path.getsize(mp4_path) > 0:
                    logger.info(f"Successfully remuxed using advanced fallback method: {mp4_path}")
                
                    # Delete original TS file
                    if os.path.exists(ts_path):
                        os.remove(ts_path)
                    return True
        
            # If we're here, try the simplest possible method as last resort
            logger.warning("Advanced fallback failed, trying simple fallback method")
        
            simple_cmd = [
                "ffmpeg",
                "-i", ts_path,
                "-c:v", "copy",
                "-y",
                mp4_path
            ]
        
            process_id = f"ffmpeg_simple_{int(datetime.now().timestamp())}"
            process = await self.subprocess_manager.start_process(simple_cmd, process_id)
            stdout, stderr = await process.communicate()
            await self.subprocess_manager.terminate_process(process_id)
        
            if process.returncode == 0 and os.path.exists(mp4_path) and os.path.getsize(mp4_path) > 0:
                logger.info(f"Successfully remuxed using simple fallback method: {mp4_path}")
            
                # Delete original TS file
                if os.path.exists(ts_path):
                    os.remove(ts_path)
                return True
            
            # If all failed, keep TS file for manual recovery
            logger.error("All remux methods failed, keeping TS file for manual recovery")
            return False
        except Exception as e:
            logger.error(f"Error in fallback remux: {e}", exc_info=True)
            return False

    async def _validate_mp4(self, mp4_path: str) -> bool:
        """Validate that an MP4 file is properly finalized with moov atom"""
        try:
            # Check if file exists and has reasonable size
            if not os.path.exists(mp4_path) or os.path.getsize(mp4_path) < 10000:  # At least 10KB
                logger.warning(f"MP4 file does not exist or is too small: {mp4_path}")
                return False
            
            # Use ffprobe to check if the file has a valid duration (indicates proper moov atom)
            cmd = [
                "ffprobe", 
                "-v", "error", 
                "-show_entries", 
                "format=duration", 
                "-of", "default=noprint_wrappers=1:nokey=1", 
                mp4_path
            ]
            
            process_id = f"ffprobe_validate_{int(datetime.now().timestamp())}"
            process = await self.subprocess_manager.start_process(cmd, process_id)
            
            stdout, stderr = await process.communicate()
            
            # Clean up the process
            await self.subprocess_manager.terminate_process(process_id)
            
            # Additional check: Make sure we can read video streams
            check_video_cmd = [
                "ffprobe",
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=codec_type",
                "-of", "default=noprint_wrappers=1:nokey=1",
                mp4_path
            ]
            
            video_process_id = f"ffprobe_video_{int(datetime.now().timestamp())}"
            video_process = await self.subprocess_manager.start_process(check_video_cmd, video_process_id)
            
            video_stdout, video_stderr = await video_process.communicate()
            await self.subprocess_manager.terminate_process(video_process_id)
            
            # If we got a valid duration and can read video stream, the file is properly finalized
            has_valid_duration = process.returncode == 0 and stdout and float(stdout.decode('utf-8', errors='ignore').strip()) > 0
            has_video_stream = video_process.returncode == 0 and video_stdout and "video" in video_stdout.decode('utf-8', errors='ignore').strip()
            
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
                "-i", ts_path,
                # Extract video (copy)
                "-map", "0:v:0", "-c:v", "copy", "-f", "h264", 
                f"{ts_path}.h264",
                # Extract audio and convert to AAC
                "-map", "0:a:0", "-c:a", "aac", "-b:a", "128k", "-f", "adts",
                f"{ts_path}.aac"
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
                    "-i", f"{ts_path}.h264",
                    "-i", f"{ts_path}.aac",
                    "-c:v", "copy",
                    "-c:a", "copy",
                    "-movflags", "+faststart",
                    "-y",
                    repaired_path
                ]
            
                process_id = f"ffmpeg_combine_{int(datetime.now().timestamp())}"
                process = await self.subprocess_manager.start_process(combine_cmd, process_id)
                stdout, stderr = await process.communicate()
                await self.subprocess_manager.terminate_process(process_id)
            
                # Check if successful
                if process.returncode == 0 and os.path.exists(repaired_path) and os.path.getsize(repaired_path) > 0:
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
                "-i", ts_path,
                "-c", "copy",
                "-movflags", "+faststart+frag_keyframe+empty_moov+default_base_moof",
                "-f", "mp4",
                "-y",
                repaired_path
            ]
        
            logger.debug(f"Attempting to repair MP4: {' '.join(cmd)}")
            
            # Use subprocess manager for the repair process
            process_id = f"ffmpeg_repair_{int(datetime.now().timestamp())}"
            process = await self.subprocess_manager.start_process(cmd, process_id)
        
            stdout, stderr = await process.communicate()
            
            # Clean up the process
            await self.subprocess_manager.terminate_process(process_id)
        
            if process.returncode == 0 and os.path.exists(repaired_path) and os.path.getsize(repaired_path) > 0:
                # Replace the original file with the repaired version
                os.replace(repaired_path, mp4_path)
                logger.info(f"Successfully repaired MP4 file: {mp4_path}")
            
                # Delete the TS file if the repair was successful
                os.remove(ts_path)
                return True
            else:
                stderr_text = stderr.decode('utf-8', errors='ignore') if stderr else "No error output"
                logger.error(f"Failed to repair MP4 file: {stderr_text}")
            
                # Keep the TS file for manual recovery
                logger.warning(f"Keeping original TS file at {ts_path} for recovery")
                return False
        except Exception as e:
            logger.error(f"Error repairing MP4: {e}", exc_info=True)
            return False

    def _generate_filename(self, streamer: Streamer, stream_data: Dict[str, Any], template: str) -> str:
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