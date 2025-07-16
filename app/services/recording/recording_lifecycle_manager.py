"""
RecordingLifecycleManager - Recording start/stop lifecycle management

Extracted from recording_service.py ULTRA-BOSS (1084 lines)  
Handles recording start, stop, monitoring, and lifecycle events.
"""

import logging
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path
from app.utils.path_utils import generate_filename
from app.services.api.twitch_api import twitch_api

logger = logging.getLogger("streamvault")


class RecordingLifecycleManager:
    """Manages recording lifecycle events and monitoring"""
    
    def __init__(self, config_manager=None, process_manager=None, 
                 database_service=None, websocket_service=None, state_manager=None):
        self.config_manager = config_manager
        self.process_manager = process_manager
        self.database_service = database_service
        self.websocket_service = websocket_service
        self.state_manager = state_manager
        
        # Shutdown management
        self._shutdown_event = asyncio.Event()
        self._is_shutting_down = False

    async def start_recording(self, stream_id: int, streamer_id: int, **kwargs) -> Optional[int]:
        """Start a new recording"""
        try:
            if self._is_shutting_down:
                logger.warning("Cannot start recording during shutdown")
                return None
            
            # Check capacity
            if not self.state_manager.can_start_new_recording():
                logger.warning("Cannot start recording: at maximum capacity")
                return None
            
            # Generate file path
            file_path = await self._generate_recording_path(streamer_id, stream_id)
            
            # Create recording in database
            recording = await self.database_service.create_recording(
                stream_id=stream_id,
                streamer_id=streamer_id, 
                file_path=file_path
            )
            
            if not recording:
                logger.error("Failed to create recording in database")
                return None
            
            recording_id = recording.id
            
            # Add to active recordings
            recording_data = {
                'file_path': file_path,
                'streamer_id': streamer_id,
                'stream_id': stream_id,
                **kwargs
            }
            self.state_manager.add_active_recording(recording_id, recording_data)
            
            # Start recording process
            success = await self._start_recording_process(recording_id, file_path, streamer_id)
            
            if success:
                # Send WebSocket notification
                if self.websocket_service:
                    await self.websocket_service.send_recording_started(
                        recording_id=recording_id,
                        streamer_id=streamer_id,
                        stream_id=stream_id,
                        file_path=file_path
                    )
                
                logger.info(f"Successfully started recording {recording_id}")
                return recording_id
            else:
                # Clean up on failure
                await self._cleanup_failed_recording(recording_id)
                return None
                
        except Exception as e:
            logger.error(f"Failed to start recording for stream {stream_id}: {e}")
            return None

    async def stop_recording(self, recording_id: int, reason: str = "manual") -> bool:
        """Stop an active recording"""
        try:
            recording_data = self.state_manager.get_active_recording(recording_id)
            if not recording_data:
                logger.warning(f"Recording {recording_id} not found in active recordings")
                return False
            
            logger.info(f"Stopping recording {recording_id}, reason: {reason}")
            
            # Stop the recording process
            success = await self._stop_recording_process(recording_id)
            
            # Update status regardless of process stop success
            await self.database_service.update_recording_status(
                recording_id=recording_id,
                status="stopped" if success else "failed"
            )
            
            # Remove from active recordings
            self.state_manager.remove_active_recording(recording_id)
            
            # Send WebSocket notification
            if self.websocket_service:
                await self.websocket_service.send_recording_status_update(
                    recording_id=recording_id,
                    status="stopped" if success else "failed",
                    additional_data={'reason': reason}
                )
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to stop recording {recording_id}: {e}")
            return False

    async def force_start_recording(self, streamer_id: int) -> Optional[int]:
        """Force start recording for a live streamer"""
        try:
            logger.info(f"Force starting recording for streamer {streamer_id}")
            
            # Get streamer info from Twitch
            streamer_data = await self.database_service.get_streamer_by_id(streamer_id)
            if not streamer_data:
                logger.error(f"Streamer {streamer_id} not found")
                return None
            
            # Check if streamer is live via Twitch API  
            twitch_id = streamer_data.twitch_id
            streams = await twitch_api.get_streams(user_ids=[twitch_id])
            
            if not streams:
                logger.warning(f"Streamer {streamer_id} is not live on Twitch")
                return None
            
            stream_info = streams[0]
            
            # Create or get stream record
            stream = await self._get_or_create_stream(streamer_id, stream_info)
            if not stream:
                logger.error("Failed to create stream record")
                return None
            
            # Start the recording
            recording_id = await self.start_recording(
                stream_id=stream.id,
                streamer_id=streamer_id,
                title=stream_info.get('title'),
                category_name=stream_info.get('game_name'),
                forced=True
            )
            
            if recording_id:
                logger.info(f"Successfully force started recording {recording_id} for streamer {streamer_id}")
            
            return recording_id
            
        except Exception as e:
            logger.error(f"Failed to force start recording for streamer {streamer_id}: {e}")
            return None

    async def monitor_and_process_recording(self, recording_id: int) -> None:
        """Monitor recording process and handle completion"""
        try:
            logger.info(f"Starting monitoring for recording {recording_id}")
            
            # Start monitoring task
            monitor_task = asyncio.create_task(
                self._monitor_recording_task(recording_id)
            )
            
            # Track the task
            self.state_manager.add_recording_task(recording_id, monitor_task)
            
            # Wait for completion
            await monitor_task
            
        except asyncio.CancelledError:
            logger.info(f"Recording {recording_id} monitoring cancelled")
        except Exception as e:
            logger.error(f"Error monitoring recording {recording_id}: {e}")
        finally:
            # Clean up task
            self.state_manager.remove_recording_task(recording_id)

    async def _monitor_recording_task(self, recording_id: int) -> None:
        """Internal monitoring task for recording"""
        try:
            while not self._is_shutting_down:
                recording_data = self.state_manager.get_active_recording(recording_id)
                if not recording_data:
                    logger.info(f"Recording {recording_id} no longer active, stopping monitoring")
                    break
                
                # Check if process is still running
                is_running = await self._check_recording_process(recording_id)
                if not is_running:
                    logger.info(f"Recording {recording_id} process finished")
                    await self._handle_recording_completion(recording_id)
                    break
                
                # Update progress if available
                await self._update_recording_progress(recording_id)
                
                # Sleep before next check
                await asyncio.sleep(10)  # Check every 10 seconds
                
        except Exception as e:
            logger.error(f"Error in recording monitoring task {recording_id}: {e}")
            await self._handle_recording_error(recording_id, str(e))

    async def _start_recording_process(self, recording_id: int, file_path: str, streamer_id: int) -> bool:
        """Start the actual recording process"""
        try:
            if not self.process_manager:
                logger.error("Process manager not available")
                return False
            
            # Start recording via process manager
            success = await self.process_manager.start_recording_process(
                recording_id=recording_id,
                file_path=file_path,
                streamer_id=streamer_id
            )
            
            if success:
                # Start monitoring task
                monitor_task = asyncio.create_task(
                    self.monitor_and_process_recording(recording_id)
                )
                self.state_manager.add_recording_task(recording_id, monitor_task)
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to start recording process {recording_id}: {e}")
            return False

    async def _stop_recording_process(self, recording_id: int) -> bool:
        """Stop the recording process"""
        try:
            if not self.process_manager:
                logger.warning("Process manager not available")
                return False
            
            # Cancel monitoring task
            self.state_manager.cancel_recording_task(recording_id)
            
            # Stop recording process
            success = await self.process_manager.stop_recording_process(recording_id)
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to stop recording process {recording_id}: {e}")
            return False

    async def _handle_recording_completion(self, recording_id: int) -> None:
        """Handle recording completion"""
        try:
            logger.info(f"Handling completion for recording {recording_id}")
            
            recording_data = self.state_manager.get_active_recording(recording_id)
            if not recording_data:
                logger.warning(f"Recording {recording_id} data not found")
                return
            
            file_path = recording_data.get('file_path')
            if not file_path or not Path(file_path).exists():
                logger.error(f"Recording file not found: {file_path}")
                await self.database_service.mark_recording_failed(
                    recording_id, "Recording file not found"
                )
                return
            
            # Update database status
            file_size = Path(file_path).stat().st_size
            await self.database_service.update_recording_status(
                recording_id=recording_id,
                status="completed",
                path=file_path
            )
            
            # Send completion notification
            if self.websocket_service:
                await self.websocket_service.send_recording_completed(
                    recording_id=recording_id,
                    file_path=file_path,
                    file_size=file_size
                )
            
            # Remove from active recordings
            self.state_manager.remove_active_recording(recording_id)
            
            logger.info(f"Recording {recording_id} completed successfully")
            
        except Exception as e:
            logger.error(f"Error handling recording completion {recording_id}: {e}")

    async def _handle_recording_error(self, recording_id: int, error_message: str) -> None:
        """Handle recording error"""
        try:
            logger.error(f"Recording {recording_id} error: {error_message}")
            
            # Update database
            await self.database_service.mark_recording_failed(recording_id, error_message)
            
            # Send error notification
            if self.websocket_service:
                await self.websocket_service.send_recording_error(
                    recording_id=recording_id,
                    error_message=error_message
                )
            
            # Remove from active recordings
            self.state_manager.remove_active_recording(recording_id)
            
        except Exception as e:
            logger.error(f"Error handling recording error {recording_id}: {e}")

    async def _generate_recording_path(self, streamer_id: int, stream_id: int) -> str:
        """Generate file path for recording"""
        try:
            # Get streamer info for filename generation
            streamer = await self.database_service.get_streamer_by_id(streamer_id)
            
            filename = await generate_filename(
                streamer_username=streamer.username if streamer else f"streamer_{streamer_id}",
                stream_id=stream_id,
                timestamp=datetime.now()
            )
            
            recordings_dir = self.config_manager.get_recordings_directory()
            return str(Path(recordings_dir) / filename)
            
        except Exception as e:
            logger.error(f"Failed to generate recording path: {e}")
            # Fallback path
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            return f"/recordings/recording_{streamer_id}_{stream_id}_{timestamp}.ts"

    # Shutdown methods
    
    async def graceful_shutdown(self) -> None:
        """Gracefully shutdown the lifecycle manager"""
        logger.info("Starting graceful shutdown of recording lifecycle manager")
        
        self._is_shutting_down = True
        self._shutdown_event.set()
        
        # Stop all active recordings
        active_recordings = self.state_manager.get_active_recordings()
        for recording_id in active_recordings:
            await self.stop_recording(recording_id, reason="shutdown")
        
        # Cancel all monitoring tasks
        cancelled_tasks = self.state_manager.cancel_all_tasks()
        if cancelled_tasks:
            logger.info(f"Cancelled {len(cancelled_tasks)} monitoring tasks")
        
        logger.info("Recording lifecycle manager shutdown complete")

    def is_shutting_down(self) -> bool:
        """Check if shutting down"""
        return self._is_shutting_down

    async def wait_for_shutdown(self) -> None:
        """Wait for shutdown to complete"""
        await self._shutdown_event.wait()

    # Helper methods
    
    async def _check_recording_process(self, recording_id: int) -> bool:
        """Check if recording process is still running"""
        if not self.process_manager:
            return False
        return await self.process_manager.is_recording_active(recording_id)

    async def _update_recording_progress(self, recording_id: int) -> None:
        """Update recording progress"""
        try:
            if not self.process_manager:
                return
            
            progress = await self.process_manager.get_recording_progress(recording_id)
            if progress is not None:
                self.state_manager.update_active_recording(recording_id, {'progress': progress})
                
                if self.websocket_service:
                    await self.websocket_service.send_recording_progress_update(
                        recording_id=recording_id,
                        progress=progress
                    )
        except Exception as e:
            logger.debug(f"Failed to update progress for recording {recording_id}: {e}")

    async def _cleanup_failed_recording(self, recording_id: int) -> None:
        """Clean up after a failed recording start"""
        try:
            self.state_manager.remove_active_recording(recording_id)
            await self.database_service.mark_recording_failed(
                recording_id, "Failed to start recording process"
            )
        except Exception as e:
            logger.error(f"Error cleaning up failed recording {recording_id}: {e}")

    async def _get_or_create_stream(self, streamer_id: int, stream_info: Dict[str, Any]):
        """Get existing stream or create new one"""
        # This would typically involve database operations
        # For now, return a mock stream object
        class MockStream:
            def __init__(self):
                self.id = hash(f"{streamer_id}_{stream_info.get('id', 'unknown')}")
        
        return MockStream()
