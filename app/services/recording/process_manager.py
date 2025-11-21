"""
Process management for recording service.

This module handles subprocess creation and management, specifically for streamlink recording processes.
Includes support for 24h+ streams through segment splitting and automatic process rotation.

Dependency Injection:
    The ProcessManager can accept a post_processing_callback in its constructor or via 
    set_post_processing_callback() to avoid circular imports and follow proper architecture.
    
    Example usage:
        async def post_processing_callback(recording_id: int, file_path: str):
            # Handle post-processing for completed recording
            pass
            
        process_manager = ProcessManager(post_processing_callback=post_processing_callback)
"""
import logging
import asyncio
import os
import shutil
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple, Callable, Awaitable
from pathlib import Path
from sqlalchemy.orm import joinedload

# Import utilities
from app.utils.streamlink_utils import get_streamlink_command, get_proxy_settings_from_db
from app.services.recording.exceptions import ProcessError, StreamUnavailableError
from app.models import Stream
from app.utils import async_file
from app.config.constants import ASYNC_DELAYS, TIMEOUTS

logger = logging.getLogger("streamvault")

# ProcessMonitor integration temporarily disabled for stability
process_monitor = None
ProcessType = None
ProcessStatus = None

class ProcessManager:
    """Manages subprocess execution and cleanup for recording processes"""

    # Constants for segment file patterns (must match RecordingLifecycleManager)
    SEGMENT_PART_IDENTIFIER = "_part"

    def __init__(self, config_manager=None, post_processing_callback: Optional[Callable[[int, str], Awaitable[None]]] = None):
        self.active_processes = {}
        self.long_stream_processes = {}  # Track processes that need segmentation
        self.lock = asyncio.Lock()
        self.config_manager = config_manager
        self.post_processing_callback = post_processing_callback  # Injected dependency
        
        # Configuration for long stream handling (avoid streamlink 24h cutoff)
        self.segment_duration_hours = 23.98  # Split streams at 23h59min to avoid streamlink cutoff
        self.max_file_size_gb = 100  # Start new segment if file exceeds this size
        self.monitor_interval_seconds = 600  # Check every 10 minutes (less frequent)
        
        # Initialize structured logging service
        try:
            from app.services.system.logging_service import logging_service
            self.logging_service = logging_service
            logger.info(f"✅ ProcessManager: Logging service initialized - {logging_service.logs_base_dir}")
        except Exception as e:
            logger.warning(f"❌ ProcessManager: Could not initialize logging service: {e}")
            self.logging_service = None
        
        # Try to import psutil for process monitoring
        try:
            import psutil
            self.psutil_available = True
        except ImportError:
            self.psutil_available = False
            logger.warning("psutil not available - process monitoring will be limited")
        
        # Shutdown management
        self._is_shutting_down = False

    async def start_recording_process(
        self, stream: Stream, output_path: str, quality: str, recording_id: Optional[int] = None
    ) -> Optional[asyncio.subprocess.Process]:
        """Start a streamlink recording process for a specific stream
        
        Args:
            stream: Stream object to record
            output_path: Path where the recording should be saved
            quality: Quality setting for the stream
            recording_id: ID of the recording entry (optional, for segmented recording tracking)
            
        Returns:
            Process object or None if failed
        """
        try:
            # Initialize segmented recording for long streams
            segment_info = await self._initialize_segmented_recording(stream, output_path, quality, recording_id)
            
            # Start the first segment
            process = await self._start_segment(
                stream, segment_info['current_segment_path'], quality, segment_info
            )
            
            if process:
                # Start monitoring task for long stream management
                monitor_task = asyncio.create_task(
                    self._monitor_long_stream(stream, segment_info, quality)
                )
                segment_info['monitor_task'] = monitor_task
                
            return process
            
        except Exception as e:
            logger.error(f"Failed to start recording process for stream {stream.id}: {e}", exc_info=True)
            raise ProcessError(f"Failed to start recording: {e}")

    async def _initialize_segmented_recording(self, stream: Stream, output_path: str, quality: str, recording_id: Optional[int] = None) -> Dict:
        """Initialize segmented recording structure for long streams"""
        base_path = Path(output_path)
        segment_dir = base_path.parent / f"{base_path.stem}_segments"
        segment_dir.mkdir(parents=True, exist_ok=True)
        
        # Create first segment path
        segment_filename = f"{base_path.stem}{self.SEGMENT_PART_IDENTIFIER}001.ts"
        current_segment_path = segment_dir / segment_filename
        
        segment_info = {
            'stream_id': stream.id,
            'recording_id': recording_id,  # Store recording_id for proper post-processing
            'base_output_path': str(output_path),
            'segment_dir': str(segment_dir),
            'current_segment_path': str(current_segment_path),
            'segment_count': 1,
            'segment_start_time': datetime.now(),
            'total_segments': [],
            'monitor_task': None
        }
        
        process_id = f"stream_{stream.id}"
        async with self.lock:
            self.long_stream_processes[process_id] = segment_info
            
        logger.info(f"Initialized segmented recording for stream {stream.id}: {segment_dir}")
        return segment_info

    async def _start_segment(
        self, stream: Stream, segment_path: str, quality: str, segment_info: Dict
    ) -> Optional[asyncio.subprocess.Process]:
        """Start recording a single segment"""
        try:
            # Get streamer info via relationship or database
            streamer_name = None
            if hasattr(stream, 'streamer') and stream.streamer:
                # Use preloaded relationship if available (better performance)
                streamer_name = stream.streamer.username
            else:
                # Fallback to DB query if not preloaded
                from app.database import SessionLocal
                from app.models import Streamer
                
                with SessionLocal() as db:
                    streamer = db.query(Streamer).filter(Streamer.id == stream.streamer_id).first()
                    if not streamer:
                        raise Exception(f"Streamer {stream.streamer_id} not found")
                    streamer_name = streamer.username
            
            if not streamer_name:
                raise Exception(f"Could not resolve streamer name for stream {stream.id}")
            
            # Debug logging to track potential mismatches
            logger.info(f"🔍 PROCESS_DEBUG: stream_id={stream.id}, stream.streamer_id={stream.streamer_id}, streamer_name={streamer_name}")
            
            # ===== MULTI-PROXY SYSTEM: Get best available proxy =====
            # CRITICAL: This prevents recording failures when proxies go down
            # Uses health checks and automatic failover to select best proxy
            proxy_settings = None
            
            from app.database import SessionLocal
            from app.models import RecordingSettings
            
            with SessionLocal() as db:
                recording_settings = db.query(RecordingSettings).first()
                
                # Check if proxy system is enabled
                if recording_settings and hasattr(recording_settings, 'enable_proxy') and recording_settings.enable_proxy:
                    from app.services.proxy.proxy_health_service import proxy_health_service
                    
                    # Get best available proxy from health service
                    best_proxy_url = await proxy_health_service.get_best_proxy()
                    
                    if best_proxy_url:
                        # Use selected proxy
                        proxy_settings = {
                            'http': best_proxy_url,
                            'https': best_proxy_url
                        }
                        logger.info(f"✅ Using proxy for recording: {best_proxy_url[:50]}...")
                    else:
                        # No healthy proxies available
                        fallback_enabled = (
                            hasattr(recording_settings, 'fallback_to_direct_connection') 
                            and recording_settings.fallback_to_direct_connection
                        )
                        
                        if fallback_enabled:
                            logger.warning(f"⚠️ No healthy proxies available - using direct connection (fallback enabled)")
                            proxy_settings = None  # Direct connection
                        else:
                            error_msg = f"Cannot start recording for {streamer_name}: No healthy proxies available and fallback disabled"
                            logger.error(f"🔴 {error_msg}")
                            raise ProcessError(
                                "No healthy proxies available. Please check proxy settings or enable fallback to direct connection."
                            )
                else:
                    # Proxy system disabled - use direct connection
                    logger.info(f"ℹ️ Proxy system disabled - using direct connection")
                    proxy_settings = None
            
            # Get codec preferences (H.265/AV1 support - Streamlink 8.0.0+)
            # Priority: Streamer-specific > Global default
            supported_codecs = None
            oauth_token = None  # Will be set to fresh token if available
            
            from app.models import GlobalSettings, StreamerRecordingSettings
            from app.services.system.twitch_token_service import TwitchTokenService
            
            with SessionLocal() as db:
                # === STEP 1: Get fresh OAuth token (auto-refresh if needed) ===
                try:
                    token_service = TwitchTokenService(db)
                    oauth_token = await token_service.get_valid_access_token()
                    
                    if oauth_token:
                        logger.info(f"🔑 Using auto-refreshed OAuth token for {streamer_name}")
                    else:
                        logger.debug(f"ℹ️ No OAuth token available - H.265/1440p quality unavailable")
                except Exception as e:
                    logger.warning(f"Failed to get OAuth token: {e}")
                    oauth_token = None
                
                # === STEP 2: Get codec preferences ===
                # Try to get per-streamer codec preference first
                streamer_settings = db.query(StreamerRecordingSettings).filter(
                    StreamerRecordingSettings.streamer_id == stream.streamer_id
                ).first()
                
                if streamer_settings and streamer_settings.supported_codecs:
                    # Per-streamer override
                    supported_codecs = streamer_settings.supported_codecs
                    logger.info(f"🎨 Using per-streamer codec preference for {streamer_name}: {supported_codecs}")
                else:
                    # Fallback to global default
                    global_settings = db.query(GlobalSettings).first()
                    if global_settings and hasattr(global_settings, 'supported_codecs'):
                        supported_codecs = global_settings.supported_codecs
                        logger.debug(f"🎨 Using global codec preference: {supported_codecs}")
            
            # NOTE: Proxy connectivity is now handled by ProxyHealthService
            # The health check system continuously monitors proxy status and only
            # returns healthy proxies. No need for manual connectivity check here.
            
            logger.info(f"🎬 PROCESS_START_SEGMENT: stream_id={stream.id}, streamer={streamer_name}")
            
            # Generate streamlink command for this segment
            # Note: Global settings (OAuth, default proxy/codecs) are in config.twitch
            # CLI parameters here override config for per-streamer customization
            cmd = get_streamlink_command(
                streamer_name=streamer_name,
                quality=quality,
                output_path=segment_path,
                proxy_settings=proxy_settings,  # Per-recording proxy override (from health check)
                supported_codecs=supported_codecs,  # Per-streamer codec preference (overrides global)
                oauth_token=oauth_token  # Auto-refreshed OAuth token (overrides config)
            )
            
            logger.info(f"🎬 Starting segment {segment_info['segment_count']} for {streamer_name}")
            logger.debug(f"🎬 Segment path: {segment_path}")
            # SECURITY: Sanitize command for logging to prevent token exposure (CWE-532)
            from app.utils.security import sanitize_command_for_logging
            logger.debug(f"🎬 Streamlink command: {sanitize_command_for_logging(cmd)}")
            
            # Log to structured logging service
            if self.logging_service:
                # The logging service now automatically creates streamer-specific directories
                streamlink_log_path = self.logging_service.log_streamlink_start(
                    streamer_name=streamer_name,
                    quality=quality,
                    output_path=segment_path,
                    cmd=cmd
                )
                
                logger.info(f"📂 Streamlink logs for {streamer_name} written to: {streamlink_log_path}")
                
                # Create additional streamer logger for direct output
                streamer_logger = logging.getLogger(f"streamlink.{streamer_name}")
                
                # Remove any existing FileHandler instances for this logger to prevent memory leaks
                for handler in list(streamer_logger.handlers):
                    if isinstance(handler, logging.FileHandler):
                        streamer_logger.removeHandler(handler)
                        handler.close()
                
                # Add a new FileHandler pointing to the streamer-specific log
                file_handler = logging.FileHandler(streamlink_log_path, mode='a', encoding='utf-8')
                file_handler.setFormatter(logging.Formatter('%(asctime)s %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
                streamer_logger.addHandler(file_handler)
                streamer_logger.setLevel(logging.INFO)
                streamer_logger.propagate = False
                
                streamer_logger.info(f"Starting streamlink recording for {streamer_name}")
                streamer_logger.info(f"Quality: {quality}")
                streamer_logger.info(f"Output: {segment_path}")
                # SECURITY: Sanitize command for logging to prevent token exposure (CWE-532)
                streamer_logger.info(f"Command: {sanitize_command_for_logging(cmd)}")
                streamer_logger.info(f"Segment: {segment_info['segment_count']}")
                streamer_logger.info("=" * 80)
            
            # Start the process
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Add immediate check to see if process started successfully
            await asyncio.sleep(ASYNC_DELAYS.PROCESS_START_GRACE)
            if process.returncode is not None:
                # Process already ended, capture output
                stdout, stderr = await process.communicate()
                logger.error(f"🎬 PROCESS_FAILED_IMMEDIATELY: PID would be {process.pid}, exit code {process.returncode}")
                logger.error(f"🎬 STDOUT: {stdout.decode()}")
                logger.error(f"🎬 STDERR: {stderr.decode()}")
                
                # Log to structured logging service
                if self.logging_service:
                    self.logging_service.log_streamlink_output(
                        streamer_name=streamer_name,
                        stdout=stdout,
                        stderr=stderr,
                        exit_code=process.returncode,
                        log_path=streamlink_log_path  # Pass the log path from start
                    )
                    
                    # Also append to the streamer-specific log file using proper logging
                    streamer_logger = logging.getLogger(f"streamlink.{streamer_name}")
                    try:
                        streamer_logger.error(f"PROCESS FAILED IMMEDIATELY (exit code: {process.returncode})")
                        if stdout:
                            streamer_logger.error(f"STDOUT:\n{stdout.decode()}")
                        if stderr:
                            streamer_logger.error(f"STDERR:\n{stderr.decode()}")
                    except Exception as e:
                        logger.warning(f"Could not write to streamlink log file: {e}")
                        
                raise ProcessError(f"Streamlink process failed immediately: {stderr.decode()}")
            
            process_id = f"stream_{stream.id}"
            async with self.lock:
                self.active_processes[process_id] = process
                
            # Add segment to the list
            segment_info['total_segments'].append({
                'path': segment_path,
                'start_time': datetime.now(),
                'process_pid': process.pid
            })
            
            # Register process with ProcessMonitor - temporarily disabled
            # if process_monitor and ProcessType:
            #     await process_monitor.register_process(
            #         process_id=f"streamlink_{stream.id}_{segment_info['segment_count']}",
            #         process_type=ProcessType.STREAMLINK,
            #         pid=process.pid,
            #         command=' '.join(cmd),
            #         streamer_id=stream.streamer_id,
            #         stream_id=stream.id,
            #         metadata={
            #             'segment_path': segment_path,
            #             'segment_count': segment_info['segment_count'],
            #             'quality': quality
            #         }
            #     )
                
            logger.info(f"Started segment recording for stream {stream.id} with PID {process.pid}")
            
            # Send Apprise notification for recording_started (NEW)
            try:
                from app.services.notifications.external_notification_service import ExternalNotificationService
                notification_service = ExternalNotificationService()
                
                await notification_service.send_recording_notification(
                    streamer_name=streamer_name,
                    event_type='recording_started',
                    details={
                        'quality': quality,
                        'stream_title': stream.title or 'N/A',
                        'category': stream.category_name or 'N/A'
                    }
                )
                
                logger.info(f"📧 Apprise notification sent: recording_started for {streamer_name}")
                
            except Exception as apprise_error:
                logger.error(f"Failed to send Apprise notification for recording_started: {apprise_error}")
            
            return process
            
        except Exception as e:
            logger.error(f"Failed to start segment recording for stream {stream.id}: {e}", exc_info=True)
            raise ProcessError(f"Failed to start segment recording: {e}")

    async def _monitor_long_stream(self, stream: Stream, segment_info: Dict, quality: str):
        """Monitor a long stream and handle segmentation"""
        process_id = f"stream_{stream.id}"
        
        try:
            while process_id in self.active_processes:
                await asyncio.sleep(self.monitor_interval_seconds)
                
                # Check if we need to start a new segment
                should_rotate = await self._should_rotate_segment(segment_info)
                
                if should_rotate:
                    logger.info(f"Rotating segment for stream {stream.id}")
                    await self._rotate_segment(stream, segment_info, quality)
                    
        except asyncio.CancelledError:
            logger.info(f"Long stream monitoring cancelled for stream {stream.id}")
        except Exception as e:
            logger.error(f"Error in long stream monitoring for stream {stream.id}: {e}", exc_info=True)

    async def _should_rotate_segment(self, segment_info: Dict) -> bool:
        """Check if we should start a new segment"""
        try:
            # Check duration
            duration = datetime.now() - segment_info['segment_start_time']
            if duration >= timedelta(hours=self.segment_duration_hours):
                logger.info(f"Segment duration limit reached: {duration}")
                return True
                
            # Check file size
            current_path = segment_info['current_segment_path']
            if await async_file.exists(current_path):
                file_size_gb = await async_file.getsize(current_path) / (1024**3)
                if file_size_gb >= self.max_file_size_gb:
                    logger.info(f"Segment file size limit reached: {file_size_gb:.2f} GB")
                    return True
                    
            return False
            
        except Exception as e:
            logger.error(f"Error checking segment rotation: {e}", exc_info=True)
            return False

    async def _rotate_segment(self, stream: Stream, segment_info: Dict, quality: str):
        """Rotate to a new segment file"""
        try:
            process_id = f"stream_{stream.id}"
            
            # Stop current process gracefully
            # CRITICAL: Entire process cleanup must be wrapped in try-catch
            # because uvloop can throw ProcessLookupError at ANY point when checking dead processes
            if process_id in self.active_processes:
                current_process = self.active_processes[process_id]
                
                try:
                    # Try to poll the process to update returncode
                    # uvloop may throw ProcessLookupError here if process is a zombie
                    current_process.poll()
                    
                    # Check if process is still alive before trying to terminate
                    if current_process.returncode is None:
                        # Process appears to be running, try graceful termination
                        current_process.terminate()
                        logger.debug(f"Sent SIGTERM to stream {stream.id} process")
                        
                        # Wait a bit for graceful termination
                        await asyncio.sleep(ASYNC_DELAYS.RECORDING_ERROR_RECOVERY)
                        
                        # Poll again to check termination status
                        current_process.poll()
                        
                        # Check again and force kill if still running
                        if current_process.returncode is None:
                            current_process.kill()
                            logger.debug(f"Sent SIGKILL to stream {stream.id} process")
                    else:
                        logger.info(f"Process for stream {stream.id} already terminated (returncode: {current_process.returncode})")
                        
                except ProcessLookupError:
                    # Process is a zombie or was cleaned up externally
                    # This is EXPECTED for long-running streams where streamlink crashes/OOM
                    logger.info(f"🔄 ROTATION: Process for stream {stream.id} already terminated externally, continuing with rotation")
                    
                except Exception as proc_error:
                    # Log but continue - we still want to start the new segment
                    logger.warning(f"🔄 ROTATION: Error stopping old process for stream {stream.id}: {proc_error}, continuing anyway")
                
                finally:
                    # ALWAYS remove the old process from tracking, even if cleanup failed
                    # This prevents stuck process references
                    try:
                        self.active_processes.pop(process_id, None)
                        logger.debug(f"Removed process {process_id} from active_processes tracking")
                    except Exception as e:
                        logger.warning(f"Error removing process {process_id} from tracking: {e}")
                    
            # Prepare next segment
            segment_info['segment_count'] += 1
            base_path = Path(segment_info['base_output_path'])
            segment_filename = f"{base_path.stem}{self.SEGMENT_PART_IDENTIFIER}{segment_info['segment_count']:03d}.ts"
            next_segment_path = Path(segment_info['segment_dir']) / segment_filename
            
            segment_info['current_segment_path'] = str(next_segment_path)
            segment_info['segment_start_time'] = datetime.now()
            
            # Start new segment
            new_process = await self._start_segment(stream, str(next_segment_path), quality, segment_info)
            
            if new_process:
                logger.info(f"Successfully rotated to segment {segment_info['segment_count']} for stream {stream.id}")
            else:
                logger.error(f"Failed to start new segment for stream {stream.id}")
                
        except Exception as e:
            logger.error(f"Error rotating segment for stream {stream.id}: {e}", exc_info=True)

    async def monitor_process(self, process: asyncio.subprocess.Process) -> int:
        """Monitor a recording process until completion with failure detection
        
        Args:
            process: The process to monitor
            
        Returns:
            Exit code of the process (0 if segmented recording completed successfully)
        """
        try:
            # Find if this is a segmented recording
            process_id = None
            segment_info = None
            
            async with self.lock:
                for pid, proc in self.active_processes.items():
                    if proc == process:
                        process_id = pid
                        break
                        
            if process_id and process_id in self.long_stream_processes:
                segment_info = self.long_stream_processes[process_id]
                
            # Wait for the process to complete
            await process.wait()
            
            # Handle segmented vs normal recording completion
            if segment_info:
                # For segmented recordings, the process ending means the stream is over
                # We need to concatenate all segments
                logger.info(f"Segmented recording completed for stream {segment_info['stream_id']}")
                await self._finalize_segmented_recording(segment_info)
                return 0  # Success for segmented recording
            else:
                # Normal single-file recording
                stdout, stderr = await process.communicate()
                
                # CRITICAL: Detect recording failure and update database
                if process.returncode != 0:
                    logger.error(f"🚨 Recording process failed with exit code {process.returncode} (PID: {process.pid})")
                    
                    # Extract error message from stderr
                    error_message = "Unknown error"
                    failure_reason = "streamlink_crash"
                    
                    if stderr:
                        stderr_text = stderr.decode('utf-8', errors='replace')
                        logger.error(f"Process stderr: {stderr_text[:1000]}")
                        
                        # Parse common failure reasons
                        if "ProxyError" in stderr_text or "Tunnel connection failed" in stderr_text:
                            failure_reason = "proxy_error"
                            error_message = "Proxy connection failed (500 Internal Server Error)"
                        elif "Unable to open URL" in stderr_text:
                            failure_reason = "stream_unavailable"
                            error_message = "Stream unavailable or ended"
                        elif "No playable streams found" in stderr_text:
                            failure_reason = "no_streams"
                            error_message = "No playable streams found"
                        else:
                            error_message = f"Streamlink exited with code {process.returncode}"
                    
                    # Update database with error information
                    await self._record_failure_in_database(process_id, error_message, failure_reason)
                    
                    # Broadcast WebSocket error notification
                    await self._notify_recording_failed(process_id, error_message)
                    
                else:
                    logger.info(f"✅ Recording process completed successfully (PID: {process.pid})")
                    
                    # Send Apprise notification for recording_completed (NEW - non-segmented)
                    try:
                        from app.database import SessionLocal
                        from app.models import Stream
                        from app.services.notifications.external_notification_service import ExternalNotificationService
                        from datetime import datetime, timezone
                        import os
                        
                        notification_service = ExternalNotificationService()
                        
                        with SessionLocal() as db:
                            stream_id = process_id.split('_')[1] if '_' in process_id else None
                            if stream_id:
                                stream = (
                                    db.query(Stream)
                                    .options(joinedload(Stream.streamer))
                                    .filter(Stream.id == int(stream_id))
                                    .first()
                                )
                                
                                if stream and stream.streamer and stream.recording_path:
                                    # Calculate recording duration from stream timestamps
                                    duration_seconds = 0
                                    if stream.started_at and stream.ended_at:
                                        duration_seconds = int((stream.ended_at - stream.started_at).total_seconds())
                                    
                                    hours = duration_seconds // 3600
                                    minutes = (duration_seconds % 3600) // 60
                                    
                                    # Get file size
                                    file_size_bytes = 0
                                    if os.path.exists(stream.recording_path):
                                        file_size_bytes = os.path.getsize(stream.recording_path)
                                    file_size_mb = file_size_bytes / (1024 * 1024)
                                    
                                    await notification_service.send_recording_notification(
                                        streamer_name=stream.streamer.username,
                                        event_type='recording_completed',
                                        details={
                                            'hours': hours,
                                            'minutes': minutes,
                                            'file_size_mb': f"{file_size_mb:.2f}",
                                            'quality': stream.quality or 'best'
                                        }
                                    )
                                    
                                    logger.info(f"📧 Apprise notification sent: recording_completed for {stream.streamer.username}")
                                    
                    except Exception as apprise_error:
                        logger.error(f"Failed to send Apprise notification for recording_completed: {apprise_error}")
                
                # Log to structured logging service
                if self.logging_service:
                    # Get streamer name from database for logging
                    try:
                        from app.database import SessionLocal
                        from app.models import Stream, Streamer
                        
                        with SessionLocal() as db:
                            # Get stream from process_id in the segment info with eager loading
                            stream_id = process_id.split('_')[1] if process_id else None
                            if stream_id:
                                stream = (
                                    db.query(Stream)
                                    .options(joinedload(Stream.streamer))
                                    .filter(Stream.id == int(stream_id))
                                    .first()
                                )
                                if stream:
                                    streamer = stream.streamer
                                    if streamer:
                                        # Get the log path for this streamer to append output
                                        log_path = self.logging_service.get_streamlink_log_path(streamer.username)
                                        self.logging_service.log_streamlink_output(
                                            streamer_name=streamer.username,
                                            stdout=stdout,
                                            stderr=stderr,
                                            exit_code=process.returncode or 0,
                                            log_path=log_path
                                        )
                    except Exception as e:
                        logger.warning(f"Could not log streamlink output to structured logging: {e}")
                        
                return process.returncode or 0
            
        except Exception as e:
            logger.error(f"Error monitoring process {process.pid}: {e}", exc_info=True)
            return -1
        finally:
            # Cleanup
            await self._cleanup_process(process)

    async def _finalize_segmented_recording(self, segment_info: Dict):
        """Concatenate all segments into final TS file"""
        try:
            logger.info(f"Finalizing segmented recording for stream {segment_info['stream_id']}")
            
            # Cancel monitoring task
            if segment_info['monitor_task']:
                segment_info['monitor_task'].cancel()
                
            # Get all segment files
            segment_files = []
            for segment in segment_info['total_segments']:
                if await async_file.exists(segment['path']) and await async_file.getsize(segment['path']) > 0:
                    segment_files.append(segment['path'])
                    
            if not segment_files:
                logger.error(f"No valid segment files found for stream {segment_info['stream_id']}")
                return
                
            # Create concatenation list file for FFmpeg
            concat_list_path = Path(segment_info['segment_dir']) / "concat_list.txt"
            with open(concat_list_path, 'w') as f:
                for segment_file in segment_files:
                    f.write(f"file '{segment_file}'\n")
                    
            # Use FFmpeg to concatenate segments
            output_path = segment_info['base_output_path']
            cmd = [
                "ffmpeg",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_list_path),
                "-c", "copy",
                "-y",
                output_path
            ]
            
            logger.info(f"Concatenating {len(segment_files)} segments for stream {segment_info['stream_id']}")
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                logger.info(f"Successfully concatenated segments into {output_path}")
                
                # Send Apprise notification for recording_completed (NEW)
                try:
                    from app.database import SessionLocal
                    from app.models import Stream
                    from app.services.notifications.external_notification_service import ExternalNotificationService
                    from datetime import datetime, timezone
                    import os
                    
                    notification_service = ExternalNotificationService()
                    
                    with SessionLocal() as db:
                        stream = (
                            db.query(Stream)
                            .options(joinedload(Stream.streamer))
                            .filter(Stream.id == segment_info['stream_id'])
                            .first()
                        )
                        
                        if stream and stream.streamer:
                            # Calculate recording duration
                            if segment_info.get('segment_start_time'):
                                duration_seconds = int((datetime.now() - segment_info['segment_start_time']).total_seconds())
                                hours = duration_seconds // 3600
                                minutes = (duration_seconds % 3600) // 60
                            else:
                                hours = 0
                                minutes = 0
                            
                            # Get file size
                            file_size_bytes = os.path.getsize(output_path) if os.path.exists(output_path) else 0
                            file_size_mb = file_size_bytes / (1024 * 1024)
                            
                            await notification_service.send_recording_notification(
                                streamer_name=stream.streamer.username,
                                event_type='recording_completed',
                                details={
                                    'hours': hours,
                                    'minutes': minutes,
                                    'file_size_mb': f"{file_size_mb:.2f}",
                                    'quality': stream.quality or 'best'
                                }
                            )
                            
                            logger.info(f"📧 Apprise notification sent: recording_completed for {stream.streamer.username}")
                            
                except Exception as apprise_error:
                    logger.error(f"Failed to send Apprise notification for recording_completed: {apprise_error}")
                
                # Move concatenated file from segments directory to parent directory
                await self._move_concatenated_file_to_parent(segment_info)
                
                # Trigger post-processing for the moved file
                await self._trigger_post_processing_for_segmented_recording(segment_info)
                
                # Clean up segment files and directory only after post-processing starts
                await self._cleanup_segments(segment_info)
            else:
                logger.error(f"Failed to concatenate segments: {stderr.decode('utf-8', errors='replace')[:500]}")
                
        except Exception as e:
            logger.error(f"Error finalizing segmented recording: {e}", exc_info=True)

    async def _move_concatenated_file_to_parent(self, segment_info: Dict):
        """Move concatenated TS file from segments directory to parent directory"""
        try:
            segment_dir = Path(segment_info['segment_dir'])
            parent_dir = segment_dir.parent
            concatenated_file = Path(segment_info['base_output_path'])
            
            # Create new filename in parent directory
            final_path = parent_dir / concatenated_file.name
            
            # Check if target file already exists and create unique name if needed
            if final_path.exists():
                counter = 1
                base_name = final_path.stem
                extension = final_path.suffix
                while final_path.exists():
                    final_path = parent_dir / f"{base_name}_copy{counter}{extension}"
                    counter += 1
                logger.warning(f"Target file existed, using unique name: {final_path}")
            
            # Move the file
            if concatenated_file.exists():
                shutil.move(str(concatenated_file), str(final_path))
                logger.info(f"Moved concatenated file from {concatenated_file} to {final_path}")
                
                # Update the segment_info with new path for post-processing
                segment_info['final_output_path'] = str(final_path)
            else:
                logger.error(f"Concatenated file not found: {concatenated_file}")
                
        except Exception as e:
            logger.error(f"Error moving concatenated file: {e}", exc_info=True)

    async def _trigger_post_processing_for_segmented_recording(self, segment_info: Dict):
        """Trigger post-processing for the segmented recording using injected callback"""
        try:
            # Use the final output path (moved file) for post-processing
            output_path = segment_info.get('final_output_path', segment_info['base_output_path'])
            stream_id = segment_info['stream_id']
            # Get recording_id from segment_info if available
            recording_id = segment_info.get('recording_id')
            
            if self.post_processing_callback and recording_id:
                # Use the injected callback to trigger post-processing with correct recording_id
                await self.post_processing_callback(recording_id, output_path)
                logger.info(f"Triggered post-processing for segmented recording {recording_id} (stream {stream_id}) via callback")
            else:
                # Fallback to direct service access (with circular import handling)
                logger.warning("No post-processing callback available or recording_id missing, using fallback method")
                await self._fallback_trigger_post_processing(stream_id, output_path, recording_id)
                
        except Exception as e:
            logger.error(f"Error triggering post-processing for segmented recording: {e}", exc_info=True)

    async def _fallback_trigger_post_processing(self, stream_id: int, output_path: str, recording_id: Optional[int] = None):
        """Fallback method for post-processing when no callback is injected"""
        try:
            # Import here to avoid circular imports (only used as fallback)
            from app.routes.recording import get_recording_service
            
            # Get recording service and orchestrator
            recording_service = get_recording_service()
            if recording_service and recording_service.orchestrator:
                # If recording_id is not provided, try to find it by stream_id
                if not recording_id:
                    # Look for active recording for this specific stream with path validation
                    recordings = await recording_service.orchestrator.database_service.get_recordings_by_status("recording")
                    candidate_recording_id: Optional[int] = None
                    
                    # First pass: try to find recording that matches both stream_id and path proximity
                    for recording in recordings:
                        if recording.stream_id == stream_id:
                            # Validate this recording actually belongs to the correct stream by checking the output path
                            try:
                                # Get stream data to verify streamer
                                stream_data = await recording_service.orchestrator.database_service.get_stream_by_id(recording.stream_id)
                                if stream_data:
                                    streamer_data = await recording_service.orchestrator.database_service.get_streamer_by_id(stream_data.streamer_id)
                                    if streamer_data:
                                        # Check if output_path contains the correct streamer name
                                        output_path_obj = Path(output_path)
                                        if streamer_data.username.lower() in str(output_path_obj).lower():
                                            candidate_recording_id = recording.id
                                            logger.info(f"Found matching recording {recording.id} for stream {stream_id} with path validation")
                                            break
                                        else:
                                            logger.warning(f"Recording {recording.id} belongs to stream {stream_id} but path {output_path} doesn't match streamer {streamer_data.username}")
                            except Exception as e:
                                logger.warning(f"Error validating recording {recording.id}: {e}")
                    
                    # If no validated candidate found, fall back to first match (with warning)
                    if not candidate_recording_id:
                        logger.warning(f"No path-validated recording found for stream {stream_id}, falling back to first match")
                        for recording in recordings:
                            if recording.stream_id == stream_id:
                                candidate_recording_id = recording.id
                                break
                    
                    recording_id = candidate_recording_id
                
                if recording_id:
                    # Get recording data using correct recording_id
                    recording_data = recording_service.orchestrator.database_service.get_recording_by_id(recording_id)
                    if recording_data:
                        # Update recording status using correct recording_id
                        await recording_service.orchestrator.database_service.update_recording_status(
                            recording_id=recording_id,  # Use actual recording_id
                            status="completed",
                            path=output_path
                        )
                        
                        # Get additional data needed for post-processing
                        stream_data = await recording_service.orchestrator.database_service.get_stream_by_id(recording_data.stream_id)
                        if stream_data:
                            streamer_data = await recording_service.orchestrator.database_service.get_streamer_by_id(stream_data.streamer_id)
                            if streamer_data:
                                # Create recording data dict for post-processing
                                recording_data_dict = {
                                    'streamer_name': streamer_data.username,
                                    'started_at': recording_data.start_time.isoformat() if recording_data.start_time else None,
                                    'stream_id': stream_data.id,
                                    'recording_id': recording_id  # Use correct recording_id
                                }
                                
                                # Use the public enqueue_post_processing method with correct recording_id
                                await recording_service.orchestrator.enqueue_post_processing(
                                    recording_id=recording_id,  # Use actual recording_id
                                    ts_file_path=output_path,
                                    recording_data=recording_data_dict
                                )
                                logger.info(f"Enqueued post-processing for segmented recording {recording_id} (stream {stream_id})")
                            else:
                                logger.error(f"Streamer data not found for recording {recording_id}")
                        else:
                            logger.error(f"Stream data not found for recording {recording_id}")
                    else:
                        logger.error(f"Recording data not found for recording {recording_id}")
                else:
                    logger.error(f"Could not find recording_id for stream {stream_id}")
            else:
                logger.warning(f"Could not trigger post-processing - recording service not available")
                
        except Exception as e:
            logger.error(f"Error in fallback post-processing trigger: {e}", exc_info=True)

    async def _cleanup_segments(self, segment_info: Dict):
        """Clean up segment files after successful concatenation"""
        try:
            segment_dir = Path(segment_info['segment_dir'])
            
            # Remove segment files
            for segment in segment_info['total_segments']:
                try:
                    if await async_file.exists(segment['path']):
                        await async_file.remove(segment['path'])
                except Exception as e:
                    logger.warning(f"Could not remove segment file {segment['path']}: {e}")
                    
            # Remove concat list file
            concat_list_path = segment_dir / "concat_list.txt"
            if concat_list_path.exists():
                concat_list_path.unlink()
                
            # Remove segment directory if empty
            try:
                segment_dir.rmdir()
                logger.info(f"Cleaned up segment directory: {segment_dir}")
            except OSError:
                logger.debug(f"Segment directory not empty, keeping: {segment_dir}")
                
        except Exception as e:
            logger.error(f"Error cleaning up segments: {e}", exc_info=True)

    async def _cleanup_process(self, process: asyncio.subprocess.Process):
        """Clean up process from tracking"""
        async with self.lock:
            # Remove from active processes
            for process_id, active_process in list(self.active_processes.items()):
                if active_process == process:
                    del self.active_processes[process_id]
                    
                    # Clean up long stream tracking
                    if process_id in self.long_stream_processes:
                        segment_info = self.long_stream_processes[process_id]
                        if segment_info['monitor_task']:
                            segment_info['monitor_task'].cancel()
                        del self.long_stream_processes[process_id]
                    break

    async def terminate_process(self, process_id: str, timeout: int = 10) -> bool:
        """
        Gracefully terminate a process (handles segmented recordings)
        
        Returns:
            bool: True if process was terminated or already terminated, False if termination failed
            
        Note: Process not found is considered SUCCESS because:
        - Process may have already terminated naturally (common with Streamlink)
        - Recording data is intact and should not be marked as failed
        - This prevents false negatives in recording status
        """
        async with self.lock:
            if process_id not in self.active_processes:
                # PRODUCTION FIX: Process not found should be considered success
                # This is NOT a breaking change - it fixes a logic bug where
                # recordings were incorrectly marked as "failed" when the process
                # had already terminated naturally (which is normal behavior)
                logger.info(f"Process {process_id} not found in active processes - assuming already terminated")
                return True  # Process already terminated = success, not failure

            process = self.active_processes.pop(process_id)            # Handle segmented recording cleanup
            if process_id in self.long_stream_processes:
                segment_info = self.long_stream_processes[process_id]
                if segment_info['monitor_task']:
                    segment_info['monitor_task'].cancel()
                    
            try:
                process.terminate()
                await asyncio.wait_for(process.wait(), timeout=timeout)
                logger.info(f"Process {process_id} terminated gracefully")
                
                # Finalize segmented recording if needed
                if process_id in self.long_stream_processes:
                    segment_info = self.long_stream_processes.pop(process_id)
                    await self._finalize_segmented_recording(segment_info)
                    
                return True
            except asyncio.TimeoutError:
                process.kill()
                logger.warning(f"Process {process_id} killed after timeout")
                
                # Still try to finalize if it was segmented
                if process_id in self.long_stream_processes:
                    segment_info = self.long_stream_processes.pop(process_id)
                    await self._finalize_segmented_recording(segment_info)
                    
                return True
            except Exception as e:
                logger.error(f"Failed to terminate process {process_id}: {e}")
                return False

    async def cleanup_all(self):
        """Terminate all active processes"""
        process_ids = list(self.active_processes.keys())
        for process_id in process_ids:
            await self.terminate_process(process_id)
            
    def get_active_process_count(self) -> int:
        """Get the number of active recording processes"""
        return len(self.active_processes)

    async def graceful_shutdown(self, timeout: int = 15):
        """Gracefully shutdown all recording processes
        
        Args:
            timeout: Maximum time to wait for processes to terminate (seconds)
        """
        logger.info("🛑 Starting graceful shutdown of Process Manager...")
        self._is_shutting_down = True
        
        try:
            # Get list of active processes
            active_process_count = len(self.active_processes)
            segmented_process_count = len(self.long_stream_processes)
            
            if active_process_count == 0 and segmented_process_count == 0:
                logger.info("No active processes to shutdown")
                return
            
            logger.info(f"⏳ Terminating {active_process_count} active processes and {segmented_process_count} segmented processes...")
            
            # Terminate all active processes gracefully
            termination_tasks = []
            
            # Handle regular processes
            for stream_id, process in list(self.active_processes.items()):
                termination_tasks.append(self._terminate_process_gracefully(stream_id, process, timeout))
            
            # Handle segmented processes
            for stream_id, segment_info in list(self.long_stream_processes.items()):
                current_process = segment_info.get('current_process')
                if current_process:
                    termination_tasks.append(self._terminate_process_gracefully(stream_id, current_process, timeout))
            
            # Wait for all terminations to complete
            if termination_tasks:
                await asyncio.gather(*termination_tasks, return_exceptions=True)
            
            # Clear process tracking
            self.active_processes.clear()
            self.long_stream_processes.clear()
            
            logger.info("✅ Process Manager graceful shutdown completed")
            
        except Exception as e:
            logger.error(f"❌ Error during Process Manager shutdown: {e}", exc_info=True)

    async def _terminate_process_gracefully(self, stream_id: int, process: asyncio.subprocess.Process, timeout: int):
        """Gracefully terminate a single process"""
        try:
            if process.returncode is None:  # Process is still running
                logger.info(f"🔄 Terminating recording process for stream {stream_id} (PID: {process.pid})")
                
                # Send SIGTERM for graceful termination
                process.terminate()
                
                try:
                    # Wait for process to terminate gracefully
                    await asyncio.wait_for(process.wait(), timeout=timeout)
                    logger.info(f"✅ Process for stream {stream_id} terminated gracefully")
                    
                except asyncio.TimeoutError:
                    # Force kill if timeout
                    logger.warning(f"⚠️ Process for stream {stream_id} didn't terminate gracefully, force killing...")
                    process.kill()
                    await process.wait()
                    logger.info(f"💀 Process for stream {stream_id} force killed")
                    
            else:
                logger.info(f"Process for stream {stream_id} already terminated")
                
        except Exception as e:
            logger.error(f"Error terminating process for stream {stream_id}: {e}")

    def is_shutting_down(self) -> bool:
        """Check if process manager is shutting down"""
        return self._is_shutting_down
    
    async def _record_failure_in_database(self, process_id: str, error_message: str, failure_reason: str):
        """Record recording failure in database for visibility
        
        Args:
            process_id: Process ID (format: stream_{stream_id})
            error_message: Detailed error message
            failure_reason: Short failure category
        """
        try:
            from app.database import SessionLocal
            from app.models import Recording, Stream
            from datetime import datetime, timezone
            
            # Extract stream_id from process_id
            stream_id = process_id.split('_')[1] if '_' in process_id else None
            if not stream_id:
                logger.warning(f"Could not extract stream_id from process_id: {process_id}")
                return
            
            with SessionLocal() as db:
                # Find the active recording for this stream
                recording = (
                    db.query(Recording)
                    .filter(
                        Recording.stream_id == int(stream_id),
                        Recording.status == 'recording'
                    )
                    .first()
                )
                
                if recording:
                    # Update recording with failure information
                    recording.status = 'failed'
                    recording.error_message = error_message
                    recording.failure_reason = failure_reason
                    recording.failure_timestamp = datetime.now(timezone.utc)
                    recording.end_time = datetime.now(timezone.utc)
                    
                    db.commit()
                    logger.info(f"✅ Recorded failure in database for recording {recording.id}: {failure_reason}")
                else:
                    logger.warning(f"No active recording found for stream {stream_id}")
                    
        except Exception as e:
            logger.error(f"Failed to record failure in database: {e}", exc_info=True)
    
    async def _notify_recording_failed(self, process_id: str, error_message: str):
        """Broadcast WebSocket notification for recording failure
        
        Args:
            process_id: Process ID (format: stream_{stream_id})
            error_message: Error message to broadcast
        """
        try:
            from app.database import SessionLocal
            from app.models import Stream, Streamer
            from datetime import datetime, timezone
            
            # Extract stream_id
            stream_id = process_id.split('_')[1] if '_' in process_id else None
            if not stream_id:
                return
            
            with SessionLocal() as db:
                # Get stream and streamer info
                stream = (
                    db.query(Stream)
                    .options(joinedload(Stream.streamer))
                    .filter(Stream.id == int(stream_id))
                    .first()
                )
                
                if stream and stream.streamer:
                    # Broadcast WebSocket event
                    try:
                        from app.services.websocket.websocket_manager import websocket_manager
                        
                        await websocket_manager.broadcast({
                            "type": "recording_failed",
                            "data": {
                                "stream_id": stream.id,
                                "streamer_id": stream.streamer.id,
                                "streamer_name": stream.streamer.username,
                                "error_message": error_message,
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "stream_title": stream.title or "N/A",
                                "category": stream.category_name or "N/A"
                            }
                        })
                        
                        logger.info(f"📡 WebSocket notification sent: recording_failed for {stream.streamer.username}")
                        
                    except Exception as ws_error:
                        logger.error(f"Failed to send WebSocket notification: {ws_error}")
                    
                    # Send Apprise notification (NEW)
                    try:
                        from app.services.notifications.external_notification_service import ExternalNotificationService
                        notification_service = ExternalNotificationService()
                        
                        await notification_service.send_recording_notification(
                            streamer_name=stream.streamer.username,
                            event_type='recording_failed',
                            details={
                                'error_message': error_message,
                                'timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC'),
                                'stream_title': stream.title or 'N/A',
                                'category': stream.category_name or 'N/A'
                            }
                        )
                        
                        logger.info(f"📧 Apprise notification sent: recording_failed for {stream.streamer.username}")
                        
                    except Exception as apprise_error:
                        logger.error(f"Failed to send Apprise notification: {apprise_error}")
                        
        except Exception as e:
            logger.error(f"Error in _notify_recording_failed: {e}", exc_info=True)

    async def get_recording_progress(self, recording_id: int) -> Optional[Dict]:
        """Get progress information for a recording
        
        Args:
            recording_id: ID of the recording to check progress for
            
        Returns:
            Dictionary with progress information or None if not found
        """
        try:
            process_id = f"stream_{recording_id}"
            
            async with self.lock:
                if process_id not in self.active_processes:
                    return None
                    
                process = self.active_processes[process_id]
                
                # Check if process is still running
                if process.returncode is not None:
                    return {"status": "completed", "exit_code": process.returncode}
                
                # Get basic process info
                progress = {
                    "status": "running",
                    "pid": process.pid,
                    "duration": None,
                    "file_size": None,
                    "segment_count": 1
                }
                
                # Add segment info if available
                if process_id in self.long_stream_processes:
                    segment_info = self.long_stream_processes[process_id]
                    progress["segment_count"] = segment_info.get("segment_count", 1)
                    
                    # Calculate duration if we have start time
                    if "segment_start_time" in segment_info:
                        duration = datetime.now() - segment_info["segment_start_time"]
                        progress["duration"] = int(duration.total_seconds())
                    
                    # Get file size if available
                    current_path = segment_info.get("current_segment_path")
                    if current_path and await async_file.exists(current_path):
                        file_size = await async_file.getsize(current_path)
                        progress["file_size"] = file_size
                
                return progress
                
        except Exception as e:
            logger.error(f"Error getting recording progress for {recording_id}: {e}", exc_info=True)
            return None

    def set_post_processing_callback(self, callback: Optional[Callable[[int, str], Awaitable[None]]]):
        """Set the post-processing callback for dependency injection
        
        Args:
            callback: Async function that takes (recording_id: int, file_path: str) parameters
        """
        self.post_processing_callback = callback
        logger.info("Post-processing callback set for ProcessManager")
