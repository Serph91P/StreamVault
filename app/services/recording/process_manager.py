"""
Process management for recording service.

This module handles subprocess creation and management, specifically for streamlink recording processes.
Includes support for 24h+ streams through segment splitting and automatic process rotation.
"""
import logging
import asyncio
import os
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple
from pathlib import Path

# Import utilities
from app.utils.streamlink_utils import get_streamlink_command, get_proxy_settings_from_db
from app.services.recording.exceptions import ProcessError, StreamUnavailableError
from app.models import Stream
from app.utils import async_file

logger = logging.getLogger("streamvault")

class ProcessManager:
    """Manages subprocess execution and cleanup for recording processes"""

    def __init__(self, config_manager=None):
        self.active_processes = {}
        self.long_stream_processes = {}  # Track processes that need segmentation
        self.lock = asyncio.Lock()
        self.config_manager = config_manager
        
        # Configuration for long stream handling (avoid streamlink 24h cutoff)
        self.segment_duration_hours = 23.98  # Split streams at 23h59min to avoid streamlink cutoff
        self.max_file_size_gb = 100  # Start new segment if file exceeds this size
        self.monitor_interval_seconds = 600  # Check every 10 minutes (less frequent)
        
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
        self, stream: Stream, output_path: str, quality: str
    ) -> Optional[asyncio.subprocess.Process]:
        """Start a streamlink recording process for a specific stream
        
        Args:
            stream: Stream object to record
            output_path: Path where the recording should be saved
            quality: Quality setting for the stream
            
        Returns:
            Process object or None if failed
        """
        try:
            # Initialize segmented recording for long streams
            segment_info = await self._initialize_segmented_recording(stream, output_path, quality)
            
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

    async def _initialize_segmented_recording(self, stream: Stream, output_path: str, quality: str) -> Dict:
        """Initialize segmented recording structure for long streams"""
        base_path = Path(output_path)
        segment_dir = base_path.parent / f"{base_path.stem}_segments"
        segment_dir.mkdir(parents=True, exist_ok=True)
        
        # Create first segment path
        segment_filename = f"{base_path.stem}_part001.ts"
        current_segment_path = segment_dir / segment_filename
        
        segment_info = {
            'stream_id': stream.id,
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
            # Get streamer info from database using streamer_id
            from app.database import SessionLocal
            from app.models import Streamer
            
            with SessionLocal() as db:
                streamer = db.query(Streamer).filter(Streamer.id == stream.streamer_id).first()
                if not streamer:
                    raise Exception(f"Streamer {stream.streamer_id} not found")
                
                streamer_name = streamer.username
            
            # Get proxy settings
            proxy_settings = get_proxy_settings_from_db()
            
            logger.info(f"🎬 PROCESS_START_SEGMENT: stream_id={stream.id}, streamer={streamer_name}")
            
            # Generate streamlink command for this segment
            cmd = get_streamlink_command(
                streamer_name=streamer_name,
                quality=quality,
                output_path=segment_path,
                proxy_settings=proxy_settings
            )
            
            logger.info(f"🎬 Starting segment {segment_info['segment_count']} for {streamer_name}")
            logger.debug(f"🎬 Segment path: {segment_path}")
            logger.debug(f"🎬 Streamlink command: {' '.join(cmd)}")
            
            # Start the process
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            process_id = f"stream_{stream.id}"
            async with self.lock:
                self.active_processes[process_id] = process
                
            # Add segment to the list
            segment_info['total_segments'].append({
                'path': segment_path,
                'start_time': datetime.now(),
                'process_pid': process.pid
            })
                
            logger.info(f"Started segment recording for stream {stream.id} with PID {process.pid}")
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
            if process_id in self.active_processes:
                current_process = self.active_processes[process_id]
                current_process.terminate()
                
                # Wait a bit for graceful termination
                await asyncio.sleep(5)
                
                if current_process.returncode is None:
                    current_process.kill()
                    
            # Prepare next segment
            segment_info['segment_count'] += 1
            base_path = Path(segment_info['base_output_path'])
            segment_filename = f"{base_path.stem}_part{segment_info['segment_count']:03d}.ts"
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
        """Monitor a recording process until completion
        
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
                
                if process.returncode == 0:
                    logger.info(f"Recording process completed successfully (PID: {process.pid})")
                else:
                    logger.error(f"Recording process failed with exit code {process.returncode} (PID: {process.pid})")
                    if stderr:
                        logger.error(f"Process stderr: {stderr.decode('utf-8', errors='replace')[:1000]}")
                        
                return process.returncode
            
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
                
                # Clean up segment files and directory
                await self._cleanup_segments(segment_info)
            else:
                logger.error(f"Failed to concatenate segments: {stderr.decode('utf-8', errors='replace')[:500]}")
                
        except Exception as e:
            logger.error(f"Error finalizing segmented recording: {e}", exc_info=True)

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
        """Gracefully terminate a process (handles segmented recordings)"""
        async with self.lock:
            if process_id not in self.active_processes:
                return False

            process = self.active_processes.pop(process_id)
            
            # Handle segmented recording cleanup
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
