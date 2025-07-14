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
from app.utils.ffmpeg_utils import convert_ts_to_mp4, validate_mp4
from app.utils.path_utils import update_recording_path
from app.services.metadata_service import MetadataService
from app.services.thumbnail_service import ThumbnailService
from app.services.recording.exceptions import FileOperationError
from app.utils import async_file

logger = logging.getLogger("streamvault")

class PipelineManager:
    """Manages sequential post-processing pipeline for recordings"""

    def __init__(self, config_manager=None):
        self.config_manager = config_manager
        self.metadata_service = MetadataService()
        self.thumbnail_service = ThumbnailService()
        
        # Pipeline step tracking
        self.active_pipelines = {}
        
        # Shutdown management
        self._is_shutting_down = False
        
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
            
            # Step 1: Generate MP4 path (same location as TS, just different extension)
            logger.info(f"Pipeline {pipeline_id}: Step 1 - Generating output path")
            pipeline_state['current_step'] = 'generate_path'
            
            mp4_path = str(Path(ts_path).with_suffix('.mp4'))
            pipeline_state['mp4_path'] = mp4_path
            pipeline_state['completed_steps'].append('generate_path')
            
            # Step 2: Generate metadata files (NFO, JSON, chapters)
            logger.info(f"Pipeline {pipeline_id}: Step 2 - Generating metadata and chapters")
            pipeline_state['current_step'] = 'metadata_generation'
            
            base_path = str(Path(ts_path).parent)
            base_filename = Path(ts_path).stem
            
            metadata_success = await self.metadata_service.generate_metadata_for_stream(
                stream_id=stream_id,
                base_path=base_path,
                base_filename=base_filename
            )
            
            if not metadata_success:
                logger.warning(f"Metadata generation failed for pipeline {pipeline_id}, continuing anyway")
                pipeline_state['errors'].append('metadata_generation_failed')
            
            pipeline_state['completed_steps'].append('metadata_generation')
            
            # Step 3: Convert TS to MP4 with embedded chapters
            logger.info(f"Pipeline {pipeline_id}: Step 3 - Converting TS to MP4 with metadata")
            pipeline_state['current_step'] = 'ts_to_mp4_conversion'
            
            # Get chapters file path and verify it exists
            chapters_file = Path(base_path) / f"{base_filename}-ffmpeg-chapters.txt"
            
            # Additional safety check: ensure chapter file exists before remux
            if chapters_file.exists():
                logger.info(f"Pipeline {pipeline_id}: FFmpeg chapters file ready: {chapters_file}")
                metadata_file_path = str(chapters_file)
            else:
                logger.warning(f"Pipeline {pipeline_id}: FFmpeg chapters file not found: {chapters_file}")
                metadata_file_path = None
            
            conversion_result = await convert_ts_to_mp4(
                input_path=ts_path,
                output_path=mp4_path,
                metadata_file=metadata_file_path,
                overwrite=True
            )
            
            if not conversion_result['success']:
                raise FileOperationError(f"TS to MP4 conversion failed: {conversion_result.get('error', 'Unknown error')}")
                
            pipeline_state['completed_steps'].append('ts_to_mp4_conversion')
            
            # Step 4: Validate MP4 file
            logger.info(f"Pipeline {pipeline_id}: Step 4 - Validating MP4 file")
            pipeline_state['current_step'] = 'mp4_validation'
            
            if not await validate_mp4(mp4_path):
                raise FileOperationError("MP4 validation failed")
                
            pipeline_state['completed_steps'].append('mp4_validation')
            
            # Step 5: Extract thumbnail from final MP4 file
            logger.info(f"Pipeline {pipeline_id}: Step 5 - Extracting thumbnail from MP4")
            pipeline_state['current_step'] = 'thumbnail_extraction'
            
            thumbnail_path = await self.metadata_service.extract_thumbnail(
                video_path=mp4_path,
                stream_id=stream_id
            )
            
            if not thumbnail_path:
                logger.warning(f"Thumbnail extraction failed for pipeline {pipeline_id}, continuing anyway")
                pipeline_state['errors'].append('thumbnail_extraction_failed')
                
            pipeline_state['completed_steps'].append('thumbnail_extraction')
            
            # Step 6: Validate file sizes
            logger.info(f"Pipeline {pipeline_id}: Step 6 - Validating file sizes")
            pipeline_state['current_step'] = 'file_size_validation'
            
            size_validation_passed = await self._validate_file_sizes(ts_path, mp4_path)
            if not size_validation_passed:
                logger.error(f"File size validation failed for pipeline {pipeline_id}")
                pipeline_state['errors'].append('file_size_validation_failed')
                
            pipeline_state['completed_steps'].append('file_size_validation')
            
            # Step 7: Clean up TS file (only if validation passed)
            if size_validation_passed:
                logger.info(f"Pipeline {pipeline_id}: Step 7 - Cleaning up TS file")
                pipeline_state['current_step'] = 'ts_cleanup'
                
                cleanup_success = await self._cleanup_ts_file(ts_path)
                if cleanup_success:
                    pipeline_state['completed_steps'].append('ts_cleanup')
                else:
                    pipeline_state['errors'].append('ts_cleanup_failed')
            else:
                logger.warning(f"Skipping TS cleanup for pipeline {pipeline_id} due to validation failure")
                
            # Step 8: Update database with final path
            logger.info(f"Pipeline {pipeline_id}: Step 8 - Updating database")
            pipeline_state['current_step'] = 'database_update'
            
            await update_recording_path(stream_id, mp4_path)
            pipeline_state['completed_steps'].append('database_update')
            
            # Pipeline completed
            pipeline_state['current_step'] = 'completed'
            duration = (datetime.now() - pipeline_state['start_time']).total_seconds()
            
            logger.info(f"Pipeline {pipeline_id} completed in {duration:.2f}s")
            
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

    async def _validate_file_sizes(self, ts_path: str, mp4_path: str) -> bool:
        """Validate that MP4 file size is reasonable compared to TS file"""
        try:
            if not await async_file.exists(ts_path) or not await async_file.exists(mp4_path):
                logger.error(f"File missing for validation - TS: {await async_file.exists(ts_path)}, MP4: {await async_file.exists(mp4_path)}")
                return False
                
            ts_size = await async_file.getsize(ts_path)
            mp4_size = await async_file.getsize(mp4_path)
            
            if ts_size == 0:
                logger.error(f"TS file is empty: {ts_path}")
                return False
                
            if mp4_size == 0:
                logger.error(f"MP4 file is empty: {mp4_path}")
                return False
                
            # Calculate size ratio
            size_ratio = mp4_size / ts_size
            
            # MP4 should be between 70% and 110% of TS size
            if size_ratio < 0.7:
                logger.error(f"MP4 file too small - Ratio: {size_ratio:.2f} (TS: {ts_size/1024/1024:.2f}MB, MP4: {mp4_size/1024/1024:.2f}MB)")
                return False
            elif size_ratio > 1.1:
                logger.warning(f"MP4 file larger than TS - Ratio: {size_ratio:.2f} (this is usually okay)")
                
            logger.info(f"File size validation passed - Ratio: {size_ratio:.2f}")
            return True
            
        except Exception as e:
            logger.error(f"Error validating file sizes: {e}", exc_info=True)
            return False

    async def _cleanup_ts_file(self, ts_path: str) -> bool:
        """Clean up TS file after successful validation"""
        try:
            if await async_file.exists(ts_path):
                # Add small delay to ensure MP4 write is complete
                await asyncio.sleep(2)
                
                await async_file.unlink(ts_path)
                logger.info(f"Successfully cleaned up TS file: {ts_path}")
                return True
            else:
                logger.warning(f"TS file not found for cleanup: {ts_path}")
                return False
                
        except Exception as e:
            logger.error(f"Error cleaning up TS file {ts_path}: {e}", exc_info=True)
            return False

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

    async def graceful_shutdown(self, timeout: int = 30):
        """Gracefully shutdown the pipeline manager
        
        Args:
            timeout: Maximum time to wait for pipelines to complete (seconds)
        """
        logger.info("🛑 Starting graceful shutdown of Pipeline Manager...")
        self._is_shutting_down = True
        
        try:
            active_count = len(self.active_pipelines)
            if active_count == 0:
                logger.info("No active pipelines to shutdown")
                return
            
            logger.info(f"⏳ Waiting for {active_count} active pipelines to complete...")
            
            # Wait for pipelines to finish naturally
            start_time = asyncio.get_event_loop().time()
            while self.active_pipelines and (asyncio.get_event_loop().time() - start_time) < timeout:
                await asyncio.sleep(1)
            
            # Log remaining pipelines
            remaining_count = len(self.active_pipelines)
            if remaining_count > 0:
                logger.warning(f"⚠️ {remaining_count} pipelines still running after timeout")
                for pipeline_id in self.active_pipelines:
                    logger.warning(f"Pipeline still active: {pipeline_id}")
            
            logger.info("✅ Pipeline Manager graceful shutdown completed")
            
        except Exception as e:
            logger.error(f"❌ Error during Pipeline Manager shutdown: {e}", exc_info=True)

    def is_shutting_down(self) -> bool:
        """Check if pipeline manager is shutting down"""
        return self._is_shutting_down