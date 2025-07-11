"""
Main recording service coordinator.

This module coordinates all recording activities using the specialized manager modules.
"""
import os
import time
import asyncio
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any, List, Tuple, Set

# Import database models
from app.models import Stream, Recording, SystemConfig
from app.database import get_db

# Import manager modules
from app.services.recording.config_manager import ConfigManager
from app.services.recording.process_manager import ProcessManager
from app.services.recording.recording_logger import RecordingLogger
from app.services.recording.file_operations import find_and_validate_mp4, intelligent_ts_cleanup
from app.services.recording.notification_manager import NotificationManager
from app.services.recording.stream_info_manager import StreamInfoManager
from app.services.recording.exceptions import (
    RecordingError, ProcessError, ConfigurationError, 
    StreamUnavailableError, FileOperationError
)

logger = logging.getLogger("streamvault")

class RecordingService:
    """Main recording service that coordinates all recording activities"""
    
    def __init__(self, db=None):
        """Initialize the recording service
        
        Args:
            db: Database session (will be created if not provided)
        """
        self.db = db
        
        # Initialize managers
        self.config_manager = ConfigManager(db=db)
        self.process_manager = ProcessManager(config_manager=self.config_manager)
        self.recording_logger = RecordingLogger(config_manager=self.config_manager)
        self.notification_manager = NotificationManager(config_manager=self.config_manager)
        self.stream_info_manager = StreamInfoManager(config_manager=self.config_manager)
        
        # Active recordings tracking
        self.active_recordings = {}
        self.recording_tasks = {}
        self.cleanup_tasks = set()
        
        # Configuration
        self.max_concurrent_recordings = self.config_manager.get_max_concurrent_recordings()
        self.recordings_directory = self.config_manager.get_recordings_directory()
        self.check_interval = self.config_manager.get_check_interval()
        
    async def start(self) -> None:
        """Start the recording service"""
        logger.info("Starting modular recording service")
        
        # Ensure recordings directory exists
        Path(self.recordings_directory).mkdir(parents=True, exist_ok=True)
        
        # Start main loop
        try:
            while True:
                await self.check_and_record_streams()
                await asyncio.sleep(self.check_interval)
                
        except asyncio.CancelledError:
            logger.info("Recording service task was cancelled")
        except Exception as e:
            logger.error(f"Error in recording service main loop: {e}", exc_info=True)
    
    async def check_and_record_streams(self) -> None:
        """Check for active streams and record them"""
        try:
            # Get database session if needed
            if not self.db:
                self.db = next(get_db())
                
            # Clean up finished tasks
            await self._cleanup_finished_tasks()
                
            # Check how many active recordings we have
            current_recordings = len([t for t in self.recording_tasks.values() if not t.done()])
            available_slots = max(0, self.max_concurrent_recordings - current_recordings)
            
            if available_slots <= 0:
                logger.debug(f"Maximum concurrent recordings reached ({self.max_concurrent_recordings})")
                return
                
            # Get streams that should be recorded
            streams_to_record = await self._get_streams_to_record(available_slots)
            
            if not streams_to_record:
                return
                
            logger.info(f"Found {len(streams_to_record)} new streams to record")
            
            # Start recording for each stream
            for stream in streams_to_record:
                task = asyncio.create_task(self.record_stream(stream))
                self.recording_tasks[stream.id] = task
                
        except Exception as e:
            logger.error(f"Error checking streams to record: {e}", exc_info=True)
    
    async def record_stream(self, stream: Stream) -> None:
        """Record a specific stream
        
        Args:
            stream: Stream model object to record
        """
        recording_id = None
        output_path = None
        start_time = datetime.now()
        success = False
        metadata = {}
        
        try:
            # Check if stream is online
            logger.info(f"Checking if stream {stream.name} is online")
            is_online, stream_info = await self.stream_info_manager.check_stream_online(stream)
            
            if not is_online:
                logger.info(f"Stream {stream.name} is not online, skipping")
                return
                
            # Get best quality
            quality = await self.stream_info_manager.get_best_quality(stream)
            
            if not quality:
                logger.warning(f"No quality available for stream {stream.name}")
                return
                
            # Get output path
            output_path = await self._get_output_path(stream)
            
            # Create recording record in database
            recording = Recording(
                stream_id=stream.id,
                start_time=datetime.now(),
                status="recording",
                path=output_path
            )
            
            self.db.add(recording)
            self.db.commit()
            recording_id = recording.id
            
            # Store metadata about the recording
            metadata = self._extract_stream_metadata(stream_info, quality)
            
            # Start recording process
            logger.info(f"Starting recording for {stream.name} at quality {quality}")
            process = await self.process_manager.start_recording_process(
                stream=stream,
                output_path=output_path,
                quality=quality
            )
            
            # Send notification
            await self.notification_manager.notify_recording_started(stream, metadata)
            
            # Add to active recordings
            self.active_recordings[stream.id] = {
                'process': process,
                'start_time': start_time,
                'output_path': output_path,
                'recording_id': recording_id
            }
            
            # Monitor the recording
            exit_code = await self.process_manager.monitor_process(process)
            
            # Process completed, handle cleanup
            duration_seconds = int((datetime.now() - start_time).total_seconds())
            
            # Log recording activity
            if exit_code == 0:
                success = True
                logger.info(f"Recording for {stream.name} completed successfully (duration: {duration_seconds}s)")
                
                # Find and validate MP4 file
                mp4_path = await find_and_validate_mp4(output_path)
                
                if mp4_path:
                    # Update database record with success
                    await self._update_recording_status(recording_id, "completed", mp4_path, duration_seconds)
                    
                    # Schedule intelligent TS cleanup
                    if output_path.endswith('.ts') and os.path.exists(output_path):
                        cleanup_task = asyncio.create_task(
                            intelligent_ts_cleanup(output_path, psutil_available=self.process_manager.psutil_available)
                        )
                        self.cleanup_tasks.add(cleanup_task)
                        cleanup_task.add_done_callback(lambda t: self.cleanup_tasks.discard(t))
                else:
                    await self._update_recording_status(recording_id, "error", output_path, duration_seconds)
                    success = False
                    logger.error(f"Recording completed but no valid MP4 found for {stream.name}")
            else:
                success = False
                logger.error(f"Recording for {stream.name} failed with exit code {exit_code}")
                await self._update_recording_status(recording_id, "error", output_path, duration_seconds)
                
            # Send notification
            await self.notification_manager.notify_recording_completed(stream, duration_seconds, output_path, success)
                
        except StreamUnavailableError as e:
            logger.info(f"Stream {stream.name} is unavailable: {e}")
            if recording_id:
                await self._update_recording_status(recording_id, "error", output_path, 0)
                
        except ProcessError as e:
            logger.error(f"Process error recording {stream.name}: {e}")
            if recording_id:
                await self._update_recording_status(recording_id, "error", output_path, 0)
            await self.notification_manager.notify_recording_error(stream, str(e))
                
        except FileOperationError as e:
            logger.error(f"File operation error recording {stream.name}: {e}")
            if recording_id:
                await self._update_recording_status(recording_id, "error", output_path, 0)
            await self.notification_manager.notify_recording_error(stream, str(e))
            
        except ConfigurationError as e:
            logger.error(f"Configuration error recording {stream.name}: {e}")
            if recording_id:
                await self._update_recording_status(recording_id, "error", output_path, 0)
            await self.notification_manager.notify_recording_error(stream, str(e))
            
        except Exception as e:
            logger.error(f"Error recording stream {stream.name}: {e}", exc_info=True)
            if recording_id:
                await self._update_recording_status(recording_id, "error", output_path, 0)
            await self.notification_manager.notify_recording_error(stream, str(e))
            
        finally:
            # Remove from active recordings
            if stream.id in self.active_recordings:
                del self.active_recordings[stream.id]
    
    async def _get_streams_to_record(self, limit: int = None) -> List[Stream]:
        """Get streams that should be recorded
        
        Args:
            limit: Maximum number of streams to return
            
        Returns:
            List of stream objects to record
        """
        try:
            # Get all streams that are marked for recording and not already being recorded
            streams = self.db.query(Stream).filter(
                Stream.record == True,
                ~Stream.id.in_(self.active_recordings.keys())
            ).all()
            
            if not streams:
                return []
                
            # Filter to limit number of streams
            if limit is not None and limit < len(streams):
                return streams[:limit]
                
            return streams
            
        except Exception as e:
            logger.error(f"Error getting streams to record: {e}", exc_info=True)
            return []
    
    async def _get_output_path(self, stream: Stream) -> str:
        """Get output path for recording a stream
        
        Args:
            stream: Stream to record
            
        Returns:
            Full path to output file
        """
        # Get base recordings directory
        recordings_dir = self.recordings_directory
        
        # Create streamer subdirectory if needed
        streamer_dir = os.path.join(recordings_dir, self._sanitize_filename(stream.name))
        Path(streamer_dir).mkdir(parents=True, exist_ok=True)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"{self._sanitize_filename(stream.name)}_{timestamp}.ts"
        
        return os.path.join(streamer_dir, filename)
    
    async def _update_recording_status(self, recording_id: int, status: str, 
                                      path: str, duration_seconds: int) -> None:
        """Update recording status in database
        
        Args:
            recording_id: Recording ID
            status: New status
            path: File path
            duration_seconds: Duration in seconds
        """
        try:
            recording = self.db.query(Recording).filter(Recording.id == recording_id).first()
            
            if recording:
                recording.status = status
                recording.end_time = datetime.now()
                recording.duration = duration_seconds
                recording.path = path
                self.db.commit()
                
        except Exception as e:
            logger.error(f"Error updating recording status: {e}", exc_info=True)
    
    async def _cleanup_finished_tasks(self) -> None:
        """Clean up finished recording tasks"""
        # Find finished tasks
        finished_stream_ids = []
        
        for stream_id, task in self.recording_tasks.items():
            if task.done():
                finished_stream_ids.append(stream_id)
                
                # Check for exceptions
                try:
                    task.result()
                except Exception as e:
                    logger.error(f"Recording task for stream {stream_id} failed: {e}", exc_info=True)
        
        # Remove finished tasks
        for stream_id in finished_stream_ids:
            if stream_id in self.recording_tasks:
                del self.recording_tasks[stream_id]
    
    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename to be safe for file system
        
        Args:
            filename: Original filename
            
        Returns:
            Sanitized filename
        """
        # Replace invalid characters
        invalid_chars = r'<>:"/\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
            
        # Remove leading/trailing whitespace and dots
        filename = filename.strip('. ')
        
        # Limit length
        if len(filename) > 100:
            filename = filename[:100]
            
        # Ensure not empty
        if not filename:
            filename = "unnamed"
            
        return filename
        
    def _extract_stream_metadata(self, stream_info: Dict[str, Any], quality: str) -> Dict[str, Any]:
        """Extract metadata from stream info
        
        Args:
            stream_info: Stream information dict
            quality: Selected quality
            
        Returns:
            Dictionary with metadata
        """
        metadata = {}
        
        try:
            if not stream_info or 'streams' not in stream_info:
                return metadata
                
            # Add quality info
            metadata['quality'] = quality
            
            # Extract resolution if available
            quality_info = stream_info['streams'].get(quality, {})
            if isinstance(quality_info, dict) and 'resolution' in quality_info:
                metadata['resolution'] = quality_info['resolution']
                
            # Extract any available stream metadata
            if 'metadata' in stream_info:
                metadata.update(stream_info['metadata'])
                
        except Exception as e:
            logger.error(f"Error extracting stream metadata: {e}", exc_info=True)
            
        return metadata
