"""
Main recording service coordinator.

This module coordinates recording activities triggered by Twitch EventSub webhooks.
The workflow is: Webhook → Start Recording → Post-processing with existing utils.
"""
import os
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any

# Import database models
from app.models import Stream, Recording, Streamer
from app.database import get_db

# Import manager modules
from app.services.recording.config_manager import ConfigManager
from app.services.recording.process_manager import ProcessManager
from app.services.recording.recording_logger import RecordingLogger
from app.services.recording.notification_manager import NotificationManager
from app.services.recording.stream_info_manager import StreamInfoManager
from app.services.recording.post_processing_manager import PostProcessingManager
from app.services.recording.exceptions import (
    RecordingError, ProcessError, ConfigurationError, 
    StreamUnavailableError, FileOperationError
)

logger = logging.getLogger("streamvault")

class RecordingService:
    """Main recording service that coordinates webhook-triggered recording activities"""
    
    def __init__(self, db=None):
        """Initialize the recording service
        
        Args:
            db: Database session (will be created if not provided)
        """
        self.db = db
        
        # Initialize managers
        self.config_manager = ConfigManager()
        self.process_manager = ProcessManager(config_manager=self.config_manager)
        self.recording_logger = RecordingLogger(config_manager=self.config_manager)
        self.notification_manager = NotificationManager(config_manager=self.config_manager)
        self.stream_info_manager = StreamInfoManager(config_manager=self.config_manager)
        self.post_processing_manager = PostProcessingManager(config_manager=self.config_manager)
        
        # Active recordings tracking
        self.active_recordings = {}
        self.recording_tasks = {}
        self.cleanup_tasks = set()
        
        # Configuration
        self.max_concurrent_recordings = self.config_manager.get_max_concurrent_recordings()
        self.recordings_directory = self.config_manager.get_recordings_directory()
        
    def _ensure_db_session(self):
        """Ensure we have a valid database session"""
        if not self.db:
            self.db = next(get_db())
    
    async def start_recording_for_stream(self, stream: Stream) -> bool:
        """Start recording for a specific stream (called by webhook handler)
        
        Args:
            stream: Stream model object (populated by webhook)
            
        Returns:
            True if recording started successfully, False otherwise
        """
        try:
            # Check if already recording this stream
            if stream.id in self.active_recordings:
                logger.warning(f"Stream {stream.streamer.username} is already being recorded")
                return False
            
            # Check concurrent recording limits
            current_recordings = len([t for t in self.recording_tasks.values() if not t.done()])
            if current_recordings >= self.max_concurrent_recordings:
                logger.warning(f"Maximum concurrent recordings reached ({self.max_concurrent_recordings}), cannot start recording for {stream.streamer.username}")
                return False
            
            # Start recording task
            task = asyncio.create_task(self.record_stream(stream))
            self.recording_tasks[stream.id] = task
            
            logger.info(f"Started recording task for stream {stream.streamer.username}")
            return True
            
        except Exception as e:
            logger.error(f"Error starting recording for stream {stream.streamer.username}: {e}", exc_info=True)
            return False
    
    async def record_stream(self, stream: Stream) -> None:
        """Record a specific stream with complete post-processing workflow
        
        Args:
            stream: Stream model object (populated by webhook)
        """
        recording_id = None
        ts_output_path = None
        start_time = datetime.now()
        success = False
        
        try:
            # Ensure we have a database session
            self._ensure_db_session()
            
            logger.info(f"Starting recording for {stream.streamer.username}")
            
            # Get quality setting
            quality = self.stream_info_manager.get_preferred_quality()
            
            # Generate TS output path (simple timestamp-based for now)
            # Post-processing will handle the final naming using path_utils
            ts_filename = f"{stream.streamer.username}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.ts"
            streamer_dir = Path(self.recordings_directory) / stream.streamer.username
            streamer_dir.mkdir(parents=True, exist_ok=True)
            ts_output_path = str(streamer_dir / ts_filename)
            
            # Create recording record in database
            recording = Recording(
                stream_id=stream.id,
                start_time=start_time,
                status="recording",
                path=ts_output_path
            )
            
            self.db.add(recording)
            self.db.commit()
            recording_id = recording.id
            
            # Get stream metadata for notifications
            metadata = await self.stream_info_manager.get_stream_metadata(stream)
            
            # Start streamlink recording process
            logger.info(f"Starting streamlink recording for {stream.streamer.username} at quality {quality}")
            logger.info(f"TS output path: {ts_output_path}")
            
            process = await self.process_manager.start_recording_process(
                stream=stream,
                output_path=ts_output_path,
                quality=quality
            )
            
            # Check if process was created successfully
            if not process:
                logger.error(f"Failed to start recording process for {stream.streamer.username}")
                await self._update_recording_status(recording_id, "error", ts_output_path, 0)
                return
            
            # Send start notification
            await self.notification_manager.notify_recording_started(stream, metadata)
            
            # Add to active recordings
            self.active_recordings[stream.id] = {
                'process': process,
                'start_time': start_time,
                'ts_output_path': ts_output_path,
                'recording_id': recording_id
            }
            
            # Monitor the recording
            exit_code = await self.process_manager.monitor_process(process)
            
            # Process completed, handle post-processing
            duration_seconds = int((datetime.now() - start_time).total_seconds())
            
            if exit_code == 0 and os.path.exists(ts_output_path) and os.path.getsize(ts_output_path) > 1024:
                logger.info(f"Recording for {stream.streamer.username} completed successfully (duration: {duration_seconds}s)")
                
                # Run complete post-processing workflow using existing utils
                try:
                    logger.info(f"Starting post-processing for {stream.streamer.username}")
                    processing_results = await self.post_processing_manager.process_completed_recording(
                        stream_id=stream.id,
                        ts_path=ts_output_path
                    )
                    
                    if processing_results['success']:
                        success = True
                        mp4_path = processing_results['mp4_path']
                        # Update database with final MP4 path
                        await self._update_recording_status(recording_id, "completed", mp4_path, duration_seconds)
                        
                        logger.info(f"Post-processing completed successfully for {stream.streamer.username}")
                        logger.info(f"Final file: {mp4_path}")
                    else:
                        logger.error(f"Post-processing failed for {stream.streamer.username}")
                        await self._update_recording_status(recording_id, "error", ts_output_path, duration_seconds)
                        
                except Exception as e:
                    logger.error(f"Error in post-processing for {stream.streamer.username}: {e}", exc_info=True)
                    await self._update_recording_status(recording_id, "error", ts_output_path, duration_seconds)
                    
            else:
                success = False
                logger.error(f"Recording for {stream.streamer.username} failed with exit code {exit_code}")
                await self._update_recording_status(recording_id, "error", ts_output_path, duration_seconds)
                
            # Send completion notification
            final_path = processing_results.get('mp4_path', ts_output_path) if success else ts_output_path
            await self.notification_manager.notify_recording_completed(
                stream, duration_seconds, final_path, success
            )
                
        except StreamUnavailableError as e:
            logger.info(f"Stream {stream.streamer.username} is unavailable: {e}")
            if recording_id:
                await self._update_recording_status(recording_id, "error", ts_output_path or "", 0)
                
        except ProcessError as e:
            logger.error(f"Process error recording {stream.streamer.username}: {e}")
            if recording_id:
                await self._update_recording_status(recording_id, "error", ts_output_path or "", 0)
            await self.notification_manager.notify_recording_error(stream, str(e))
                
        except FileOperationError as e:
            logger.error(f"File operation error recording {stream.streamer.username}: {e}")
            if recording_id:
                await self._update_recording_status(recording_id, "error", ts_output_path or "", 0)
            await self.notification_manager.notify_recording_error(stream, str(e))
            
        except ConfigurationError as e:
            logger.error(f"Configuration error recording {stream.streamer.username}: {e}")
            if recording_id:
                await self._update_recording_status(recording_id, "error", ts_output_path or "", 0)
            await self.notification_manager.notify_recording_error(stream, str(e))
            
        except Exception as e:
            logger.error(f"Error recording stream {stream.streamer.username}: {e}", exc_info=True)
            if recording_id:
                await self._update_recording_status(recording_id, "error", ts_output_path or "", 0)
            await self.notification_manager.notify_recording_error(stream, str(e))
            
        finally:
            # Remove from active recordings
            if stream.id in self.active_recordings:
                del self.active_recordings[stream.id]

    async def stop_recording_for_stream(self, stream: Stream) -> bool:
        """Stop recording for a specific stream (called by webhook handler)
        
        Args:
            stream: Stream model object
            
        Returns:
            True if stopped successfully, False otherwise
        """
        try:
            if stream.id not in self.active_recordings:
                logger.warning(f"No active recording found for stream {stream.streamer.username}")
                return False
                
            # Terminate the process gracefully
            process_id = f"stream_{stream.id}"
            success = await self.process_manager.terminate_process(process_id)
            
            if success:
                logger.info(f"Successfully stopped recording for stream {stream.streamer.username}")
            else:
                logger.warning(f"Failed to stop recording for stream {stream.streamer.username}")
                
            return success
            
        except Exception as e:
            logger.error(f"Error stopping recording for stream {stream.streamer.username}: {e}", exc_info=True)
            return False

    async def _update_recording_status(
        self, recording_id: int, status: str, path: str, duration_seconds: int
    ) -> None:
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

    async def get_active_recordings(self) -> Dict[int, Dict[str, Any]]:
        """Get information about currently active recordings
        
        Returns:
            Dictionary with stream IDs as keys and recording info as values
        """
        active_info = {}
        
        for stream_id, recording_info in self.active_recordings.items():
            active_info[stream_id] = {
                'start_time': recording_info['start_time'],
                'ts_output_path': recording_info.get('ts_output_path'),
                'recording_id': recording_info.get('recording_id'),
                'duration': int((datetime.now() - recording_info['start_time']).total_seconds())
            }
            
        return active_info

    async def cleanup_all_recordings(self) -> None:
        """Stop all active recordings and clean up"""
        try:
            logger.info("Cleaning up all active recordings")
            
            # Stop all recording processes
            for stream_id in list(self.active_recordings.keys()):
                process_id = f"stream_{stream_id}"
                await self.process_manager.terminate_process(process_id)
                
            # Clean up process manager
            await self.process_manager.cleanup_all()
            
            # Wait for cleanup tasks to complete
            if self.cleanup_tasks:
                await asyncio.gather(*self.cleanup_tasks, return_exceptions=True)
                
            logger.info("Recording service cleanup completed")
            
        except Exception as e:
            logger.error(f"Error cleaning up recordings: {e}", exc_info=True)

    async def cleanup_finished_tasks(self) -> None:
        """Clean up finished recording tasks (should be called periodically)"""
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