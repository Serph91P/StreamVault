"""
Post-Processing Task Handlers

Defines specific handlers for different post-processing tasks
that run in the background queue.
"""
import asyncio
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from app.database import SessionLocal
from app.models import Stream, Recording, StreamMetadata, Streamer
from app.services.metadata_service import MetadataService
from app.services.thumbnail_service import ThumbnailService
from app.services.background_queue_service import QueueTask, TaskStatus, TaskPriority
from app.utils.structured_logging import log_with_context
from app.utils import async_file

logger = logging.getLogger("streamvault")

class PostProcessingTasks:
    """Collection of post-processing task handlers"""
    
    def __init__(self):
        self.metadata_service = MetadataService()
        self.thumbnail_service = ThumbnailService()
        
    async def handle_video_conversion(self, task: QueueTask):
        """Convert .ts file to .mp4 with metadata and chapters"""
        payload = task.payload
        stream_id = payload['stream_id']
        ts_file_path = payload['ts_file_path']
        output_dir = payload['output_dir']
        
        log_with_context(
            logger, 'info',
            f"Starting video conversion for stream {stream_id}",
            stream_id=stream_id,
            task_id=task.id,
            input_file=ts_file_path,
            operation='video_conversion'
        )
        
        try:
            # Update progress
            task.progress = 10.0
            
            # Verify input file exists
            if not os.path.exists(ts_file_path):
                raise FileNotFoundError(f"Input file not found: {ts_file_path}")
                
            # Get stream and streamer info
            with SessionLocal() as db:
                stream = db.query(Stream).filter(Stream.id == stream_id).first()
                if not stream:
                    raise ValueError(f"Stream {stream_id} not found")
                    
                streamer = db.query(Streamer).filter(Streamer.id == stream.streamer_id).first()
                if not streamer:
                    raise ValueError(f"Streamer {stream.streamer_id} not found")
            
            # Update progress
            task.progress = 20.0
            
            # Generate output filename
            base_filename = Path(ts_file_path).stem
            mp4_output_path = Path(output_dir) / f"{base_filename}.mp4"
            
            # Step 1: Convert TS to MP4 using FFmpeg
            await self._convert_ts_to_mp4(ts_file_path, str(mp4_output_path), task)
            
            # Update progress
            task.progress = 60.0
            
            # Step 2: Generate metadata files
            await self.metadata_service.generate_metadata_for_stream(
                stream_id=stream_id,
                base_path=str(output_dir),
                base_filename=base_filename
            )
            
            # Update progress
            task.progress = 80.0
            
            # Step 3: Generate/ensure thumbnail
            await self.thumbnail_service.ensure_thumbnail_with_fallback(
                stream_id=stream_id,
                output_dir=str(output_dir),
                video_path=str(mp4_output_path)
            )
            
            # Update progress
            task.progress = 90.0
            
            # Step 4: Update database
            with SessionLocal() as db:
                # Update stream with final MP4 path
                stream = db.query(Stream).filter(Stream.id == stream_id).first()
                if stream:
                    stream.recording_path = str(mp4_output_path)
                    
                # Update recording status
                recording = db.query(Recording).filter(Recording.stream_id == stream_id).first()
                if recording:
                    recording.status = "completed"
                    recording.path = str(mp4_output_path)
                    recording.end_time = datetime.now(timezone.utc)
                    
                    # Calculate file size
                    if os.path.exists(mp4_output_path):
                        recording.file_size = os.path.getsize(mp4_output_path)
                        
                db.commit()
                
            # Update progress
            task.progress = 95.0
            
            # Step 5: Cleanup TS file (optional)
            cleanup_ts = payload.get('cleanup_ts_file', True)
            if cleanup_ts and os.path.exists(ts_file_path):
                try:
                    os.remove(ts_file_path)
                    logger.info(f"Cleaned up TS file: {ts_file_path}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup TS file: {e}")
                    
            # Final progress
            task.progress = 100.0
            
            log_with_context(
                logger, 'info',
                f"Video conversion completed successfully",
                stream_id=stream_id,
                task_id=task.id,
                output_file=str(mp4_output_path),
                operation='video_conversion_complete'
            )
            
        except Exception as e:
            log_with_context(
                logger, 'error',
                f"Video conversion failed: {e}",
                stream_id=stream_id,
                task_id=task.id,
                operation='video_conversion_error'
            )
            raise
            
    async def handle_metadata_generation(self, task: QueueTask):
        """Generate metadata files for a stream"""
        payload = task.payload
        stream_id = payload['stream_id']
        base_path = payload['base_path']
        base_filename = payload['base_filename']
        
        log_with_context(
            logger, 'info',
            f"Starting metadata generation for stream {stream_id}",
            stream_id=stream_id,
            task_id=task.id,
            operation='metadata_generation'
        )
        
        try:
            task.progress = 10.0
            
            # Generate all metadata files
            success = await self.metadata_service.generate_metadata_for_stream(
                stream_id=stream_id,
                base_path=base_path,
                base_filename=base_filename
            )
            
            if not success:
                raise Exception("Metadata generation failed")
                
            task.progress = 100.0
            
            log_with_context(
                logger, 'info',
                f"Metadata generation completed successfully",
                stream_id=stream_id,
                task_id=task.id,
                operation='metadata_generation_complete'
            )
            
        except Exception as e:
            log_with_context(
                logger, 'error',
                f"Metadata generation failed: {e}",
                stream_id=stream_id,
                task_id=task.id,
                operation='metadata_generation_error'
            )
            raise
            
    async def handle_thumbnail_generation(self, task: QueueTask):
        """Generate thumbnail for a stream"""
        payload = task.payload
        stream_id = payload['stream_id']
        video_path = payload.get('video_path')
        output_dir = payload['output_dir']
        
        log_with_context(
            logger, 'info',
            f"Starting thumbnail generation for stream {stream_id}",
            stream_id=stream_id,
            task_id=task.id,
            operation='thumbnail_generation'
        )
        
        try:
            task.progress = 10.0
            
            # Generate thumbnail
            if video_path:
                # Extract from video file
                thumbnail_path = await self.thumbnail_service.generate_thumbnail_from_mp4(
                    stream_id=stream_id,
                    mp4_path=video_path
                )
            else:
                # Try to get from Twitch or existing sources
                thumbnail_path = await self.thumbnail_service.ensure_thumbnail_with_fallback(
                    stream_id=stream_id,
                    output_dir=output_dir
                )
                
            task.progress = 100.0
            
            if thumbnail_path:
                log_with_context(
                    logger, 'info',
                    f"Thumbnail generation completed successfully",
                    stream_id=stream_id,
                    task_id=task.id,
                    thumbnail_path=thumbnail_path,
                    operation='thumbnail_generation_complete'
                )
            else:
                raise Exception("Thumbnail generation failed")
                
        except Exception as e:
            log_with_context(
                logger, 'error',
                f"Thumbnail generation failed: {e}",
                stream_id=stream_id,
                task_id=task.id,
                operation='thumbnail_generation_error'
            )
            raise
            
    async def handle_file_cleanup(self, task: QueueTask):
        """Clean up temporary files"""
        payload = task.payload
        files_to_delete = payload.get('files_to_delete', [])
        directories_to_delete = payload.get('directories_to_delete', [])
        
        log_with_context(
            logger, 'info',
            f"Starting file cleanup task",
            task_id=task.id,
            files_count=len(files_to_delete),
            dirs_count=len(directories_to_delete),
            operation='file_cleanup'
        )
        
        try:
            total_items = len(files_to_delete) + len(directories_to_delete)
            processed = 0
            
            # Delete files
            for file_path in files_to_delete:
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        logger.debug(f"Deleted file: {file_path}")
                    processed += 1
                    task.progress = (processed / total_items) * 100
                except Exception as e:
                    logger.warning(f"Failed to delete file {file_path}: {e}")
                    
            # Delete directories
            for dir_path in directories_to_delete:
                try:
                    if os.path.exists(dir_path) and os.path.isdir(dir_path):
                        import shutil
                        shutil.rmtree(dir_path)
                        logger.debug(f"Deleted directory: {dir_path}")
                    processed += 1
                    task.progress = (processed / total_items) * 100
                except Exception as e:
                    logger.warning(f"Failed to delete directory {dir_path}: {e}")
                    
            task.progress = 100.0
            
            log_with_context(
                logger, 'info',
                f"File cleanup completed",
                task_id=task.id,
                operation='file_cleanup_complete'
            )
            
        except Exception as e:
            log_with_context(
                logger, 'error',
                f"File cleanup failed: {e}",
                task_id=task.id,
                operation='file_cleanup_error'
            )
            raise
            
    async def _convert_ts_to_mp4(self, ts_file_path: str, mp4_output_path: str, task: QueueTask):
        """Convert TS file to MP4 using FFmpeg"""
        
        # Get streamer name from task
        streamer_name = task.streamer_name if hasattr(task, 'streamer_name') else "unknown"
        
        # FFmpeg command for conversion
        cmd = [
            "ffmpeg",
            "-i", ts_file_path,
            "-c", "copy",  # Copy streams without re-encoding
            "-bsf:a", "aac_adtstoasc",  # Fix AAC stream
            "-movflags", "+faststart",  # Optimize for streaming
            "-y",  # Overwrite output file
            mp4_output_path
        ]
        
        # Use the logging service to create per-streamer logs
        if self.logging_service:
            streamer_log_path = self.logging_service.log_ffmpeg_start("ts_to_mp4_task", cmd, streamer_name)
            logger.info(f"FFmpeg logs will be written to: {streamer_log_path}")
        
        # Create process
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Monitor progress (simplified)
        stdout, stderr = await process.communicate()
        
        # Log the FFmpeg output using the logging service
        if self.logging_service:
            self.logging_service.log_ffmpeg_output("ts_to_mp4_task", stdout, stderr, process.returncode, streamer_name)
        
        if process.returncode != 0:
            error_msg = stderr.decode('utf-8', errors='ignore')
            raise Exception(f"FFmpeg conversion failed: {error_msg}")
            
        # Update progress during conversion
        task.progress = 50.0
        
        # Verify output file was created
        if not os.path.exists(mp4_output_path):
            raise Exception(f"Output file was not created: {mp4_output_path}")
            
        # Check if file has reasonable size
        if os.path.getsize(mp4_output_path) < 1024:  # Less than 1KB
            raise Exception(f"Output file is too small: {mp4_output_path}")

# Global instance
post_processing_tasks = PostProcessingTasks()
