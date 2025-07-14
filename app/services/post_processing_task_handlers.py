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
from app.services.metadata_service import MetadataService
from app.services.thumbnail_service import ThumbnailService
from app.utils import ffmpeg_utils
from app.utils.structured_logging import log_with_context

logger = logging.getLogger("streamvault")

class PostProcessingTaskHandlers:
    """Collection of task handlers for post-processing operations"""
    
    def __init__(self):
        self.metadata_service = MetadataService()
        self.thumbnail_service = ThumbnailService()
    
    async def handle_metadata_generation(self, task):
        """Handle metadata generation task"""
        payload = task.payload
        stream_id = payload['stream_id']
        base_filename = payload['base_filename']
        output_dir = payload['output_dir']
        
        log_with_context(
            logger, 'info',
            f"Starting metadata generation for stream {stream_id}",
            task_id=task.id,
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
                task_id=task.id,
                stream_id=stream_id,
                operation='metadata_generation_complete'
            )
            
        except Exception as e:
            log_with_context(
                logger, 'error',
                f"Metadata generation failed for stream {stream_id}: {e}",
                task_id=task.id,
                stream_id=stream_id,
                error=str(e),
                operation='metadata_generation_error'
            )
            raise
    
    async def handle_chapters_generation(self, task):
        """Handle chapters generation task"""
        payload = task.payload
        stream_id = payload['stream_id']
        mp4_path = payload['mp4_path']
        
        log_with_context(
            logger, 'info',
            f"Starting chapters generation for stream {stream_id}",
            task_id=task.id,
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
                task_id=task.id,
                stream_id=stream_id,
                chapter_formats=list(chapter_info.keys()),
                operation='chapters_generation_complete'
            )
            
        except Exception as e:
            log_with_context(
                logger, 'error',
                f"Chapters generation failed for stream {stream_id}: {e}",
                task_id=task.id,
                stream_id=stream_id,
                error=str(e),
                operation='chapters_generation_error'
            )
            raise
    
    async def handle_mp4_remux(self, task):
        """Handle MP4 remux task"""
        payload = task.payload
        stream_id = payload['stream_id']
        ts_file_path = payload['ts_file_path']
        mp4_output_path = payload['mp4_output_path']
        streamer_name = payload['streamer_name']
        
        log_with_context(
            logger, 'info',
            f"Starting MP4 remux for stream {stream_id}",
            task_id=task.id,
            stream_id=stream_id,
            ts_file_path=ts_file_path,
            mp4_output_path=mp4_output_path,
            operation='mp4_remux_start'
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
                if metadata and metadata.chapters_vtt_path:
                    # You could parse VTT chapters here if needed
                    pass
            
            # Convert TS to MP4 with metadata
            result = await ffmpeg_utils.embed_metadata_with_ffmpeg_wrapper(
                input_path=ts_file_path,
                output_path=mp4_output_path,
                metadata=metadata_dict,
                chapters=chapters,
                streamer_name=streamer_name
            )
            
            if not result.get('success'):
                raise Exception(f"MP4 remux failed: {result.get('stderr', 'Unknown error')}")
                
            # Validate MP4 file
            if not await ffmpeg_utils.validate_mp4(mp4_output_path):
                raise Exception("MP4 validation failed")
                
            log_with_context(
                logger, 'info',
                f"MP4 remux completed for stream {stream_id}",
                task_id=task.id,
                stream_id=stream_id,
                mp4_output_path=mp4_output_path,
                operation='mp4_remux_complete'
            )
            
        except Exception as e:
            log_with_context(
                logger, 'error',
                f"MP4 remux failed for stream {stream_id}: {e}",
                task_id=task.id,
                stream_id=stream_id,
                error=str(e),
                operation='mp4_remux_error'
            )
            raise
    
    async def handle_thumbnail_generation(self, task):
        """Handle thumbnail generation task"""
        payload = task.payload
        stream_id = payload['stream_id']
        mp4_path = payload['mp4_path']
        output_dir = payload['output_dir']
        
        log_with_context(
            logger, 'info',
            f"Starting thumbnail generation for stream {stream_id}",
            task_id=task.id,
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
                task_id=task.id,
                stream_id=stream_id,
                thumbnail_path=thumbnail_path,
                operation='thumbnail_generation_complete'
            )
            
        except Exception as e:
            log_with_context(
                logger, 'error',
                f"Thumbnail generation failed for stream {stream_id}: {e}",
                task_id=task.id,
                stream_id=stream_id,
                error=str(e),
                operation='thumbnail_generation_error'
            )
            raise
    
    async def handle_cleanup(self, task):
        """Handle cleanup task"""
        payload = task.payload
        stream_id = payload['stream_id']
        files_to_remove = payload['files_to_remove']
        mp4_path = payload['mp4_path']
        
        log_with_context(
            logger, 'info',
            f"Starting cleanup for stream {stream_id}",
            task_id=task.id,
            stream_id=stream_id,
            files_to_remove=files_to_remove,
            operation='cleanup_start'
        )
        
        try:
            # Only remove files if MP4 exists and is valid
            if mp4_path and os.path.exists(mp4_path):
                mp4_size = os.path.getsize(mp4_path)
                if mp4_size > 1024:  # MP4 must be at least 1KB
                    removed_files = []
                    for file_path in files_to_remove:
                        if os.path.exists(file_path):
                            try:
                                os.remove(file_path)
                                removed_files.append(file_path)
                                logger.info(f"Removed file: {file_path}")
                            except Exception as e:
                                logger.warning(f"Failed to remove file {file_path}: {e}")
                    
                    log_with_context(
                        logger, 'info',
                        f"Cleanup completed for stream {stream_id}",
                        task_id=task.id,
                        stream_id=stream_id,
                        removed_files=removed_files,
                        operation='cleanup_complete'
                    )
                else:
                    raise Exception(f"MP4 file too small ({mp4_size} bytes), not removing source files")
            else:
                raise Exception("MP4 file not found, not removing source files")
                
        except Exception as e:
            log_with_context(
                logger, 'error',
                f"Cleanup failed for stream {stream_id}: {e}",
                task_id=task.id,
                stream_id=stream_id,
                error=str(e),
                operation='cleanup_error'
            )
            raise
    
    async def cleanup(self):
        """Clean up services"""
        await self.metadata_service.close()
        await self.thumbnail_service.close()

# Global instance
post_processing_task_handlers = PostProcessingTaskHandlers()
