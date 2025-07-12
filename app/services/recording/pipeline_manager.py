"""
Sequential pipeline manager for recording post-processing.

This module ensures that post-processing tasks run in the correct order:
1. Recording finishes → 2. Metadata/chapters generated → 3. TS to MP4 remux with embedded metadata
4. Thumbnail extracted from final MP4 → 5. File size validation → 6. TS cleanup
"""
import logging
import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any

# Import existing utilities
from app.utils.file_utils import remux_file, create_ffmpeg_chapters_file
from app.utils.path_utils import generate_filename, update_recording_path
from app.services.metadata_service import MetadataService
from app.services.thumbnail_service import ThumbnailService
from app.services.recording.exceptions import FileOperationError

logger = logging.getLogger("streamvault")

class PipelineManager:
    """Manages sequential post-processing pipeline for recordings"""

    def __init__(self, config_manager=None):
        self.config_manager = config_manager
        self.metadata_service = MetadataService()
        self.thumbnail_service = ThumbnailService()
        
        # Pipeline step tracking
        self.active_pipelines = {}
        
    async def start_post_processing_pipeline(self, stream_id: int, ts_path: str) -> Dict[str, Any]:
        """Start the complete sequential post-processing pipeline
        
        Args:
            stream_id: ID of the stream
            ts_path: Path to the completed TS file
            
        Returns:
            Dictionary with pipeline results
        """
        pipeline_id = f"pipeline_{stream_id}_{int(datetime.now().timestamp())}"
        
        try:
            logger.info(f"Starting post-processing pipeline {pipeline_id} for stream {stream_id}")
            
            # Initialize pipeline tracking
            pipeline_state = {
                'stream_id': stream_id,
                'ts_path': ts_path,
                'mp4_path': None,
                'start_time': datetime.now(),
                'current_step': 'starting',
                'completed_steps': [],
                'errors': []
            }
            
            self.active_pipelines[pipeline_id] = pipeline_state
            
            # Step 1: Generate output path using existing path_utils
            logger.info(f"Pipeline {pipeline_id}: Step 1 - Generating output path")
            pipeline_state['current_step'] = 'generate_path'
            
            mp4_path = await self._generate_output_path(stream_id, ts_path)
            if not mp4_path:
                raise FileOperationError("Failed to generate output path")
                
            pipeline_state['mp4_path'] = mp4_path
            pipeline_state['completed_steps'].append('generate_path')
            
            # Step 2: Generate metadata files (NFO, JSON, chapters)
            logger.info(f"Pipeline {pipeline_id}: Step 2 - Generating metadata and chapters")
            pipeline_state['current_step'] = 'metadata_generation'
            
            metadata_success = await self._generate_metadata_and_chapters(stream_id, mp4_path)
            if not metadata_success:
                logger.warning(f"Metadata generation failed for pipeline {pipeline_id}, continuing anyway")
                pipeline_state['errors'].append('metadata_generation_failed')
            
            pipeline_state['completed_steps'].append('metadata_generation')
            
            # Step 3: Remux TS to MP4 with embedded metadata and chapters
            logger.info(f"Pipeline {pipeline_id}: Step 3 - Converting TS to MP4 with metadata")
            pipeline_state['current_step'] = 'ts_to_mp4_conversion'
            
            conversion_success = await self._convert_ts_to_mp4_with_metadata(stream_id, ts_path, mp4_path)
            if not conversion_success:
                raise FileOperationError("TS to MP4 conversion failed")
                
            pipeline_state['completed_steps'].append('ts_to_mp4_conversion')
            
            # Step 4: Extract thumbnail from final MP4 file
            logger.info(f"Pipeline {pipeline_id}: Step 4 - Extracting thumbnail from MP4")
            pipeline_state['current_step'] = 'thumbnail_extraction'
            
            thumbnail_success = await self._extract_thumbnail_from_mp4(stream_id, mp4_path)
            if not thumbnail_success:
                logger.warning(f"Thumbnail extraction failed for pipeline {pipeline_id}, continuing anyway")
                pipeline_state['errors'].append('thumbnail_extraction_failed')
                
            pipeline_state['completed_steps'].append('thumbnail_extraction')
            
            # Step 5: Validate MP4 file size vs TS file size
            logger.info(f"Pipeline {pipeline_id}: Step 5 - Validating file sizes")
            pipeline_state['current_step'] = 'file_size_validation'
            
            size_validation_passed = await self._validate_file_sizes(ts_path, mp4_path)
            if not size_validation_passed:
                logger.error(f"File size validation failed for pipeline {pipeline_id} - MP4 significantly smaller than TS")
                pipeline_state['errors'].append('file_size_validation_failed')
                # Don't continue to cleanup if validation failed
                
            pipeline_state['completed_steps'].append('file_size_validation')
            
            # Step 6: Clean up TS file (only if validation passed)
            if size_validation_passed:
                logger.info(f"Pipeline {pipeline_id}: Step 6 - Cleaning up TS file")
                pipeline_state['current_step'] = 'ts_cleanup'
                
                cleanup_success = await self._cleanup_ts_file(ts_path)
                if cleanup_success:
                    pipeline_state['completed_steps'].append('ts_cleanup')
                else:
                    pipeline_state['errors'].append('ts_cleanup_failed')
            else:
                logger.warning(f"Skipping TS cleanup for pipeline {pipeline_id} due to size validation failure")
                
            # Step 7: Update database with final path
            logger.info(f"Pipeline {pipeline_id}: Step 7 - Updating database")
            pipeline_state['current_step'] = 'database_update'
            
            await update_recording_path(stream_id, mp4_path)
            pipeline_state['completed_steps'].append('database_update')
            
            # Pipeline completed
            pipeline_state['current_step'] = 'completed'
            duration = (datetime.now() - pipeline_state['start_time']).total_seconds()
            
            logger.info(f"Pipeline {pipeline_id} completed in {duration:.2f}s. Steps: {len(pipeline_state['completed_steps'])}, Errors: {len(pipeline_state['errors'])}")
            
            return {
                'success': len(pipeline_state['errors']) == 0 or 'file_size_validation_failed' not in pipeline_state['errors'],
                'mp4_path': mp4_path,
                'completed_steps': pipeline_state['completed_steps'],
                'errors': pipeline_state['errors'],
                'duration_seconds': duration
            }
            
        except Exception as e:
            logger.error(f"Pipeline {pipeline_id} failed: {e}", exc_info=True)
            if pipeline_id in self.active_pipelines:
                self.active_pipelines[pipeline_id]['current_step'] = 'failed'
                self.active_pipelines[pipeline_id]['errors'].append(str(e))
            
            return {
                'success': False,
                'mp4_path': pipeline_state.get('mp4_path'),
                'completed_steps': pipeline_state.get('completed_steps', []),
                'errors': pipeline_state.get('errors', []) + [str(e)],
                'duration_seconds': 0
            }
            
        finally:
            # Cleanup services
            await self.metadata_service.close()
            await self.thumbnail_service.close()
            
            # Remove from active pipelines
            if pipeline_id in self.active_pipelines:
                del self.active_pipelines[pipeline_id]

    async def _generate_output_path(self, stream_id: int, ts_path: str) -> Optional[str]:
        """Generate the final MP4 output path using existing path_utils"""
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
                
                # Get template from settings (user-configured)
                settings = db.query(RecordingSettings).first()
                template = settings.filename_template if settings else "default"
                
                # Prepare stream data for path generation
                stream_data = {
                    'id': stream.id,
                    'title': stream.title or 'untitled',
                    'category_name': stream.category_name or 'unknown',
                    'language': stream.language or 'en'
                }
                
                # Use existing path_utils to generate filename with user template
                filename = generate_filename(streamer, stream_data, template)
                
                # Get output directory from ts_path parent or use configured directory
                if settings and settings.output_directory:
                    base_dir = Path(settings.output_directory)
                else:
                    base_dir = Path(ts_path).parent.parent  # Go up from streamer dir
                
                # Create full path respecting user's folder structure template
                mp4_path = base_dir / Path(filename).parent / Path(filename).name
                mp4_path.parent.mkdir(parents=True, exist_ok=True)
                
                logger.info(f"Generated output path for stream {stream_id}: {mp4_path}")
                return str(mp4_path)
                
        except Exception as e:
            logger.error(f"Error generating output path for stream {stream_id}: {e}", exc_info=True)
            return None

    async def _generate_metadata_and_chapters(self, stream_id: int, mp4_path: str) -> bool:
        """Generate metadata files and chapters using existing metadata service"""
        try:
            # Use existing metadata service to generate all metadata files
            success = await self.metadata_service.generate_metadata_for_stream(
                stream_id=stream_id,
                mp4_path=mp4_path
            )
            
            if success:
                logger.info(f"Successfully generated metadata and chapters for stream {stream_id}")
            else:
                logger.error(f"Failed to generate metadata and chapters for stream {stream_id}")
                
            return success
            
        except Exception as e:
            logger.error(f"Error generating metadata and chapters for stream {stream_id}: {e}", exc_info=True)
            return False

    async def _convert_ts_to_mp4_with_metadata(self, stream_id: int, ts_path: str, mp4_path: str) -> bool:
        """Convert TS to MP4 with embedded metadata and chapters"""
        try:
            # Generate FFmpeg metadata file with chapters
            metadata_file_path = await self._generate_ffmpeg_metadata_file(stream_id, mp4_path)
            
            # Get streamer name for logging
            streamer_name = await self._get_streamer_name(stream_id)
            
            # Use existing remux_file function with metadata
            conversion_result = await remux_file(
                input_path=ts_path,
                output_path=mp4_path,
                overwrite=True,
                metadata_file=metadata_file_path,
                streamer_name=streamer_name
            )
            
            # Clean up temporary metadata file
            if metadata_file_path and os.path.exists(metadata_file_path):
                try:
                    os.unlink(metadata_file_path)
                except Exception as e:
                    logger.warning(f"Could not clean up metadata file {metadata_file_path}: {e}")
            
            success = conversion_result.get('success', False)
            
            if success:
                logger.info(f"Successfully converted TS to MP4 with metadata for stream {stream_id}")
            else:
                logger.error(f"TS to MP4 conversion failed for stream {stream_id}: {conversion_result.get('stderr', 'No error details')}")
                
            return success
            
        except Exception as e:
            logger.error(f"Error converting TS to MP4 for stream {stream_id}: {e}", exc_info=True)
            return False

    async def _generate_ffmpeg_metadata_file(self, stream_id: int, mp4_path: str) -> Optional[str]:
        """Generate FFmpeg metadata file with chapters"""
        try:
            from app.database import SessionLocal
            from app.models import Stream, StreamEvent, Streamer, RecordingSettings
            
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
                
                # Check user preference for chapter titles (title vs category)
                settings = db.query(RecordingSettings).first()
                use_category_as_chapter = settings.use_category_as_chapter_title if settings else False
                
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
                        
                        # Create chapter title based on user preference
                        if use_category_as_chapter and event.category_name:
                            chapter_title = event.category_name
                        elif event.title:
                            chapter_title = event.title[:50]  # Limit length
                        else:
                            chapter_title = self._generate_chapter_title(event)
                            
                        chapters.append({
                            'start_time': max(0, start_time),  # Ensure non-negative
                            'end_time': end_time,
                            'title': chapter_title
                        })
                
                # Create temporary metadata file
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
        """Generate a chapter title from a stream event"""
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

    async def _extract_thumbnail_from_mp4(self, stream_id: int, mp4_path: str) -> bool:
        """Extract thumbnail from final MP4 file using FFmpeg"""
        try:
            mp4_dir = Path(mp4_path).parent
            base_filename = Path(mp4_path).stem
            thumbnail_path = mp4_dir / f"{base_filename}-thumb.jpg"
            
            # Try multiple timestamps to get the best thumbnail from MP4
            timestamps = ["00:01:00", "00:02:00", "00:05:00", "00:00:30"]  # 1min, 2min, 5min, 30sec
            
            for timestamp in timestamps:
                logger.info(f"Attempting to extract thumbnail from MP4 at {timestamp} for stream {stream_id}")
                
                success = await self.thumbnail_service.extract_thumbnail_from_video(
                    video_path=mp4_path,
                    output_path=str(thumbnail_path),
                    timestamp=timestamp
                )
                
                if success and os.path.exists(thumbnail_path) and os.path.getsize(thumbnail_path) > 1000:
                    logger.info(f"Successfully extracted thumbnail from MP4 at {timestamp}: {thumbnail_path}")
                    
                    # Update database with thumbnail path
                    await self._update_thumbnail_in_database(stream_id, str(thumbnail_path))
                    return True
                    
            logger.warning(f"Failed to extract thumbnail from MP4 for stream {stream_id}")
            return False
            
        except Exception as e:
            logger.error(f"Error extracting thumbnail from MP4 for stream {stream_id}: {e}", exc_info=True)
            return False

    async def _update_thumbnail_in_database(self, stream_id: int, thumbnail_path: str):
        """Update StreamMetadata with thumbnail path"""
        try:
            from app.database import SessionLocal
            from app.models import StreamMetadata
            
            with SessionLocal() as db:
                metadata = db.query(StreamMetadata).filter(StreamMetadata.stream_id == stream_id).first()
                if metadata:
                    metadata.thumbnail_path = thumbnail_path
                    db.commit()
                    logger.debug(f"Updated thumbnail path in database for stream {stream_id}")
                    
        except Exception as e:
            logger.error(f"Error updating thumbnail in database for stream {stream_id}: {e}")

    async def _validate_file_sizes(self, ts_path: str, mp4_path: str) -> bool:
        """Validate that MP4 file size is reasonable compared to TS file"""
        try:
            if not os.path.exists(ts_path) or not os.path.exists(mp4_path):
                logger.error(f"File missing for size validation - TS: {os.path.exists(ts_path)}, MP4: {os.path.exists(mp4_path)}")
                return False
                
            ts_size = os.path.getsize(ts_path)
            mp4_size = os.path.getsize(mp4_path)
            
            if ts_size == 0:
                logger.error(f"TS file is empty: {ts_path}")
                return False
                
            if mp4_size == 0:
                logger.error(f"MP4 file is empty: {mp4_path}")
                return False
                
            # Calculate size ratio
            size_ratio = mp4_size / ts_size
            
            # MP4 should be between 70% and 110% of TS size (allowing for small variations)
            if size_ratio < 0.7:
                logger.error(f"MP4 file significantly smaller than TS - Ratio: {size_ratio:.2f} (TS: {ts_size/1024/1024:.2f}MB, MP4: {mp4_size/1024/1024:.2f}MB)")
                return False
            elif size_ratio > 1.1:
                logger.warning(f"MP4 file larger than TS - Ratio: {size_ratio:.2f} (TS: {ts_size/1024/1024:.2f}MB, MP4: {mp4_size/1024/1024:.2f}MB)")
                # This is okay, sometimes MP4 can be slightly larger due to metadata
                
            logger.info(f"File size validation passed - Ratio: {size_ratio:.2f} (TS: {ts_size/1024/1024:.2f}MB, MP4: {mp4_size/1024/1024:.2f}MB)")
            return True
            
        except Exception as e:
            logger.error(f"Error validating file sizes: {e}", exc_info=True)
            return False

    async def _cleanup_ts_file(self, ts_path: str) -> bool:
        """Clean up TS file after successful validation"""
        try:
            if os.path.exists(ts_path):
                # Add small delay to ensure MP4 write is complete
                await asyncio.sleep(2)
                
                os.unlink(ts_path)
                logger.info(f"Successfully cleaned up TS file: {ts_path}")
                return True
            else:
                logger.warning(f"TS file not found for cleanup: {ts_path}")
                return False
                
        except Exception as e:
            logger.error(f"Error cleaning up TS file {ts_path}: {e}", exc_info=True)
            return False

    async def _get_streamer_name(self, stream_id: int) -> str:
        """Get streamer name for a stream"""
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

    def get_active_pipelines(self) -> Dict[str, Dict[str, Any]]:
        """Get information about currently active pipelines"""
        return {
            pipeline_id: {
                'stream_id': info['stream_id'],
                'current_step': info['current_step'],
                'completed_steps': info['completed_steps'],
                'errors': info['errors'],
                'duration_seconds': int((datetime.now() - info['start_time']).total_seconds())
            }
            for pipeline_id, info in self.active_pipelines.items()
        }