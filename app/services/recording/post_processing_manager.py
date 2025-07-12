"""
Post-processing manager for recording service.

This module handles all post-recording operations using existing file_utils and path_utils:
- TS to MP4 conversion with metadata and chapters
- File organization using existing templates
- Cleanup operations
"""
import logging
import asyncio
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any, List

# Import existing utilities and new pipeline manager
from app.utils.file_utils import remux_file, create_ffmpeg_chapters_file, sanitize_filename
from app.utils.path_utils import generate_filename, update_recording_path
from app.services.metadata_service import MetadataService
from app.services.thumbnail_service import ThumbnailService
from app.services.recording.pipeline_manager import PipelineManager
from app.services.recording.exceptions import FileOperationError

logger = logging.getLogger("streamvault")

class PostProcessingManager:
    """Manages post-recording processing operations using existing file and path utilities"""

    def __init__(self, config_manager=None):
        self.config_manager = config_manager
        self.pipeline_manager = PipelineManager(config_manager=config_manager)
        
        # Keep legacy services for backwards compatibility
        self.metadata_service = MetadataService()
        self.thumbnail_service = ThumbnailService()

    async def process_completed_recording(
        self, 
        stream_id: int, 
        ts_path: str
    ) -> Dict[str, Any]:
        """Complete post-processing workflow for a recording using sequential pipeline
        
        Args:
            stream_id: ID of the stream
            ts_path: Path to the TS file
            
        Returns:
            Dictionary with processing results
        """
        try:
            logger.info(f"Starting sequential post-processing pipeline for stream {stream_id}: {ts_path}")
            
            # Use the new pipeline manager for sequential processing
            pipeline_results = await self.pipeline_manager.start_post_processing_pipeline(
                stream_id=stream_id,
                ts_path=ts_path
            )
            
            # Convert pipeline results to expected format for backwards compatibility
            results = {
                'success': pipeline_results['success'],
                'ts_path': ts_path,
                'mp4_path': pipeline_results.get('mp4_path'),
                'completed_steps': pipeline_results.get('completed_steps', []),
                'errors': pipeline_results.get('errors', []),
                'duration_seconds': pipeline_results.get('duration_seconds', 0),
                
                # Legacy format fields for backwards compatibility
                'metadata_generated': 'metadata_generation' in pipeline_results.get('completed_steps', []),
                'chapters_generated': 'metadata_generation' in pipeline_results.get('completed_steps', []),
                'conversion_completed': 'ts_to_mp4_conversion' in pipeline_results.get('completed_steps', []),
                'files_cleaned': 'ts_cleanup' in pipeline_results.get('completed_steps', []),
                'thumbnail_generated': 'thumbnail_extraction' in pipeline_results.get('completed_steps', [])
            }
            
            if results['success']:
                logger.info(f"Sequential pipeline completed successfully for stream {stream_id} in {results['duration_seconds']:.2f}s")
            else:
                logger.error(f"Sequential pipeline failed for stream {stream_id}. Errors: {results['errors']}")
                
            return results
            
        except Exception as e:
            logger.error(f"Error in post-processing pipeline for stream {stream_id}: {e}", exc_info=True)
            raise FileOperationError(f"Post-processing pipeline failed: {e}")
        finally:
            # Clean up legacy service sessions (pipeline manager handles its own cleanup)
            await self.metadata_service.close()
            await self.thumbnail_service.close()

    async def _generate_output_path(self, stream_id: int, ts_path: str) -> Optional[str]:
        """Generate the final MP4 output path using existing path_utils
        
        Args:
            stream_id: ID of the stream
            ts_path: Path to the TS file
            
        Returns:
            Path to the MP4 file or None if generation failed
        """
        try:
            from app.database import SessionLocal
            from app.models import Stream, Streamer, RecordingSettings
            
            with SessionLocal() as db:
                # Get stream and related data
                stream = db.query(Stream).filter(Stream.id == stream_id).first()
                if not stream:
                    logger.warning(f"Stream {stream_id} not found for path generation")
                    return None
                    
                streamer = db.query(Streamer).filter(Streamer.id == stream.streamer_id).first()
                if not streamer:
                    logger.warning(f"Streamer not found for stream {stream_id}")
                    return None
                
                # Get template from settings
                settings = db.query(RecordingSettings).first()
                template = settings.filename_template if settings else "default"
                
                # Prepare stream data for path generation
                stream_data = {
                    'id': stream.id,
                    'title': stream.title or 'untitled',
                    'category_name': stream.category_name or 'unknown',
                    'language': stream.language or 'en'
                }
                
                # Use existing path_utils to generate filename
                filename = generate_filename(streamer, stream_data, template)
                
                # Get output directory from ts_path parent or use default
                ts_dir = Path(ts_path).parent
                mp4_path = ts_dir / filename
                
                logger.info(f"Generated output path for stream {stream_id}: {mp4_path}")
                return str(mp4_path)
                
        except Exception as e:
            logger.error(f"Error generating output path for stream {stream_id}: {e}", exc_info=True)
            return None

    async def _generate_ffmpeg_metadata_file(self, stream_id: int, mp4_path: str) -> Optional[str]:
        """Generate FFmpeg metadata file with chapters using existing utilities
        
        Args:
            stream_id: ID of the stream
            mp4_path: Path to the MP4 file
            
        Returns:
            Path to the metadata file or None if generation failed
        """
        try:
            from app.database import SessionLocal
            from app.models import Stream, StreamEvent, Streamer
            
            with SessionLocal() as db:
                # Get stream and related data
                stream = db.query(Stream).filter(Stream.id == stream_id).first()
                if not stream:
                    logger.warning(f"Stream {stream_id} not found for metadata generation")
                    return None
                    
                streamer = db.query(Streamer).filter(Streamer.id == stream.streamer_id).first()
                if not streamer:
                    logger.warning(f"Streamer not found for stream {stream_id}")
                    return None
                
                # Get stream events for chapter generation
                events = db.query(StreamEvent).filter(
                    StreamEvent.stream_id == stream_id
                ).order_by(StreamEvent.timestamp).all()
                
                # Create chapters from events
                chapters = []
                if events and stream.started_at:
                    for i, event in enumerate(events):
                        # Calculate chapter timing
                        start_time = (event.timestamp - stream.started_at).total_seconds()
                        
                        # End time is either next event or +30 minutes for last event
                        if i < len(events) - 1:
                            next_event = events[i + 1]
                            end_time = (next_event.timestamp - stream.started_at).total_seconds()
                        else:
                            end_time = start_time + (30 * 60)  # 30 minutes default
                        
                        # Create chapter
                        chapter_title = self._generate_chapter_title(event)
                        chapters.append({
                            'start_time': max(0, start_time),  # Ensure non-negative
                            'end_time': end_time,
                            'title': chapter_title
                        })
                
                # Create temporary metadata file using existing utility
                temp_dir = Path(mp4_path).parent
                metadata_file = temp_dir / f"metadata_{stream_id}_{int(datetime.now().timestamp())}.txt"
                
                # Use existing file_utils function to create chapters file
                success = await create_ffmpeg_chapters_file(
                    chapters=chapters,
                    output_path=str(metadata_file),
                    title=stream.title or f"{streamer.username} Stream",
                    artist=streamer.username,
                    date=stream.started_at.strftime('%Y-%m-%d') if stream.started_at else datetime.now().strftime('%Y-%m-%d'),
                    overwrite=True
                )
                
                if success:
                    logger.info(f"Generated FFmpeg metadata file for stream {stream_id}: {metadata_file}")
                    return str(metadata_file)
                else:
                    logger.error(f"Failed to create metadata file for stream {stream_id}")
                    return None
                
        except Exception as e:
            logger.error(f"Error generating FFmpeg metadata file for stream {stream_id}: {e}", exc_info=True)
            return None

    def _generate_chapter_title(self, event) -> str:
        """Generate a chapter title from a stream event
        
        Args:
            event: StreamEvent object
            
        Returns:
            Chapter title string
        """
        try:
            if event.event_type == 'stream.online':
                return "Stream Started"
            elif event.event_type == 'stream.offline':
                return "Stream Ended"
            elif event.event_type == 'channel.update':
                if event.title:
                    return f"Title: {event.title[:50]}"
                elif event.category_name:
                    return f"Category: {event.category_name}"
                else:
                    return "Stream Update"
            else:
                return f"Event: {event.event_type}"
                
        except Exception as e:
            logger.error(f"Error generating chapter title: {e}")
            return "Unknown Event"

    async def _cleanup_temporary_files(self, ts_path: str, metadata_file_path: Optional[str]) -> None:
        """Clean up temporary files after processing
        
        Args:
            ts_path: Path to the TS file
            metadata_file_path: Path to the temporary metadata file
        """
        try:
            # Clean up metadata file
            if metadata_file_path and os.path.exists(metadata_file_path):
                os.unlink(metadata_file_path)
                logger.debug(f"Cleaned up metadata file: {metadata_file_path}")
                
            # Clean up TS file (with some delay to ensure MP4 is complete)
            if os.path.exists(ts_path):
                await asyncio.sleep(2)  # Small delay
                try:
                    os.unlink(ts_path)
                    logger.info(f"Cleaned up TS file: {ts_path}")
                except Exception as e:
                    logger.warning(f"Could not clean up TS file {ts_path}: {e}")
                    
        except Exception as e:
            logger.error(f"Error cleaning up temporary files: {e}", exc_info=True)

    async def _get_streamer_name(self, stream_id: int) -> str:
        """Get streamer name for a stream
        
        Args:
            stream_id: ID of the stream
            
        Returns:
            Streamer name or 'unknown'
        """
        try:
            from app.database import SessionLocal
            from app.models import Stream, Streamer
            
            with SessionLocal() as db:
                stream = db.query(Stream).filter(Stream.id == stream_id).first()
                if stream and stream.streamer:
                    return stream.streamer.username
                    
        except Exception as e:
            logger.error(f"Error getting streamer name for stream {stream_id}: {e}")
            
        return "unknown"

    async def _ensure_artwork_directory(self, mp4_path: str) -> None:
        """Ensure .artwork directory exists for hidden metadata files"""
        try:
            # Get recordings directory from MP4 path
            recordings_dir = Path(mp4_path).parents[1]  # Go up from streamer dir to recordings dir
            artwork_dir = recordings_dir / ".artwork"
            
            # Create .artwork directory if it doesn't exist
            artwork_dir.mkdir(parents=True, exist_ok=True)
            
            # Also create streamer subdirectory in .artwork
            mp4_streamer_dir = Path(mp4_path).parent
            streamer_name = mp4_streamer_dir.name
            streamer_artwork_dir = artwork_dir / streamer_name
            streamer_artwork_dir.mkdir(parents=True, exist_ok=True)
            
            logger.debug(f"Ensured artwork directory exists: {artwork_dir}")
            
        except Exception as e:
            logger.error(f"Error creating artwork directory: {e}", exc_info=True)

    async def _generate_thumbnail(self, stream_id: int, mp4_path: str) -> bool:
        """Generate thumbnail using dedicated thumbnail service (1 minute into stream)"""
        try:
            # Use the thumbnail service to create a high-quality thumbnail
            # Try to extract from 1 minute into the video (as requested by user)
            mp4_dir = Path(mp4_path).parent
            base_filename = Path(mp4_path).stem
            thumbnail_path = mp4_dir / f"{base_filename}-thumb.jpg"
            
            # Try multiple timestamps to get the best thumbnail
            timestamps = ["00:01:00", "00:02:00", "00:05:00", "00:00:30"]  # 1min, 2min, 5min, 30sec
            
            for timestamp in timestamps:
                logger.info(f"Attempting to create thumbnail at {timestamp} for stream {stream_id}")
                
                success = await self.thumbnail_service.extract_thumbnail_from_video(
                    video_path=mp4_path,
                    output_path=str(thumbnail_path),
                    timestamp=timestamp
                )
                
                if success and os.path.exists(thumbnail_path) and os.path.getsize(thumbnail_path) > 1000:
                    logger.info(f"Successfully created thumbnail at {timestamp}: {thumbnail_path}")
                    return True
                    
            # If video extraction failed, try the existing thumbnail service fallback
            logger.info(f"Video thumbnail extraction failed, trying Twitch thumbnail fallback for stream {stream_id}")
            result_path = await self.thumbnail_service.ensure_thumbnail_with_fallback(
                stream_id=stream_id,
                output_dir=str(mp4_dir),
                video_path=mp4_path
            )
            
            return result_path is not None
            
        except Exception as e:
            logger.error(f"Error generating thumbnail for stream {stream_id}: {e}", exc_info=True)
            return False