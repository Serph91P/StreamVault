"""
RecordingLifecycleManager - Recording start/stop lifecycle management

Extracted from recording_service.py ULTRA-BOSS (1084 lines)  
Handles recording start, stop, monitoring, and lifecycle events.
"""

import logging
import asyncio
from typing import Dict, Any, Optional
import re
from datetime import datetime
from pathlib import Path
from app.utils.path_utils import generate_filename, update_episode_number
from app.services.api.twitch_api import twitch_api
try:
    from app.utils.cache import app_cache
except ImportError:
    # Fallback if cache module is not available
    class DummyCache:
        def delete(self, key): pass
        def get(self, key): return None
        def set(self, key, value, ttl=None): pass
    app_cache = DummyCache()

# Import background queue service at module level to avoid repeated imports
try:
    from app.services.background_queue_service import background_queue_service
except ImportError:
    background_queue_service = None

logger = logging.getLogger("streamvault")

# Constants for recording progress tracking
RUNNING_PROGRESS_PERCENT = 50.0  # Show 50% for running recordings


class RecordingLifecycleManager:
    """Manages recording lifecycle events and monitoring"""
    
    # Constants for segment file patterns
    SEGMENT_FILE_PATTERN = "*_part*.ts"
    SEGMENT_DIR_SUFFIX = "_segments"
    SEGMENT_PART_IDENTIFIER = "_part"
    
    # Supported video extensions for filename cleanup
    SUPPORTED_VIDEO_EXTENSIONS = ['.mp4', '.ts', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm']
    
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
            logger.info(f"🎬 LIFECYCLE_START: stream_id={stream_id}, streamer_id={streamer_id}")
            
            # SECURITY FIX: Always derive the correct streamer_id from the stream to prevent mismatches
            stream = await self.database_service.get_stream_by_id(stream_id)
            if not stream:
                logger.error(f"🎬 NO_STREAM: stream_id={stream_id}")
                return None
            
            # Use authoritative streamer_id from the stream, not the parameter
            authoritative_streamer_id = stream.streamer_id
            if authoritative_streamer_id != streamer_id:
                logger.warning(f"🚨 PARAMETER_MISMATCH_CORRECTED: Provided streamer_id={streamer_id} != stream.streamer_id={authoritative_streamer_id}. Using authoritative value.")
            
            # Use the authoritative streamer_id from here on
            streamer_id = authoritative_streamer_id
            
            if self._is_shutting_down:
                logger.warning("🎬 SHUTDOWN_BLOCK: Cannot start recording during shutdown")
                return None
            
            # Check capacity
            if not self.state_manager.can_start_new_recording():
                # Provide richer capacity info for diagnostics
                try:
                    active = self.state_manager.get_active_recording_count()
                    limit = self.state_manager.max_concurrent_recordings
                    logger.warning(f"🎬 CAPACITY_BLOCK: Cannot start recording: at maximum capacity ({active}/{limit})")
                except Exception:
                    logger.warning("🎬 CAPACITY_BLOCK: Cannot start recording: at maximum capacity")
                return None
            
            # Generate file path
            file_path = await self._generate_recording_path(streamer_id, stream_id)
            
            # Create recording in database
            recording = await self.database_service.create_recording(
                stream_id=stream_id,
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
                # Invalidate active recordings cache
                app_cache.delete("active_recordings")
                
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
            
            # Trigger database event for orphaned recovery
            try:
                from app.services.recording.database_event_orphaned_recovery import on_recording_status_changed
                await on_recording_status_changed(recording_id, "active", "stopped" if success else "failed")
            except Exception as e:
                logger.debug(f"Could not trigger database event for orphaned recovery: {e}")
            
            # Remove from active recordings
            self.state_manager.remove_active_recording(recording_id)
            
            # Invalidate active recordings cache
            app_cache.delete("active_recordings")
            
            # Send WebSocket notification
            if self.websocket_service:
                await self.websocket_service.send_recording_status_update(
                    recording_id=recording_id,
                    status="stopped" if success else "failed",
                    additional_data={'reason': reason}
                )
            
            # Trigger post-processing for automatic stops (stream ended)
            # Even if process termination failed, streamlink may have finished correctly
            if reason == "automatic":
                logger.info(f"🎬 TRIGGERING_POST_PROCESSING: recording_id={recording_id}, success={success}")
                # PRODUCTION FIX: Run post-processing asynchronously to avoid blocking the stream offline handler
                asyncio.create_task(self._trigger_post_processing_async(recording_id))
            
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
            logger.info(f"🎬 LIFECYCLE_START_PROCESS: recording_id={recording_id}, file_path={file_path}")
            
            if not self.process_manager:
                logger.error("🎬 NO_PROCESS_MANAGER: Process manager not available")
                return False
            
            # Get the Stream object from the recording to use the new API properly
            recording = self.database_service.get_recording_by_id(recording_id)
            if not recording:
                logger.error(f"🎬 NO_RECORDING: Recording {recording_id} not found")
                return False
            
            stream = await self.database_service.get_stream_by_id(recording.stream_id)
            if not stream:
                logger.error(f"🎬 NO_STREAM: Stream {recording.stream_id} not found for recording {recording_id}")
                return False
            
            logger.info(f"🎬 CALLING_NEW_API: stream_id={stream.id}, output_path={file_path}")
            
            # Use the new ProcessManager API with proper parameters
            process = await self.process_manager.start_recording_process(
                stream=stream,
                output_path=file_path,
                quality="best"  # TODO: Get quality from recording settings
            )
            
            success = process is not None
            
            if success:
                # Register recording as external task in background queue for monitoring
                try:
                    if background_queue_service:
                        task_payload = {
                            'recording_id': recording_id,
                            'streamer_id': streamer_id,
                            'streamer_name': stream.streamer.username if stream.streamer else 'Unknown',
                            'stream_id': stream.id,
                            'file_path': file_path
                        }
                        background_queue_service.add_external_task(
                            f"recording_{recording_id}",
                            "recording",
                            task_payload
                        )
                        logger.debug(f"Registered recording {recording_id} as external task")
                except Exception as e:
                    logger.warning(f"Failed to register recording {recording_id} as external task: {e}")
                
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
            logger.info(f"🎬 LIFECYCLE_STOP_PROCESS: recording_id={recording_id}")
            
            if not self.process_manager:
                logger.warning("🎬 NO_PROCESS_MANAGER: Process manager not available")
                return False
            
            # Cancel monitoring task
            self.state_manager.cancel_recording_task(recording_id)
            
            # Get recording to find stream ID
            recording = self.database_service.get_recording_by_id(recording_id)
            if not recording:
                logger.error(f"🎬 NO_RECORDING: Recording {recording_id} not found for stop")
                return False
            
            # Use new ProcessManager API - process_id format is "stream_{stream_id}"
            process_id = f"stream_{recording.stream_id}"
            logger.info(f"🎬 TERMINATING_PROCESS: process_id={process_id}")
            
            success = await self.process_manager.terminate_process(process_id)
            logger.info(f"🎬 STOP_RESULT: success={success}")
            
            return success
            
        except Exception as e:
            logger.error(f"🎬 STOP_ERROR: Failed to stop recording process {recording_id}: {e}")
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
                    file_size=file_size,
                    additional_data={
                        'stream_id': recording_data.get('stream_id')
                    }
                )
            
            # Remove from active recordings
            self.state_manager.remove_active_recording(recording_id)
            
            # Complete external task in background queue - CRITICAL FIX for stuck recordings
            try:
                if background_queue_service:
                    task_id = f"recording_{recording_id}"
                    background_queue_service.complete_external_task(task_id, success=True)
                    
                    # Also remove from external tasks to prevent UI showing as stuck
                    if hasattr(background_queue_service, 'progress_tracker'):
                        background_queue_service.progress_tracker.remove_external_task(task_id)
                    
                    logger.info(f"✅ EXTERNAL_TASK_COMPLETED: recording_{recording_id} marked as completed and removed")
            except Exception as e:
                logger.error(f"❌ EXTERNAL_TASK_ERROR: Failed to complete external task for recording {recording_id}: {e}")
            
            logger.info(f"Recording {recording_id} completed successfully")
            
        except Exception as e:
            logger.error(f"Error handling recording completion {recording_id}: {e}")

    async def _handle_recording_error(self, recording_id: int, error_message: str) -> None:
        """Handle recording error"""
        try:
            logger.error(f"Recording {recording_id} error: {error_message}")
            
            # Update database
            await self.database_service.mark_recording_failed(recording_id, error_message)
            
            # Mark external task as failed in background queue - CRITICAL FIX for stuck recordings
            try:
                if background_queue_service:
                    task_id = f"recording_{recording_id}"
                    background_queue_service.complete_external_task(task_id, success=False)
                    
                    # Also remove from external tasks to prevent UI showing as stuck
                    if hasattr(background_queue_service, 'progress_tracker'):
                        background_queue_service.progress_tracker.remove_external_task(task_id)
                    
                    logger.info(f"❌ EXTERNAL_TASK_FAILED: recording_{recording_id} marked as failed and removed")
            except Exception as e:
                logger.error(f"❌ EXTERNAL_TASK_ERROR: Failed to mark external task as failed for recording {recording_id}: {e}")
            
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
            logger.info(f"🎬 GENERATE_PATH: streamer_id={streamer_id}, stream_id={stream_id}")
            
            # Get streamer and stream info for filename generation
            stream = await self.database_service.get_stream_by_id(stream_id)
            # Always derive streamer from the stream to avoid mismatches
            if not stream:
                logger.error(f"🎬 NO_STREAM: stream_id={stream_id}")
                raise Exception(f"Stream {stream_id} not found")

            # If a mismatched streamer_id was provided, log and correct it
            if stream.streamer_id != streamer_id:
                logger.error(
                    f"🚨 CRITICAL_STREAMER_MISMATCH: provided_streamer_id={streamer_id} does not match stream.streamer_id={stream.streamer_id} for stream_id={stream_id}; using authoritative value from stream"
                )
                logger.error(f"🚨 This indicates a serious bug in the event handling or stream creation logic!")

            streamer = await self.database_service.get_streamer_by_id(stream.streamer_id)
            
            if not streamer:
                logger.error(f"🎬 NO_STREAMER: streamer_id={streamer_id}")
                raise Exception(f"Streamer {streamer_id} not found")
            
            # Create stream_data dictionary for generate_filename
            stream_data = {
                "id": stream.id,
                "title": stream.title or "Unknown Stream",
                "category_name": stream.category_name or "Unknown",
                "language": stream.language or "en",
                "started_at": stream.started_at or datetime.now()
            }
            
            logger.info(f"🎬 CALLING_GENERATE_FILENAME: streamer={streamer.username}")
            
            # Use media server structure template (like Plex/Jellyfin) - no extension here!
            template = "Season {year}-{month}/{streamer} - S{year}{month}E{episode:02d} - {title}"
            
            filename = await generate_filename(
                streamer=streamer,
                stream_data=stream_data,
                template=template
            )

            # Try to persist the month-episode number we just used into the Stream
            try:
                # Extract E## from the generated filename pattern SYYYYMME##
                m = re.search(r"S(\d{6})E(\d{2})", filename)
                if m:
                    episode_num = int(m.group(2))
                    # Persist on Stream for later consumers (NFO, APIs)
                    await update_episode_number(stream.id, episode_num)
            except Exception:
                logger.exception("Failed to update episode number for stream %s", stream.id)
            
            # Clean up filename and add .ts extension
            # Remove any existing video extensions from the filename (case-insensitive)
            for ext in self.SUPPORTED_VIDEO_EXTENSIONS:
                if filename.lower().endswith(ext):
                    filename = filename[:-len(ext)]
                    break  # Stop after first match to avoid unnecessary iterations
            
            # Add .ts extension
            filename += '.ts'
            
            # Hardcoded Docker path - always /recordings in container
            recordings_dir = "/recordings"
            
            # Create full path with streamer directory and season structure
            streamer_dir = Path(recordings_dir) / streamer.username
            full_path = str(streamer_dir / filename)
            
            # Ensure directory exists
            season_dir = streamer_dir / filename.split('/')[0]  # Extract season directory
            season_dir.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"🎬 GENERATED_PATH: {full_path}")
            return full_path
            
        except Exception as e:
            logger.error(f"🎬 GENERATE_PATH_ERROR: Failed to generate recording path: {e}", exc_info=True)
            # Fallback path
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            fallback_path = f"/recordings/recording_{streamer_id}_{stream_id}_{timestamp}.ts"
            logger.info(f"🎬 FALLBACK_PATH: {fallback_path}")
            return fallback_path

    async def _trigger_post_processing_async(self, recording_id: int):
        """Trigger post-processing asynchronously to avoid blocking the stream offline handler"""
        try:
            logger.info(f"🎬 POST_PROCESSING_ASYNC_START: recording_id={recording_id}")
            
            # Add a small delay to ensure the stream offline handler completes first
            await asyncio.sleep(0.1)
            
            # Call the synchronous post-processing method
            await self._trigger_post_processing(recording_id)
            
        except Exception as e:
            logger.error(f"Error in async post-processing for recording {recording_id}: {e}", exc_info=True)

    async def _trigger_post_processing(self, recording_id: int):
        """Trigger post-processing for a completed recording"""
        try:
            logger.info(f"🎬 POST_PROCESSING_START: recording_id={recording_id}")
            
            # Get recording info
            recording_data = self.database_service.get_recording_by_id(recording_id)
            if not recording_data:
                logger.error(f"Recording {recording_id} not found for post-processing")
                return
            
            # Get stream info
            stream_data = await self.database_service.get_stream_by_id(recording_data.stream_id)
            if not stream_data:
                logger.error(f"Stream {recording_data.stream_id} not found for post-processing")
                return
            
            # Get streamer info
            streamer_data = await self.database_service.get_streamer_by_id(stream_data.streamer_id)
            if not streamer_data:
                logger.error(f"Streamer {stream_data.streamer_id} not found for post-processing")
                return
            
            # For segmented recordings, find the actual segments
            recording_path = recording_data.path
            if not recording_path:
                logger.error(f"No recording path found for recording {recording_id}")
                return
                
            # Check if this is a segmented recording
            segments_dir = recording_path.replace('.ts', self.SEGMENT_DIR_SUFFIX)
            if Path(segments_dir).exists():
                logger.info(f"🎬 SEGMENTED_RECORDING_DETECTED: {segments_dir}")
                
                # Find all segment files
                segment_files = list(Path(segments_dir).glob(self.SEGMENT_FILE_PATTERN))
                segment_files.sort()  # Sort to maintain order
                
                if segment_files:
                    logger.info(f"🎬 FOUND_SEGMENTS: {len(segment_files)} segments")
                    
                    # PRODUCTION FIX: Queue segment concatenation as background task instead of blocking
                    logger.info(f"🎬 QUEUING_SEGMENT_CONCATENATION: {len(segment_files)} files for recording {recording_id}")
                    
                    # Queue segment concatenation task first
                    await self._queue_segment_concatenation_task(recording_id, segment_files, recording_path, streamer_data)
                    return  # Exit here - post-processing will continue after concatenation
                else:
                    logger.warning(f"🎬 NO_SEGMENTS_FOUND: {segments_dir}")
                    return
            
            # Verify the recording file exists
            if not Path(recording_path).exists():
                logger.error(f"🎬 RECORDING_FILE_NOT_FOUND: {recording_path}")
                return
            
            file_size = Path(recording_path).stat().st_size
            logger.info(f"🎬 RECORDING_FILE_FOUND: {recording_path} ({file_size} bytes)")
            
            # Import TaskPriority only, background_queue_service already imported at module level
            from app.services.queues.task_progress_tracker import TaskPriority
            background_queue = background_queue_service
            
            # Schedule post-processing tasks with dependencies
            logger.info(f"🎬 SCHEDULING_POST_PROCESSING_TASKS: recording_id={recording_id}")
            
            import os
            mp4_path = recording_path.replace('.ts', '.mp4')
            base_filename = os.path.splitext(os.path.basename(mp4_path))[0]
            output_dir = os.path.dirname(mp4_path)
            
            # 1. Metadata generation task (run first)
            metadata_task_id = await background_queue.enqueue_task_with_dependencies(
                "metadata_generation",
                {
                    "recording_id": recording_id,
                    "stream_id": stream_data.id,
                    "streamer_id": streamer_data.id,
                    "base_filename": base_filename,
                    "output_dir": output_dir,
                    "video_path": mp4_path,
                    "streamer_name": streamer_data.username,
                    "stream_title": stream_data.title or "Unknown Stream"
                },
                dependencies=[],  # No dependencies - run first
                priority=TaskPriority.HIGH
            )
            
            # 2. MP4 remux task (after metadata)
            mp4_remux_task_id = await background_queue.enqueue_task_with_dependencies(
                "mp4_remux",
                {
                    "recording_id": recording_id,
                    "stream_id": stream_data.id,
                    "ts_file_path": recording_path,
                    "mp4_output_path": mp4_path,
                    "streamer_name": streamer_data.username,
                    "stream_title": stream_data.title or "Unknown Stream"
                },
                dependencies=[metadata_task_id],  # Wait for metadata
                priority=TaskPriority.HIGH
            )
            
            # 3. Thumbnail generation task (after MP4 remux)
            thumbnail_task_id = await background_queue.enqueue_task_with_dependencies(
                "thumbnail_generation",
                {
                    "recording_id": recording_id,
                    "stream_id": stream_data.id,
                    "mp4_path": mp4_path,
                    "output_dir": output_dir,
                    "streamer_name": streamer_data.username
                },
                dependencies=[mp4_remux_task_id],  # Wait for MP4 remux
                priority=TaskPriority.NORMAL
            )
            
            # 4. Cleanup task (after everything)
            files_to_remove = [recording_path]  # Remove .ts file
            
            # Also remove segments directory if it exists
            segments_dir = recording_path.replace('.ts', self.SEGMENT_DIR_SUFFIX)
            if Path(segments_dir).exists():
                files_to_remove.append(segments_dir)
                logger.info(f"🎬 CLEANUP_SCHEDULED: Will remove segments directory {segments_dir}")
            
            # Ensure all required fields are present in cleanup payload
            cleanup_payload = {
                "recording_id": recording_id,
                "stream_id": stream_data.id,
                "files_to_remove": files_to_remove,
                "mp4_path": mp4_path,
                "streamer_name": streamer_data.username,
                "intelligent_cleanup": True,
                "max_wait_time": 300
            }
            
            logger.info(f"🎬 CLEANUP_PAYLOAD: {cleanup_payload}")
            
            await background_queue.enqueue_task_with_dependencies(
                "cleanup",
                cleanup_payload,
                dependencies=[thumbnail_task_id],  # Wait for thumbnail generation
                priority=TaskPriority.LOW
            )
            
            logger.info(f"🎬 POST_PROCESSING_SCHEDULED: recording_id={recording_id}")
            
        except Exception as e:
            logger.error(f"Error triggering post-processing for recording {recording_id}: {e}", exc_info=True)

    async def _queue_segment_concatenation_task(self, recording_id: int, segment_files: list, recording_path: str, streamer_data):
        """Queue segment concatenation as a background task to avoid blocking the stream offline handler"""
        try:
            from app.services.queues.task_progress_tracker import TaskPriority
            
            # Create concatenation task payload
            concat_payload = {
                'recording_id': recording_id,
                'segment_files': [str(f) for f in segment_files],
                'output_path': recording_path,
                'streamer_name': streamer_data.username,
                'stream_id': recording_id,  # Use recording_id as fallback for stream_id
            }
            
            # Enqueue segment concatenation task with high priority
            concat_task_id = await background_queue_service.enqueue_task(
                task_type='segment_concatenation',
                payload=concat_payload,
                priority=TaskPriority.HIGH  # High priority for immediate processing
            )
            
            logger.info(f"🎬 SEGMENT_CONCATENATION_QUEUED: task_id={concat_task_id}, recording_id={recording_id}")
            
        except Exception as e:
            logger.error(f"Error queuing segment concatenation for recording {recording_id}: {e}", exc_info=True)

    async def _concatenate_segments(self, segment_files: list, recording_id: int) -> Optional[Path]:
        """Concatenate multiple .ts segments into a single file using FFmpeg"""
        try:
            logger.info(f"🎬 CONCATENATING_SEGMENTS: {len(segment_files)} files for recording {recording_id}")
            
            # Create output path with input validation
            first_segment = Path(segment_files[0])
            if not first_segment.exists() or not first_segment.is_file():
                logger.error(f"🎬 INVALID_SEGMENT_FILE: {first_segment}")
                return None
                
            # Validate recording_id is numeric to prevent injection
            if not isinstance(recording_id, int) or recording_id <= 0:
                logger.error(f"🎬 INVALID_RECORDING_ID: {recording_id}")
                return None
                
            output_path = first_segment.parent.parent / f"{first_segment.stem.split(self.SEGMENT_PART_IDENTIFIER)[0]}.ts"
            
            # Validate output path doesn't contain dangerous shell characters
            if any(char in str(output_path) for char in [';', '|', '&', '`', '$']):
                logger.error(f"🎬 UNSAFE_OUTPUT_PATH: {output_path}")
                return None
            
            # Create concat file list for FFmpeg with safe path validation
            concat_file_path = first_segment.parent / f"concat_list_{recording_id}.txt"
            
            # Validate all segment files exist and are safe
            validated_segments = []
            for segment in segment_files:
                segment_path = Path(segment)
                if not segment_path.exists() or not segment_path.is_file():
                    logger.warning(f"🎬 SKIPPING_INVALID_SEGMENT: {segment}")
                    continue
                if not segment_path.suffix == '.ts':
                    logger.warning(f"🎬 SKIPPING_NON_TS_SEGMENT: {segment}")
                    continue
                validated_segments.append(segment_path)
            
            if not validated_segments:
                logger.error("🎬 NO_VALID_SEGMENTS_FOUND")
                return None
            
            # Write concat file with escaped paths
            with open(concat_file_path, 'w', encoding='utf-8') as f:
                for segment in validated_segments:
                    # Use relative paths and escape single quotes
                    safe_name = segment.name.replace("'", "'\"'\"'")
                    f.write(f"file '{safe_name}'\n")
            
            # Run FFmpeg concatenation with safe arguments
            import subprocess
            ffmpeg_cmd = [
                "ffmpeg",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_file_path),
                "-c", "copy",
                "-y",  # Overwrite output file
                str(output_path)
            ]
            
            logger.debug(f"🎬 FFMPEG_CONCAT_CMD: {' '.join(ffmpeg_cmd)}")
            
            # Execute FFmpeg command with timeout and safe environment
            try:
                process = await asyncio.wait_for(
                    asyncio.create_subprocess_exec(
                        *ffmpeg_cmd,
                        cwd=str(first_segment.parent),  # Set working directory
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        env={"PATH": "/usr/bin:/bin"}  # Restricted environment
                    ),
                    timeout=300  # 5 minute timeout
                )
                
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=600  # 10 minute timeout for large files
                )
                
            except asyncio.TimeoutError:
                logger.error("🎬 CONCATENATION_TIMEOUT: FFmpeg process timed out")
                if 'process' in locals():
                    process.kill()
                return None
            
            if process.returncode == 0:
                logger.info(f"🎬 CONCATENATION_SUCCESS: {output_path}")
                
                # Verify output file was created and has reasonable size
                if output_path.exists() and output_path.stat().st_size > 0:
                    # Clean up concat file
                    try:
                        concat_file_path.unlink()
                    except Exception as e:
                        logger.warning(f"Could not remove concat file: {e}")
                    
                    return output_path
                else:
                    logger.error("🎬 CONCATENATION_FAILED: Output file not created or empty")
                    return None
            else:
                logger.error(f"🎬 CONCATENATION_FAILED: FFmpeg returned {process.returncode}")
                
                # Safe stderr decoding with error handling
                try:
                    stderr_text = stderr.decode('utf-8', errors='replace')
                except Exception as e:
                    stderr_text = f"Could not decode stderr: {e}"
                
                logger.error(f"FFmpeg stderr: {stderr_text}")
                return None
                
        except Exception as e:
            logger.error(f"Error concatenating segments for recording {recording_id}: {e}", exc_info=True)
            return None

    # Shutdown methods
    
    async def graceful_shutdown(self, timeout: int | None = None) -> None:
        """Gracefully shutdown the lifecycle manager
        
        Args:
            timeout: Optional timeout hint (seconds) for terminating recording processes.
        """
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
        
        # Also request ProcessManager to gracefully shutdown subprocesses if available
        try:
            if self.process_manager and hasattr(self.process_manager, 'graceful_shutdown'):
                await self.process_manager.graceful_shutdown(timeout=timeout or 15)
        except Exception as e:
            logger.warning(f"ProcessManager graceful shutdown encountered an error: {e}")
        
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
        try:
            if not self.process_manager:
                return False
            
            # Get recording to find stream ID
            recording = self.database_service.get_recording_by_id(recording_id)
            if not recording:
                return False
            
            # Check if process is active using new API
            process_id = f"stream_{recording.stream_id}"
            is_active = process_id in self.process_manager.active_processes
            
            return is_active
            
        except Exception as e:
            logger.error(f"🎬 CHECK_PROCESS_ERROR: {e}")
            return False

    async def _update_recording_progress(self, recording_id: int) -> None:
        """Update recording progress"""
        try:
            if not self.process_manager:
                return
            
            progress = await self.process_manager.get_recording_progress(recording_id)
            if progress is not None and isinstance(progress, dict):
                # Extract duration as a simple percentage (for now, just show that it's running)
                if progress.get("status") == "running":
                    progress_percent = RUNNING_PROGRESS_PERCENT  # Show 50% for running recordings
                elif progress.get("status") == "completed":
                    progress_percent = 100.0
                else:
                    progress_percent = 0.0
                    
                progress_percent = min(100.0, max(0.0, progress_percent))
                self.state_manager.update_active_recording(recording_id, {'progress': progress_percent})
                
                # Update external task progress in background queue
                try:
                    if background_queue_service:
                        background_queue_service.update_external_task_progress(
                            f"recording_{recording_id}",
                            progress_percent
                        )
                        logger.debug(f"HEARTBEAT recording_{recording_id} progress={progress_percent}")
                except Exception as e:
                    logger.debug(f"Failed to update external task progress: {e}")
                
                if self.websocket_service:
                    await self.websocket_service.send_recording_progress_update(
                        recording_id=recording_id,
                        progress=progress_percent
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
            
            # Mark external task as failed in background queue
            try:
                if background_queue_service:
                    background_queue_service.complete_external_task(
                        f"recording_{recording_id}",
                        success=False
                    )
                    logger.debug(f"Marked recording {recording_id} as failed in background queue")
            except Exception as e:
                logger.warning(f"Failed to mark external task as failed for recording {recording_id}: {e}")
                
        except Exception as e:
            logger.error(f"Error cleaning up failed recording {recording_id}: {e}")

    async def _get_or_create_stream(self, streamer_id: int, stream_info: Dict[str, Any]):
        """Get existing stream or create new one"""
        try:
            # Check if stream already exists
            existing_stream = await self.database_service.get_stream_by_twitch_stream_id(
                stream_info.get('id', 'Unknown')
            )
            
            if existing_stream:
                return existing_stream
            
            # Create new stream
            stream_data = {
                'streamer_id': streamer_id,
                'title': stream_info.get('title', 'Unknown Stream'),
                'category_name': stream_info.get('game_name', 'Unknown'),
                'language': stream_info.get('language', 'en'),
                'started_at': datetime.now(),
                'is_live': True,
                'twitch_stream_id': stream_info.get('id', 'Unknown')  # Use consistent field name
            }
            
            return await self.database_service.create_stream(stream_data)
            
        except Exception as e:
            logger.error(f"Failed to get or create stream: {e}")
            return None
