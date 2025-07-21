"""
Task handlers for post-processing tasks
Implements the actual task execution logic for different post-processing operations
"""
import asyncio
import logging
import os
from pathlib import Path
from typing import Dict, Any

from app.database import SessionLocal
from app.models import Stream, Recording, StreamMetadata
from app.services.media.metadata_service import MetadataService
from app.services.media.thumbnail_service import ThumbnailService
from app.utils import ffmpeg_utils
from app.utils.structured_logging import log_with_context

logger = logging.getLogger("streamvault")

class PostProcessingTaskHandlers:
    """Collection of task handlers for post-processing operations"""
    
    def __init__(self):
        self.metadata_service = MetadataService()
        self.thumbnail_service = ThumbnailService()
        
        # Initialize logging service
        try:
            from app.services.system.logging_service import logging_service
            self.logging_service = logging_service
        except Exception as e:
            logger.warning(f"Could not initialize logging service: {e}")
            self.logging_service = None
    
    async def handle_metadata_generation(self, payload, progress_callback=None):
        """Handle metadata generation task"""
        stream_id = payload['stream_id']
        base_filename = payload['base_filename']
        output_dir = payload['output_dir']
        
        log_with_context(
            logger, 'info',
            f"Starting metadata generation for stream {stream_id}",
            task_id=payload.get('task_id'),
            stream_id=stream_id,
            operation='metadata_generation_start'
        )
        
        try:
            # Generate metadata using metadata service
            success = await self.metadata_service.generate_metadata_for_stream(
                stream_id=stream_id,
                base_path=output_dir,
                base_filename=base_filename
            )
            
            if not success:
                raise Exception("Metadata generation failed")
                
            log_with_context(
                logger, 'info',
                f"Metadata generation completed for stream {stream_id}",
                task_id=payload.get('task_id'),
                stream_id=stream_id,
                operation='metadata_generation_complete'
            )
            
        except Exception as e:
            log_with_context(
                logger, 'error',
                f"Metadata generation failed for stream {stream_id}: {e}",
                task_id=payload.get('task_id'),
                stream_id=stream_id,
                error=str(e),
                operation='metadata_generation_error'
            )
            raise
    
    async def handle_chapters_generation(self, payload, progress_callback=None):
        """Handle chapters generation task"""
        stream_id = payload['stream_id']
        mp4_path = payload['mp4_path']
        
        log_with_context(
            logger, 'info',
            f"Starting chapters generation for stream {stream_id}",
            task_id=payload.get('task_id'),
            stream_id=stream_id,
            operation='chapters_generation_start'
        )
        
        try:
            # Generate chapters using metadata service
            chapter_info = await self.metadata_service.ensure_all_chapter_formats(
                stream_id=stream_id,
                mp4_path=mp4_path
            )
            
            if not chapter_info:
                raise Exception("Chapters generation failed")
                
            log_with_context(
                logger, 'info',
                f"Chapters generation completed for stream {stream_id}",
                task_id=payload.get('task_id'),
                stream_id=stream_id,
                chapter_formats=list(chapter_info.keys()),
                operation='chapters_generation_complete'
            )
            
        except Exception as e:
            log_with_context(
                logger, 'error',
                f"Chapters generation failed for stream {stream_id}: {e}",
                task_id=payload.get('task_id'),
                stream_id=stream_id,
                error=str(e),
                operation='chapters_generation_error'
            )
            raise
    
    async def handle_mp4_remux(self, payload, progress_callback=None):
        """Handle MP4 remux task"""
        stream_id = payload['stream_id']
        ts_file_path = payload['ts_file_path']
        mp4_output_path = payload['mp4_output_path']
        streamer_name = payload['streamer_name']
        
        log_with_context(
            logger, 'info',
            f"Starting MP4 remux for stream {stream_id}",
            task_id=payload.get('task_id'),
            stream_id=stream_id,
            ts_file_path=ts_file_path,
            mp4_output_path=mp4_output_path,
            operation='mp4_remux_start',
            streamer_name=streamer_name
        )
        
        # Log to structured logging service
        if self.logging_service:
            self.logging_service.log_recording_activity(
                "MP4_REMUX_START",
                streamer_name,
                f"Remuxing {ts_file_path} to {mp4_output_path}"
            )
        
        try:
            # Check if TS file exists
            if not os.path.exists(ts_file_path):
                raise Exception(f"TS file not found: {ts_file_path}")
                
            # Get stream metadata for embedding
            with SessionLocal() as db:
                stream = db.query(Stream).filter(Stream.id == stream_id).first()
                if not stream:
                    raise Exception(f"Stream {stream_id} not found")
                
                # Get metadata for embedding
                metadata = db.query(StreamMetadata).filter(StreamMetadata.stream_id == stream_id).first()
                
                # Build metadata dict for embedding
                metadata_dict = {
                    'title': stream.title or f"{streamer_name} Stream",
                    'artist': streamer_name,
                    'date': stream.started_at.strftime('%Y-%m-%d') if stream.started_at else None,
                    'creation_time': stream.started_at.isoformat() if stream.started_at else None,
                    'comment': f"Stream by {streamer_name}",
                    'genre': stream.category_name or 'Livestream'
                }
                
                # Get chapters if available
                chapters = None
                if metadata and metadata.chapters_ffmpeg_path:
                    # Load chapters from FFmpeg format file
                    try:
                        chapters_list = []
                        if os.path.exists(metadata.chapters_ffmpeg_path):
                            with open(metadata.chapters_ffmpeg_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                                # Parse FFmpeg chapters format
                                import re
                                chapter_blocks = re.split(r'\n\[CHAPTER\]\n', content)
                                for block in chapter_blocks[1:]:  # Skip metadata part
                                    lines = block.strip().split('\n')
                                    chapter_data = {}
                                    for line in lines:
                                        if '=' in line:
                                            key, value = line.split('=', 1)
                                            chapter_data[key] = value
                                    
                                    if 'START' in chapter_data and 'END' in chapter_data and 'title' in chapter_data:
                                        chapters_list.append({
                                            'start_time': int(chapter_data['START']) / 1000.0,  # Convert ms to seconds
                                            'end_time': int(chapter_data['END']) / 1000.0,
                                            'title': chapter_data['title']
                                        })
                            
                            if chapters_list:
                                chapters = chapters_list
                                logger.info(f"Loaded {len(chapters_list)} chapters for embedding")
                    except Exception as e:
                        logger.warning(f"Failed to load chapters from {metadata.chapters_ffmpeg_path}: {e}")
                        chapters = None
            
            # Convert TS to MP4 with metadata
            result = await ffmpeg_utils.embed_metadata_with_ffmpeg_wrapper(
                input_path=ts_file_path,
                output_path=mp4_output_path,
                metadata=metadata_dict,
                chapters=chapters,
                streamer_name=streamer_name,
                logging_service=self.logging_service
            )
            
            if not result.get('success'):
                raise Exception(f"MP4 remux failed: {result.get('stderr', 'Unknown error')}")
                
            # Validate MP4 file
            if not await ffmpeg_utils.validate_mp4(mp4_output_path):
                raise Exception("MP4 validation failed")
                
            log_with_context(
                logger, 'info',
                f"MP4 remux completed for stream {stream_id}",
                task_id=payload.get('task_id'),
                stream_id=stream_id,
                mp4_output_path=mp4_output_path,
                operation='mp4_remux_complete'
            )
            
        except Exception as e:
            log_with_context(
                logger, 'error',
                f"MP4 remux failed for stream {stream_id}: {e}",
                task_id=payload.get('task_id'),
                stream_id=stream_id,
                error=str(e),
                operation='mp4_remux_error'
            )
            raise
    
    async def handle_thumbnail_generation(self, payload, progress_callback=None):
        """Handle thumbnail generation task"""
        stream_id = payload['stream_id']
        mp4_path = payload['mp4_path']
        output_dir = payload['output_dir']
        
        log_with_context(
            logger, 'info',
            f"Starting thumbnail generation for stream {stream_id}",
            task_id=payload.get('task_id'),
            stream_id=stream_id,
            mp4_path=mp4_path,
            operation='thumbnail_generation_start'
        )
        
        try:
            # Generate thumbnail from MP4
            thumbnail_path = await self.thumbnail_service.generate_thumbnail_from_mp4(
                stream_id=stream_id,
                mp4_path=mp4_path
            )
            
            if not thumbnail_path:
                raise Exception("Thumbnail generation failed")
                
            log_with_context(
                logger, 'info',
                f"Thumbnail generation completed for stream {stream_id}",
                task_id=payload.get('task_id'),
                stream_id=stream_id,
                thumbnail_path=thumbnail_path,
                operation='thumbnail_generation_complete'
            )
            
        except Exception as e:
            log_with_context(
                logger, 'error',
                f"Thumbnail generation failed for stream {stream_id}: {e}",
                task_id=payload.get('task_id'),
                stream_id=stream_id,
                error=str(e),
                operation='thumbnail_generation_error'
            )
            raise
    
    async def handle_mp4_validation(self, payload, progress_callback=None):
        """Handle MP4 validation task"""
        stream_id = payload['stream_id']
        mp4_path = payload['mp4_path']
        ts_file_path = payload['ts_file_path']
        validate_size_ratio = payload.get('validate_size_ratio', True)
        min_size_mb = payload.get('min_size_mb', 1)
        
        log_with_context(
            logger, 'info',
            f"Starting MP4 validation for stream {stream_id}",
            task_id=payload.get('task_id'),
            stream_id=stream_id,
            mp4_path=mp4_path,
            operation='mp4_validation_start'
        )
        
        try:
            # Check if MP4 exists
            if not os.path.exists(mp4_path):
                raise Exception(f"MP4 file not found: {mp4_path}")
            
            # Check MP4 size
            mp4_size = os.path.getsize(mp4_path)
            min_size_bytes = min_size_mb * 1024 * 1024
            
            if mp4_size < min_size_bytes:
                raise Exception(f"MP4 file too small: {mp4_size} bytes (minimum: {min_size_bytes} bytes)")
            
            # Validate size ratio if requested
            if validate_size_ratio and os.path.exists(ts_file_path):
                ts_size = os.path.getsize(ts_file_path)
                if ts_size > 0:
                    size_ratio = mp4_size / ts_size
                    
                    # MP4 should be between 70% and 110% of TS size
                    if size_ratio < 0.7:
                        raise Exception(f"MP4 file too small compared to TS - Ratio: {size_ratio:.2f}")
                    elif size_ratio > 1.1:
                        logger.warning(f"MP4 file larger than TS - Ratio: {size_ratio:.2f} (this is usually okay)")
            
            # Use FFmpeg utils validation
            is_valid = await ffmpeg_utils.validate_mp4(mp4_path)
            if not is_valid:
                raise Exception("MP4 validation failed - file may be corrupted")
            
            log_with_context(
                logger, 'info',
                f"MP4 validation completed for stream {stream_id}",
                task_id=payload.get('task_id'),
                stream_id=stream_id,
                mp4_size=mp4_size,
                operation='mp4_validation_complete'
            )
            
        except Exception as e:
            log_with_context(
                logger, 'error',
                f"MP4 validation failed for stream {stream_id}: {e}",
                task_id=payload.get('task_id'),
                stream_id=stream_id,
                error=str(e),
                operation='mp4_validation_error'
            )
            raise

    async def handle_cleanup(self, payload, progress_callback=None):
        """Handle cleanup task with intelligent TS cleanup"""
        stream_id = payload['stream_id']
        files_to_remove = payload.get('files_to_remove', [])  # Default to empty list if not provided
        mp4_path = payload['mp4_path']
        intelligent_cleanup = payload.get('intelligent_cleanup', False)
        max_wait_time = payload.get('max_wait_time', 300)  # 5 minutes default
        streamer_name = payload.get('streamer_name', f'stream_{stream_id}')
        
        # Validate that files_to_remove is a list
        if not isinstance(files_to_remove, list):
            logger.warning(f"files_to_remove is not a list: {type(files_to_remove)}, converting to list")
            files_to_remove = [files_to_remove] if files_to_remove else []
        
        log_with_context(
            logger, 'info',
            f"Starting cleanup for stream {stream_id}",
            task_id=payload.get('task_id'),
            stream_id=stream_id,
            files_to_remove=files_to_remove,
            intelligent_cleanup=intelligent_cleanup,
            operation='cleanup_start',
            streamer_name=streamer_name
        )
        
        # Log to structured logging service
        if self.logging_service:
            self.logging_service.log_recording_activity(
                "CLEANUP_START",
                streamer_name,
                f"Cleaning up {len(files_to_remove)} files for stream {stream_id}"
            )
        
        try:
            # Validation should have already passed, but double-check
            if not mp4_path or not os.path.exists(mp4_path):
                raise Exception("MP4 file not found, not removing source files")
            
            mp4_size = os.path.getsize(mp4_path)
            if mp4_size < 1024 * 1024:  # Less than 1MB
                raise Exception(f"MP4 file too small ({mp4_size} bytes), not removing source files")
            
            removed_files = []
            for file_path in files_to_remove:
                if os.path.exists(file_path):
                    try:
                        # Check if it's a directory
                        if os.path.isdir(file_path):
                            # Remove directory and all its contents
                            import shutil
                            shutil.rmtree(file_path)
                            logger.info(f"Removed directory: {file_path}")
                            removed_files.append(file_path)
                        else:
                            # Use intelligent cleanup for TS files if requested
                            if intelligent_cleanup and file_path.endswith('.ts'):
                                cleanup_success = await self._intelligent_ts_cleanup(file_path, mp4_path, max_wait_time)
                                if cleanup_success:
                                    removed_files.append(file_path)
                                else:
                                    logger.warning(f"Intelligent cleanup failed for {file_path}, keeping file")
                            else:
                                # Simple file removal
                                os.remove(file_path)
                                logger.info(f"Removed file: {file_path}")
                                removed_files.append(file_path)
                    except Exception as e:
                        logger.warning(f"Failed to remove {file_path}: {e}")
            
            log_with_context(
                logger, 'info',
                f"Cleanup completed for stream {stream_id}",
                task_id=payload.get('task_id'),
                stream_id=stream_id,
                removed_files=removed_files,
                operation='cleanup_complete'
            )
                
        except Exception as e:
            log_with_context(
                logger, 'error',
                f"Cleanup failed for stream {stream_id}: {e}",
                task_id=payload.get('task_id'),
                stream_id=stream_id,
                error=str(e),
                operation='cleanup_error'
            )
            raise
    
    async def _intelligent_ts_cleanup(self, ts_path: str, mp4_path: str, max_wait_time: int):
        """Intelligent TS cleanup that waits for processes to finish"""
        try:
            # Use the intelligent cleanup from file_operations
            from app.services.recording.file_operations import intelligent_ts_cleanup
            
            # Check if psutil is available for process monitoring
            psutil_available = False
            try:
                import psutil
                psutil_available = True
            except ImportError:
                pass
            
            # Run intelligent cleanup
            await intelligent_ts_cleanup(ts_path, max_wait_time, psutil_available)
            
        except Exception as e:
            # Fallback to simple removal if intelligent cleanup fails
            logger.warning(f"Intelligent cleanup failed, falling back to simple removal: {e}")
            if os.path.exists(ts_path):
                os.remove(ts_path)
    
    async def cleanup(self):
        """Clean up services"""
        await self.metadata_service.close()
        await self.thumbnail_service.close()

# Global instance
post_processing_task_handlers = PostProcessingTaskHandlers()
