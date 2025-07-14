"""
Main recording service coordinator.

WORKFLOW:
1. EventSub webhook → start_recording()
2. Streamlink records .ts file (monitored by process_manager)
3. When done → Post-processing:
   - metadata_service creates all metadata files
   - ffmpeg_utils converts .ts → .mp4 with chapters
   - Validate MP4
   - Delete .ts file
"""
import logging
import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any

from app.models import Stream, Recording, Streamer
from app.utils import async_file
from app.database import get_db

# Import managers
from app.services.recording.config_manager import ConfigManager
from app.services.recording.process_manager import ProcessManager
from app.services.recording.recording_logger import RecordingLogger
from app.services.recording.notification_manager import NotificationManager
from app.services.recording.stream_info_manager import StreamInfoManager
from app.services.recording.pipeline_manager import PipelineManager
from app.dependencies import websocket_manager
from app.services.state_persistence_service import state_persistence_service

# Import utils
from app.utils.path_utils import generate_filename
from app.utils.file_utils import sanitize_filename

logger = logging.getLogger("streamvault")

class RecordingService:
    """Main recording service that coordinates webhook-triggered recording activities"""
    
    def __init__(self, db=None):
        self.db = db
        
        # Initialize managers
        self.config_manager = ConfigManager()
        self.process_manager = ProcessManager(config_manager=self.config_manager)
        self.recording_logger = RecordingLogger(config_manager=self.config_manager)
        self.notification_manager = NotificationManager(config_manager=self.config_manager)
        self.stream_info_manager = StreamInfoManager(config_manager=self.config_manager)
        self.pipeline_manager = PipelineManager(config_manager=self.config_manager)
        
        # Active recordings tracking
        self.active_recordings = {}
        self.recording_tasks = {}
        
        # Configuration
        self.max_concurrent_recordings = self.config_manager.get_max_concurrent_recordings()
        self.recordings_directory = self.config_manager.get_recordings_directory()
        
        # Shutdown management
        self._shutdown_event = asyncio.Event()
        self._is_shutting_down = False

    def _ensure_db_session(self):
        """Ensure we have a valid database session"""
        if not self.db:
            self.db = next(get_db())

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

    async def recover_active_recordings_from_persistence(self):
        """Recover active recordings from persistent storage after restart"""
        logger.info("Starting recovery of active recordings from persistent storage")
        
        try:
            # Get recoverable recordings from persistent storage
            recoverable_recordings = await state_persistence_service.recover_active_recordings()
            
            if not recoverable_recordings:
                logger.info("No recoverable recordings found")
                return
            
            logger.info(f"Found {len(recoverable_recordings)} recoverable recordings")
            
            # Recover each recording
            for recording_info in recoverable_recordings:
                try:
                    await self._recover_single_recording(recording_info)
                except Exception as e:
                    logger.error(f"Failed to recover recording {recording_info['stream_id']}: {e}", exc_info=True)
                    # Remove failed recovery from persistent storage
                    await state_persistence_service.remove_active_recording(recording_info['stream_id'])
                    
            logger.info("Recording recovery completed")
            
        except Exception as e:
            logger.error(f"Error during recording recovery: {e}", exc_info=True)
            
    async def _recover_single_recording(self, recording_info: Dict[str, Any]):
        """Recover a single recording from persistent storage"""
        stream_id = recording_info['stream_id']
        process_id = recording_info['process_id']
        streamer_name = recording_info['streamer_name']
        
        logger.info(f"Recovering recording for {streamer_name} (stream {stream_id}, process {process_id})")
        
        # Check if process is still running
        import psutil
        if not psutil.pid_exists(process_id):
            logger.warning(f"Process {process_id} no longer exists, cannot recover {streamer_name}")
            raise Exception(f"Process {process_id} no longer exists")
            
        # Get the process object
        try:
            process = psutil.Process(process_id)
        except psutil.NoSuchProcess:
            logger.warning(f"Process {process_id} no longer exists, cannot recover {streamer_name}")
            raise Exception(f"Process {process_id} no longer exists")
            
        # Verify output file exists and is growing
        ts_output_path = recording_info['ts_output_path']
        if not os.path.exists(ts_output_path):
            logger.warning(f"Output file {ts_output_path} not found, cannot recover {streamer_name}")
            raise Exception(f"Output file {ts_output_path} not found")
            
        # Add to memory state
        self.active_recordings[stream_id] = {
            'process': process,
            'start_time': recording_info['start_time'],
            'ts_output_path': ts_output_path,
            'recording_id': recording_info['recording_id'],
            'force_mode': recording_info['force_mode'],
            'streamer_name': streamer_name
        }
        
        # Get stream object from database
        self._ensure_db_session()
        stream = self.db.query(Stream).filter(Stream.id == stream_id).first()
        if not stream:
            logger.error(f"Stream {stream_id} not found in database, cannot recover")
            raise Exception(f"Stream {stream_id} not found in database")
        
        # Start monitoring task for the recovered recording
        task = asyncio.create_task(self._monitor_and_process_recording(
            stream=stream,
            recording_id=recording_info['recording_id'],
            ts_output_path=ts_output_path,
            start_time=recording_info['start_time']
        ))
        self.recording_tasks[stream_id] = task
        
        logger.info(f"Successfully recovered recording for {streamer_name}")

    async def send_active_recordings_websocket_update(self):
        """Send current active recordings to all WebSocket clients"""
        try:
            # Get active recordings data
            active_recordings_dict = await self.get_active_recordings()
            
            # Convert to the format expected by frontend
            active_recordings_list = []
            
            # Use a new session for database queries
            self._ensure_db_session()
            
            for stream_id, recording_info in active_recordings_dict.items():
                try:
                    # Get stream and streamer info
                    stream = self.db.query(Stream).filter(Stream.id == stream_id).first()
                    if stream and stream.streamer:
                        # Format recording info for WebSocket
                        recording_data = {
                            'streamer_id': stream.streamer_id,
                            'streamer_name': stream.streamer.username,
                            'stream_id': stream_id,
                            'started_at': recording_info['start_time'].isoformat() if isinstance(recording_info['start_time'], datetime) else recording_info['start_time'],
                            'duration': recording_info.get('duration', 0),
                            'output_path': recording_info.get('ts_output_path', ''),
                            'quality': 'best',  # Default value since config might not be available
                            'title': stream.title or '',
                            'category': stream.category_name or ''
                        }
                        active_recordings_list.append(recording_data)
                except Exception as e:
                    logger.warning(f"Error formatting active recording for stream {stream_id}: {e}")
                    continue
            
            # Send via WebSocket
            await websocket_manager.send_active_recordings_update(active_recordings_list)
            
            # Update heartbeats for all active recordings
            for stream_id in active_recordings_dict.keys():
                try:
                    await state_persistence_service.update_heartbeat(stream_id)
                except Exception as e:
                    logger.warning(f"Failed to update heartbeat for stream {stream_id}: {e}")
            
        except Exception as e:
            logger.error(f"Error sending active recordings WebSocket update: {e}", exc_info=True)

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

    async def graceful_shutdown(self, timeout: int = 30):
        """Gracefully shutdown the recording service
        
        Args:
            timeout: Maximum time to wait for recordings to finish (seconds)
        """
        logger.info("🛑 Starting graceful shutdown of Recording Service...")
        self._is_shutting_down = True
        
        try:
            # Stop accepting new recordings
            logger.info("📛 Preventing new recordings from starting...")
            
            # Get list of active recordings
            active_count = len(self.active_recordings)
            if active_count > 0:
                logger.info(f"⏳ Waiting for {active_count} active recordings to complete...")
                
                # Wait for recordings to finish naturally (up to timeout)
                start_time = asyncio.get_event_loop().time()
                while self.active_recordings and (asyncio.get_event_loop().time() - start_time) < timeout:
                    await asyncio.sleep(1)
                    await self.cleanup_finished_tasks()
                
                # Force stop remaining recordings
                remaining_count = len(self.active_recordings)
                if remaining_count > 0:
                    logger.warning(f"⚠️ Force stopping {remaining_count} remaining recordings...")
                    await self._force_stop_all_recordings()
            
            # Cancel all recording tasks
            if self.recording_tasks:
                logger.info(f"🔄 Cancelling {len(self.recording_tasks)} recording tasks...")
                await self._cancel_all_tasks()
            
            # Shutdown process manager
            if hasattr(self.process_manager, 'graceful_shutdown'):
                logger.info("🔄 Shutting down process manager...")
                await self.process_manager.graceful_shutdown()
            
            # Shutdown pipeline manager
            if hasattr(self.pipeline_manager, 'graceful_shutdown'):
                logger.info("🔄 Shutting down pipeline manager...")
                await self.pipeline_manager.graceful_shutdown()
            
            logger.info("✅ Recording Service graceful shutdown completed")
            
        except Exception as e:
            logger.error(f"❌ Error during Recording Service shutdown: {e}", exc_info=True)
        finally:
            self._shutdown_event.set()

    async def _force_stop_all_recordings(self):
        """Force stop all active recordings"""
        for stream_id in list(self.active_recordings.keys()):
            try:
                logger.info(f"🛑 Force stopping recording for stream {stream_id}")
                
                # Stop via process manager
                if hasattr(self.process_manager, 'stop_recording_process'):
                    await self.process_manager.stop_recording_process(stream_id)
                
                # Remove from active recordings
                if stream_id in self.active_recordings:
                    del self.active_recordings[stream_id]
                    
            except Exception as e:
                logger.error(f"Error force stopping recording {stream_id}: {e}")

    async def _cancel_all_tasks(self):
        """Cancel all recording tasks"""
        for stream_id, task in list(self.recording_tasks.items()):
            try:
                if not task.done():
                    logger.info(f"🔄 Cancelling recording task for stream {stream_id}")
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        logger.info(f"✅ Recording task for stream {stream_id} cancelled")
                    except Exception as e:
                        logger.error(f"Error cancelling task for stream {stream_id}: {e}")
                        
            except Exception as e:
                logger.error(f"Error handling task cancellation for stream {stream_id}: {e}")
        
        self.recording_tasks.clear()

    def is_shutting_down(self) -> bool:
        """Check if service is shutting down"""
        return self._is_shutting_down

    async def wait_for_shutdown(self):
        """Wait for shutdown to complete"""
        await self._shutdown_event.wait()

    async def start_recording(self, streamer_id: int, stream_data: Dict[str, Any], force_mode: bool = False) -> bool:
        """Start recording for a streamer (called by EventHandlerRegistry)
        
        This is the main entry point for starting a recording when a stream goes online.
        It handles the complete recording lifecycle including post-processing.
        
        Args:
            streamer_id: ID of the streamer
            stream_data: Stream information from Twitch webhook
            force_mode: If True, uses more aggressive streamlink settings
            
        Returns:
            True if recording started successfully, False otherwise
        """
        recording_id = None
        ts_output_path = None
        start_time = datetime.now()
        success = False
        
        # Check if service is shutting down
        if self._is_shutting_down:
            logger.warning(f"Cannot start recording for {streamer_id}: service is shutting down")
            return False
        
        try:
            # Ensure we have a database session
            self._ensure_db_session()
            
            # Get the streamer and stream
            streamer = self.db.query(Streamer).filter(Streamer.id == streamer_id).first()
            if not streamer:
                logger.error(f"Streamer not found: {streamer_id}")
                return False
                
            # Find the active stream
            stream = self.db.query(Stream).filter(
                Stream.streamer_id == streamer_id,
                Stream.ended_at.is_(None)
            ).order_by(Stream.started_at.desc()).first()
            
            if not stream:
                logger.error(f"No active stream found for streamer {streamer.username}")
                return False
                
            if not stream.id:
                logger.error(f"Stream has no ID for streamer {streamer.username}")
                return False
            
            # Set the streamer relationship
            stream.streamer = streamer
            
            # Check if already recording this stream
            if stream.id in self.active_recordings:
                logger.warning(f"Stream {streamer.username} is already being recorded")
                return False
            
            # Check concurrent recording limits
            current_recordings = len([t for t in self.recording_tasks.values() if not t.done()])
            if current_recordings >= self.max_concurrent_recordings:
                logger.warning(f"Maximum concurrent recordings reached ({self.max_concurrent_recordings}), cannot start recording for {streamer.username}")
                return False
            
            logger.info(f"Starting recording for {streamer.username} (force_mode={force_mode})")
            
            # Get quality setting from streamer-specific or global settings
            quality = self.config_manager.get_quality_setting(streamer_id)
            
            # Generate output path using the configured template and path_utils
            filename_template = self.config_manager.get_filename_template(streamer_id)
            
            # Use path_utils to generate the filename
            ts_filename = await generate_filename(streamer, stream_data, filename_template)
            
            # Change extension to .ts for recording
            if ts_filename.endswith('.mp4'):
                ts_filename = ts_filename[:-4] + '.ts'
            
            # Create full path
            streamer_dir = Path(self.recordings_directory) / streamer.username
            await async_file.path_mkdir(streamer_dir, parents=True, exist_ok=True)
            ts_output_path = str(streamer_dir / ts_filename)
            
            # Create recording record in database
            recording = Recording(
                stream_id=stream.id,
                start_time=start_time,
                status="recording",
                path=ts_output_path
            )
            
            # Validate that stream_id is set
            if not recording.stream_id:
                logger.error(f"Failed to set stream_id for recording of streamer {streamer.username}")
                return False
            
            self.db.add(recording)
            self.db.commit()
            recording_id = recording.id
            
            # Verify recording was created correctly
            if not recording_id:
                logger.error(f"Failed to create recording record for streamer {streamer.username}")
                return False
            
            # Get stream metadata for notifications
            metadata = await self.stream_info_manager.get_stream_metadata(stream)
            
            # Log the recording start
            self.recording_logger.log_recording_start(
                streamer_id=streamer_id,
                streamer_name=streamer.username,
                quality=quality,
                output_path=ts_output_path
            )
            
            # Start streamlink recording process using process_manager
            logger.info(f"Starting streamlink recording for {streamer.username} at quality {quality}")
            logger.info(f"TS output path: {ts_output_path}")
            
            process = await self.process_manager.start_recording_process(
                stream=stream,
                output_path=ts_output_path,
                quality=quality
            )
            
            # Check if process was created successfully
            if not process:
                logger.error(f"Failed to start recording process for {streamer.username}")
                await self._update_recording_status(recording_id, "error", ts_output_path, 0)
                self.recording_logger.log_recording_error(
                    streamer_id=streamer_id,
                    streamer_name=streamer.username,
                    error="Failed to start streamlink process"
                )
                return False
            
            # Send start notification
            await self.notification_manager.notify_recording_started(stream, metadata)
            
            # Generate process identifier for tracking
            process_identifier = f"stream_{stream.id}"
            
            # Build config dict for persistence
            config = {
                'quality': quality,
                'force_mode': force_mode,
                'streamer_id': streamer_id,
                'stream_id': stream.id
            }
            
            # Add to active recordings
            self.active_recordings[stream.id] = {
                'process': process,
                'start_time': start_time,
                'ts_output_path': ts_output_path,
                'recording_id': recording_id,
                'force_mode': force_mode,
                'streamer_name': streamer.username
            }
            
            # Save to persistent storage
            try:
                await state_persistence_service.save_active_recording(
                    stream_id=stream.id,
                    recording_id=recording_id,
                    process_id=process.pid,
                    process_identifier=process_identifier,
                    streamer_name=streamer.username,
                    started_at=start_time,
                    ts_output_path=ts_output_path,
                    force_mode=force_mode,
                    quality=quality,
                    config=config
                )
            except Exception as e:
                logger.error(f"Failed to save recording state to persistent storage: {e}", exc_info=True)
            
            # Send WebSocket notification for recording started
            try:
                recording_info = {
                    'streamer_id': streamer_id,
                    'streamer_name': streamer.username,
                    'stream_id': stream.id,
                    'started_at': start_time.isoformat(),
                    'duration': 0,
                    'output_path': ts_output_path,
                    'quality': config.get('quality', 'best'),
                    'title': stream.title or '',
                    'category': stream.category_name or ''
                }
                await websocket_manager.send_recording_started(recording_info)
                
                # Send immediate active recordings update
                from app.services.active_recordings_broadcaster import send_immediate_active_recordings_update
                await send_immediate_active_recordings_update()
            except Exception as e:
                logger.warning(f"Failed to send WebSocket recording started notification: {e}")
            
            # Start monitoring task
            task = asyncio.create_task(self._monitor_and_process_recording(stream, recording_id, ts_output_path, start_time))
            self.recording_tasks[stream.id] = task
            
            logger.info(f"Recording started successfully for {streamer.username}")
            return True
            
        except Exception as e:
            logger.error(f"Error starting recording: {e}", exc_info=True)
            if recording_id:
                await self._update_recording_status(recording_id, "error", ts_output_path or "", 0)
            return False

    async def _monitor_and_process_recording(self, stream: Stream, recording_id: int, ts_output_path: str, start_time: datetime) -> None:
        """Monitor recording and handle post-processing when complete
        
        This method runs in the background and handles the complete recording lifecycle.
        """
        success = False
        mp4_path = None
        
        try:
            # Get the process from active recordings
            recording_info = self.active_recordings.get(stream.id)
            if not recording_info:
                logger.error(f"No active recording found for stream {stream.streamer.username}")
                return
                
            process = recording_info['process']
            streamer_name = recording_info['streamer_name']
            
            # Monitor the recording process using process_manager
            logger.info(f"Monitoring recording for {streamer_name}")
            exit_code = await self.process_manager.monitor_process(process)
            
            duration_seconds = int((datetime.now() - start_time).total_seconds())
            
            # Check if recording was successful
            if exit_code == 0 and await async_file.exists(ts_output_path) and await async_file.getsize(ts_output_path) > 1024:
                logger.info(f"Recording for {streamer_name} completed successfully (duration: {duration_seconds}s)")
                
                # Post-processing pipeline handled by PipelineManager
                try:
                    processing_results = await self.pipeline_manager.start_post_processing_pipeline(
                        stream_id=stream.id,
                        ts_path=ts_output_path
                    )
                    
                    if processing_results['success']:
                        success = True
                        mp4_path = processing_results['mp4_path']
                        # Update database with final MP4 path
                        await self._update_recording_status(recording_id, "completed", mp4_path, duration_seconds)
                        
                        logger.info(f"Post-processing completed successfully for {streamer_name}")
                        logger.info(f"Final file: {mp4_path}")
                    else:
                        logger.error(f"Post-processing failed for {streamer_name}")
                        await self._update_recording_status(recording_id, "error", ts_output_path, duration_seconds)
                        
                except Exception as e:
                    logger.error(f"Error in post-processing for {streamer_name}: {e}", exc_info=True)
                    await self._update_recording_status(recording_id, "error", ts_output_path, duration_seconds)
                    
            else:
                logger.error(f"Recording for {streamer_name} failed with exit code {exit_code}")
                await self._update_recording_status(recording_id, "error", ts_output_path, duration_seconds)
            
            # Send completion notification
            final_path = mp4_path if success else ts_output_path
            await self.notification_manager.notify_recording_completed(
                stream, duration_seconds, final_path, success
            )
            
        except Exception as e:
            logger.error(f"Error in recording monitor for {stream.streamer.username}: {e}", exc_info=True)
            if recording_id:
                await self._update_recording_status(recording_id, "error", ts_output_path, 0)
            await self.notification_manager.notify_recording_error(stream, str(e))
            
        finally:
            # Clean up
            if stream.id in self.active_recordings:
                del self.active_recordings[stream.id]

    async def stop_recording(self, streamer_id: int, reason: str = "manual") -> bool:
        """Stop recording for a streamer (called by EventHandlerRegistry)
        
        This is mainly for manual stops or error conditions.
        Normal stream endings are handled automatically by streamlink.
        
        Args:
            streamer_id: ID of the streamer
            reason: Reason for stopping (manual, automatic, error)
            
        Returns:
            True if stopped successfully, False otherwise
        """
        try:
            # Find the active stream for this streamer
            stream = self.db.query(Stream).filter(
                Stream.streamer_id == streamer_id,
                Stream.ended_at.is_(None)
            ).order_by(Stream.started_at.desc()).first()
            
            if not stream or stream.id not in self.active_recordings:
                logger.warning(f"No active recording found for streamer ID {streamer_id}")
                return False
            
            recording_info = self.active_recordings.get(stream.id, {})
            streamer_name = recording_info.get('streamer_name', 'unknown')
            
            logger.info(f"Stopping recording for streamer ID {streamer_id} (reason: {reason})")
            
            # Terminate the process gracefully using process_manager
            process_id = f"stream_{stream.id}"
            success = await self.process_manager.terminate_process(process_id)
            
            if success:
                logger.info(f"Successfully stopped recording for streamer ID {streamer_id}")
                duration = int((datetime.now() - recording_info['start_time']).total_seconds())
                self.recording_logger.log_recording_stop(
                    streamer_id=streamer_id,
                    streamer_name=streamer_name,
                    duration=duration,
                    output_path=recording_info.get('ts_output_path', ''),
                    reason=reason
                )
                
                # Send WebSocket notification for recording stopped
                try:
                    recording_info_ws = {
                        'streamer_id': streamer_id,
                        'streamer_name': streamer_name,
                        'stream_id': stream.id,
                        'stopped_at': datetime.now().isoformat(),
                        'duration': duration,
                        'reason': reason
                    }
                    await websocket_manager.send_recording_stopped(recording_info_ws)
                    
                    # Send immediate active recordings update
                    from app.services.active_recordings_broadcaster import send_immediate_active_recordings_update
                    await send_immediate_active_recordings_update()
                    
                    # Remove from persistent storage
                    await state_persistence_service.remove_active_recording(stream.id)
                except Exception as e:
                    logger.warning(f"Failed to send WebSocket recording stopped notification: {e}")
            else:
                logger.warning(f"Failed to stop recording gracefully for streamer ID {streamer_id}")
                
            return success
            
        except Exception as e:
            logger.error(f"Error stopping recording: {e}", exc_info=True)
            return False