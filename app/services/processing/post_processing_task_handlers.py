"""
Task handlers for post-processing tasks
Implements the actual task execution logic for different post-processing operations
"""
import asyncio
import logging
import os
import copy
from pathlib import Path
from typing import Dict, Any

from app.database import SessionLocal
from app.models import Stream, Recording, StreamMetadata, Streamer, RecordingProcessingState
from app.services.media.metadata_service import MetadataService
from app.services.media.thumbnail_service import ThumbnailService
from app.services.communication.websocket_manager import websocket_manager
from app.utils import ffmpeg_utils
from app.utils.structured_logging import log_with_context

logger = logging.getLogger("streamvault")

class PostProcessingTaskHandlers:
    """Collection of task handlers for post-processing operations"""
    
    def __init__(self):
        self.metadata_service = MetadataService()
        self.thumbnail_service = ThumbnailService()
        # Debounce map: recording_id -> pending snapshot & task
        self._broadcast_debounce = {}
        
        # Initialize logging service
        try:
            from app.services.system.logging_service import logging_service
            self.logging_service = logging_service
        except Exception as e:
            logger.warning(f"Could not initialize logging service: {e}")
            self.logging_service = None
    
    async def handle_metadata_generation(self, payload, progress_callback=None):
        """Handle metadata generation task"""
        # Deep copy payload to avoid accidental mutation across tasks
        local_payload = copy.deepcopy(payload)

        stream_id = local_payload['stream_id']
        base_filename = local_payload['base_filename']
        output_dir = local_payload['output_dir']

        log_with_context(
            logger, 'info',
            f"Starting metadata generation for stream {stream_id}",
            task_id=local_payload.get('task_id'),
            stream_id=stream_id,
            operation='metadata_generation_start'
        )
        # Mark running state (best-effort)
        try:
            with SessionLocal() as db:
                rec_id = local_payload.get('recording_id')
                if rec_id:
                    self._set_status(db, rec_id, stream_id, 'metadata_generation', 'running')
        except Exception as e:
            logger.debug(f"metadata_generation: failed to mark running state: {e}")

        try:
            # Update progress
            if progress_callback:
                progress_callback(10.0)

            # Verify input parameters
            if not stream_id or not base_filename or not output_dir:
                raise ValueError(f"Missing required parameters: stream_id={stream_id}, base_filename={base_filename}, output_dir={output_dir}")

            # Normalize base filename (strip common extensions if provided)
            if base_filename.lower().endswith(('.mp4', '.ts', '.mkv')):
                base_filename = Path(base_filename).stem

            # If possible, correct output_dir and base_filename from the authoritative recording_path
            try:
                with SessionLocal() as db:
                    stream = db.query(Stream).filter(Stream.id == stream_id).first()
                    if stream and getattr(stream, 'recording_path', None):
                        rec_path = Path(stream.recording_path)
                        if rec_path.exists():
                            rec_dir = str(rec_path.parent)
                            rec_stem = rec_path.stem
                            if rec_dir != output_dir or rec_stem != base_filename:
                                logger.warning(
                                    "[METADATA_DIR_CORRECTION] Provided output/base did not match recording_path; correcting. "
                                    f"stream_id={stream_id}, provided_dir={output_dir}, provided_name={base_filename}, "
                                    f"recording_dir={rec_dir}, recording_name={rec_stem}"
                                )
                                output_dir = rec_dir
                                base_filename = rec_stem
            except Exception as corr_err:
                logger.debug(f"Could not correct metadata generation paths from recording_path: {corr_err}")

            # Check if output directory exists
            output_path = Path(output_dir)
            if not output_path.exists():
                log_with_context(
                    logger, 'warning',
                    f"Output directory does not exist, creating: {output_dir}",
                    stream_id=stream_id,
                    operation='metadata_generation_dir_create'
                )
                output_path.mkdir(parents=True, exist_ok=True)

            if progress_callback:
                progress_callback(20.0)

            # Generate metadata using metadata service
            try:
                success = await self.metadata_service.generate_metadata_for_stream(
                    stream_id=stream_id,
                    base_path=output_dir,
                    base_filename=base_filename
                )

                if not success:
                    log_with_context(
                        logger, 'warning',
                        f"Metadata generation returned False for stream {stream_id} - continuing with post-processing",
                        task_id=local_payload.get('task_id'),
                        stream_id=stream_id,
                        operation='metadata_generation_warning'
                    )
                else:
                    log_with_context(
                        logger, 'info',
                        f"Metadata generation completed successfully for stream {stream_id}",
                        task_id=local_payload.get('task_id'),
                        stream_id=stream_id,
                        operation='metadata_generation_complete'
                    )
            except Exception as metadata_error:
                log_with_context(
                    logger, 'warning',
                    f"Metadata generation failed for stream {stream_id}: {metadata_error} - continuing with post-processing",
                    task_id=local_payload.get('task_id'),
                    stream_id=stream_id,
                    error=str(metadata_error),
                    operation='metadata_generation_error_continue'
                )

            # Persist processing state
            try:
                with SessionLocal() as db:
                    rec_id = payload.get('recording_id')
                    if rec_id:
                        self._set_status(db, rec_id, stream_id, 'metadata_generation', 'completed')
            except Exception as persist_err:
                logger.debug(f"Could not persist metadata status: {persist_err}")

            if progress_callback:
                progress_callback(90.0)

            if progress_callback:
                progress_callback(100.0)

        except Exception as e:
            # Log any unexpected errors in the metadata generation task
            log_with_context(
                logger, 'error',
                f"Unexpected error in metadata generation task for stream {stream_id}: {e}",
                task_id=local_payload.get('task_id'),
                stream_id=stream_id,
                error=str(e),
                operation='metadata_generation_unexpected_error'
            )
            # Don't raise - metadata generation failures shouldn't stop post-processing
            # The specific metadata errors are already handled in the try-catch above
            try:
                with SessionLocal() as db:
                    rec_id = payload.get('recording_id')
                    stream_id = payload.get('stream_id')
                    if rec_id and stream_id:
                        self._set_status(db, rec_id, stream_id, 'metadata_generation', 'failed', str(e))
            except Exception as persist_err:
                logger.debug(f"Could not persist metadata failed status: {persist_err}")
    
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
            with SessionLocal() as db:
                rec_id = payload.get('recording_id')
                if rec_id:
                    self._set_status(db, rec_id, stream_id, 'chapters_generation', 'running')
        except Exception as e:
            logger.debug(f"chapters_generation: failed to mark running: {e}")
        
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
            # Persist
            try:
                with SessionLocal() as db:
                    rec_id = payload.get('recording_id')
                    stream_id = payload.get('stream_id')
                    if rec_id and stream_id:
                        self._set_status(db, rec_id, stream_id, 'chapters_generation', 'completed')
            except Exception as persist_err:
                logger.debug(f"Could not persist chapters status: {persist_err}")
            
        except Exception as e:
            log_with_context(
                logger, 'error',
                f"Chapters generation failed for stream {stream_id}: {e}",
                task_id=payload.get('task_id'),
                stream_id=stream_id,
                error=str(e),
                operation='chapters_generation_error'
            )
            # Persist failure
            try:
                with SessionLocal() as db:
                    rec_id = payload.get('recording_id')
                    stream_id = payload.get('stream_id')
                    if rec_id and stream_id:
                        self._set_status(db, rec_id, stream_id, 'chapters_generation', 'failed', str(e))
            except Exception as persist_err:
                logger.debug(f"Could not persist chapters failed status: {persist_err}")
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
        try:
            with SessionLocal() as db:
                rec_id = payload.get('recording_id')
                if rec_id:
                    self._set_status(db, rec_id, stream_id, 'mp4_remux', 'running')
        except Exception as e:
            logger.debug(f"mp4_remux: failed to mark running: {e}")
        
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
                
            # Update Stream.recording_path to the MP4 file
            with SessionLocal() as db:
                stream = db.query(Stream).filter(Stream.id == stream_id).first()
                if stream:
                    # Capture old path only for logging
                    old_path = stream.recording_path
                    stream.recording_path = mp4_output_path
                    db.commit()
                    logger.info(f"Updated Stream.recording_path for stream {stream_id}: {old_path} -> {mp4_output_path}")
                    
                    # Send WebSocket notification that recording is now available
                    try:
                        # Get streamer info for the notification
                        streamer = db.query(Streamer).filter(Streamer.id == stream.streamer_id).first()
                        if streamer and websocket_manager:
                            # Send recording available notification
                            import asyncio
                            async def send_notification():
                                await websocket_manager.send_message_to_all({
                                    "type": "recording_available",
                                    "data": {
                                        "stream_id": stream_id,
                                        "streamer_id": stream.streamer_id,
                                        "streamer_name": streamer.username,
                                        "recording_path": mp4_output_path,
                                        "title": stream.title
                                    }
                                })
                            
                            # Run async notification in the event loop
                            try:
                                loop = asyncio.get_running_loop()
                                asyncio.create_task(send_notification())
                            except RuntimeError:
                                # No running event loop, so create one
                                asyncio.run(send_notification())
                                
                    except Exception as e:
                        logger.warning(f"Failed to send recording_available WebSocket notification: {e}")
                else:
                    logger.warning(f"Stream {stream_id} not found for recording_path update")
                
            log_with_context(
                logger, 'info',
                f"MP4 remux completed for stream {stream_id}",
                task_id=payload.get('task_id'),
                stream_id=stream_id,
                mp4_output_path=mp4_output_path,
                operation='mp4_remux_complete'
            )
            # Persist
            try:
                with SessionLocal() as db:
                    rec_id = payload.get('recording_id')
                    if rec_id:
                        self._set_status(db, rec_id, stream_id, 'mp4_remux', 'completed')
            except Exception as persist_err:
                logger.debug(f"Could not persist mp4_remux status: {persist_err}")
            
        except Exception as e:
            log_with_context(
                logger, 'error',
                f"MP4 remux failed for stream {stream_id}: {e}",
                task_id=payload.get('task_id'),
                stream_id=stream_id,
                error=str(e),
                operation='mp4_remux_error'
            )
            try:
                with SessionLocal() as db:
                    rec_id = payload.get('recording_id')
                    if rec_id:
                        self._set_status(db, rec_id, stream_id, 'mp4_remux', 'failed', str(e))
            except Exception as persist_err:
                logger.debug(f"Could not persist mp4_remux failed status: {persist_err}")
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
            with SessionLocal() as db:
                rec_id = payload.get('recording_id')
                if rec_id:
                    self._set_status(db, rec_id, stream_id, 'thumbnail_generation', 'running')
        except Exception as e:
            logger.debug(f"thumbnail_generation: failed to mark running: {e}")
        
        try:
            # Generate unified thumbnail from MP4 (only creates -thumb.jpg format)
            thumbnail_path = await self.thumbnail_service.create_unified_thumbnail(
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
            # Persist
            try:
                with SessionLocal() as db:
                    rec_id = payload.get('recording_id')
                    if rec_id:
                        self._set_status(db, rec_id, stream_id, 'thumbnail_generation', 'completed')
            except Exception as persist_err:
                logger.debug(f"Could not persist thumbnail status: {persist_err}")
            
        except Exception as e:
            log_with_context(
                logger, 'error',
                f"Thumbnail generation failed for stream {stream_id}: {e}",
                task_id=payload.get('task_id'),
                stream_id=stream_id,
                error=str(e),
                operation='thumbnail_generation_error'
            )
            try:
                with SessionLocal() as db:
                    rec_id = payload.get('recording_id')
                    if rec_id:
                        self._set_status(db, rec_id, stream_id, 'thumbnail_generation', 'failed', str(e))
            except Exception as persist_err:
                logger.debug(f"Could not persist thumbnail failed status: {persist_err}")
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
            with SessionLocal() as db:
                rec_id = payload.get('recording_id')
                if rec_id:
                    self._set_status(db, rec_id, stream_id, 'mp4_validation', 'running')
        except Exception as e:
            logger.debug(f"mp4_validation: failed to mark running: {e}")
        
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
            try:
                with SessionLocal() as db:
                    rec_id = payload.get('recording_id')
                    if rec_id:
                        self._set_status(db, rec_id, stream_id, 'mp4_validation', 'completed')
            except Exception as persist_err:
                logger.debug(f"Could not persist mp4_validation status: {persist_err}")
            
        except Exception as e:
            log_with_context(
                logger, 'error',
                f"MP4 validation failed for stream {stream_id}: {e}",
                task_id=payload.get('task_id'),
                stream_id=stream_id,
                error=str(e),
                operation='mp4_validation_error'
            )
            try:
                with SessionLocal() as db:
                    rec_id = payload.get('recording_id')
                    if rec_id:
                        self._set_status(db, rec_id, stream_id, 'mp4_validation', 'failed', str(e))
            except Exception as persist_err:
                logger.debug(f"Could not persist mp4_validation failed status: {persist_err}")
            raise

    async def handle_cleanup(self, payload, progress_callback=None):
        """Handle cleanup task with intelligent TS cleanup or stream deletion cleanup"""
        stream_id = payload['stream_id']
        
        # Handle both post-processing cleanup and stream deletion cleanup
        if 'cleanup_paths' in payload:
            # Stream deletion cleanup - delete everything without validation
            files_to_remove = payload['cleanup_paths']
            mp4_path = None
            intelligent_cleanup = False
            is_deletion_cleanup = True
        else:
            # Post-processing cleanup - requires MP4 validation
            files_to_remove = payload.get('files_to_remove', [])
            mp4_path = payload['mp4_path']
            intelligent_cleanup = payload.get('intelligent_cleanup', False)
            is_deletion_cleanup = False
        
        max_wait_time = payload.get('max_wait_time', 300)  # 5 minutes default
        streamer_name = payload.get('streamer_name', f'stream_{stream_id}')
        
        # Validate that files_to_remove is a list
        if not isinstance(files_to_remove, list):
            logger.warning(f"files_to_remove is not a list: {type(files_to_remove)}, converting to list")
            files_to_remove = [files_to_remove] if files_to_remove else []
        
        # For post-processing cleanup, validate MP4 file exists early (fail fast)
        if not is_deletion_cleanup:
            if not mp4_path or not os.path.exists(mp4_path):
                raise Exception("MP4 file not found, not removing source files")
            
            mp4_size = os.path.getsize(mp4_path)
            if mp4_size < 1024 * 1024:  # Less than 1MB
                raise Exception(f"MP4 file too small ({mp4_size} bytes), not removing source files")
        
        log_with_context(
            logger, 'info',
            f"Starting {'deletion' if is_deletion_cleanup else 'post-processing'} cleanup for stream {stream_id}",
            task_id=payload.get('task_id'),
            stream_id=stream_id,
            files_to_remove=files_to_remove,
            intelligent_cleanup=intelligent_cleanup,
            operation='cleanup_start',
            streamer_name=streamer_name,
            is_deletion_cleanup=is_deletion_cleanup
        )
        try:
            if not is_deletion_cleanup:
                with SessionLocal() as db:
                    rec_id = payload.get('recording_id')
                    if rec_id:
                        self._set_status(db, rec_id, stream_id, 'cleanup', 'running')
        except Exception as e:
            logger.debug(f"cleanup: failed to mark running: {e}")
        
        # Log to structured logging service
        if self.logging_service:
            cleanup_type = "DELETION_CLEANUP" if is_deletion_cleanup else "POST_PROCESSING_CLEANUP"
            self.logging_service.log_recording_activity(
                f"{cleanup_type}_START",
                streamer_name,
                f"Cleaning up {len(files_to_remove)} files for stream {stream_id}"
            )
        
        try:
            removed_files = []
            for file_path in files_to_remove:
                if os.path.exists(file_path):
                    try:
                        logger.debug(f"🧹 CLEANUP_ATTEMPT: path={file_path} type={'dir' if os.path.isdir(file_path) else 'file'} intelligent={intelligent_cleanup and not is_deletion_cleanup}")
                        # Check if it's a directory
                        if os.path.isdir(file_path):
                            # Remove directory and all its contents
                            import shutil
                            shutil.rmtree(file_path)
                            logger.info(f"Removed directory: {file_path}")
                            removed_files.append(file_path)
                        else:
                            # Use intelligent cleanup for TS files if requested (only for post-processing cleanup)
                            if not is_deletion_cleanup and intelligent_cleanup and file_path.endswith('.ts'):
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
                else:
                    logger.debug(f"🧹 CLEANUP_SKIP_MISSING: path={file_path}")
            
            log_with_context(
                logger, 'info',
                f"{'Deletion' if is_deletion_cleanup else 'Post-processing'} cleanup completed for stream {stream_id}",
                task_id=payload.get('task_id'),
                stream_id=stream_id,
                removed_files=removed_files,
                operation='cleanup_complete',
                is_deletion_cleanup=is_deletion_cleanup
            )
            # Persist
            try:
                if not is_deletion_cleanup:
                    with SessionLocal() as db:
                        rec_id = payload.get('recording_id')
                        if rec_id:
                            self._set_status(db, rec_id, stream_id, 'cleanup', 'completed')
            except Exception as persist_err:
                logger.debug(f"Could not persist cleanup status: {persist_err}")
            
            # Trigger database event for orphaned recovery after cleanup completion (only for post-processing)
            if not is_deletion_cleanup:
                try:
                    from app.services.recording.database_event_orphaned_recovery import on_post_processing_completed
                    recording_id = payload.get('recording_id')
                    if recording_id:
                        await on_post_processing_completed(recording_id, "cleanup")
                except Exception as e:
                    logger.debug(f"Could not trigger database event for orphaned recovery: {e}")
                
        except Exception as e:
            log_with_context(
                logger, 'error',
                f"{'Deletion' if is_deletion_cleanup else 'Post-processing'} cleanup failed for stream {stream_id}: {e}",
                task_id=payload.get('task_id'),
                stream_id=stream_id,
                error=str(e),
                operation='cleanup_error',
                is_deletion_cleanup=is_deletion_cleanup
            )
            try:
                if not is_deletion_cleanup:
                    with SessionLocal() as db:
                        rec_id = payload.get('recording_id')
                        if rec_id:
                            self._set_status(db, rec_id, stream_id, 'cleanup', 'failed', str(e))
            except Exception as persist_err:
                logger.debug(f"Could not persist cleanup failed status: {persist_err}")
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

    # --- Helpers ---
    def _get_or_create_state(self, db, recording_id: int, stream_id: int):
        """Fetch or create RecordingProcessingState safely.
        Returns None if Stream is missing to avoid invalid FK values.
        """
        try:
            state = db.query(RecordingProcessingState).filter(RecordingProcessingState.recording_id == recording_id).first()
            if state:
                return state
            stream = db.query(Stream).get(stream_id)
            if not stream:
                logger.debug(f"_get_or_create_state: stream {stream_id} not found for recording {recording_id}")
                return None
            state = RecordingProcessingState(
                recording_id=recording_id,
                stream_id=stream_id,
                streamer_id=stream.streamer_id
            )
            db.add(state)
            return state
        except Exception as e:
            logger.debug(f"_get_or_create_state failed: {e}")
            return None

    def _set_status(self, db, recording_id: int, stream_id: int, step: str, status: str, last_error: str | None = None):
        """Set a specific step status with minimal duplication.
        step can be one of: metadata_generation|metadata, chapters_generation|chapters, mp4_remux,
        mp4_validation, thumbnail_generation|thumbnail, cleanup
        """
        try:
            state = self._get_or_create_state(db, recording_id, stream_id)
            if not state:
                return
            step_map = {
                'metadata_generation': 'metadata_status',
                'metadata': 'metadata_status',
                'chapters_generation': 'chapters_status',
                'chapters': 'chapters_status',
                'mp4_remux': 'mp4_remux_status',
                'mp4_validation': 'mp4_validation_status',
                'thumbnail_generation': 'thumbnail_status',
                'thumbnail': 'thumbnail_status',
                'cleanup': 'cleanup_status',
            }
            attr = step_map.get(step)
            if not attr:
                logger.debug(f"_set_status: unknown step '{step}' for recording {recording_id}")
                return
            setattr(state, attr, status)
            if last_error is not None:
                state.last_error = last_error
            db.commit()
            # Try to refresh updated_at set by DB trigger
            try:
                db.refresh(state)
            except Exception:
                pass
            # Broadcast snapshot to clients
            try:
                snapshot = self._status_snapshot(state)
                self._broadcast_processing_status(stream_id, snapshot)
            except Exception as be:
                logger.debug(f"_set_status broadcast failed for recording {recording_id}: {be}")
        except Exception as e:
            logger.debug(f"_set_status failed for recording {recording_id}, step {step}: {e}")

    def _status_snapshot(self, state: RecordingProcessingState) -> Dict[str, Any]:
        """Build a lightweight status snapshot for websocket updates."""
        try:
            updated_iso = None
            try:
                if getattr(state, 'updated_at', None):
                    updated_iso = state.updated_at.isoformat()
            except Exception:
                updated_iso = None
            return {
                'type': 'recording_processing_status',
                'data': {
                    'recording_id': state.recording_id,
                    'stream_id': state.stream_id,
                    'streamer_id': state.streamer_id,
                    'statuses': {
                        'metadata': state.metadata_status,
                        'chapters': state.chapters_status,
                        'mp4_remux': state.mp4_remux_status,
                        'mp4_validation': state.mp4_validation_status,
                        'thumbnail': state.thumbnail_status,
                        'cleanup': state.cleanup_status,
                    },
                    'last_error': state.last_error,
                    'updated_at': updated_iso,
                }
            }
        except Exception as e:
            logger.debug(f"_status_snapshot failed: {e}")
            return {
                'type': 'recording_processing_status',
                'data': {
                    'recording_id': getattr(state, 'recording_id', None),
                    'stream_id': getattr(state, 'stream_id', None),
                    'streamer_id': getattr(state, 'streamer_id', None),
                    'statuses': {},
                    'last_error': getattr(state, 'last_error', None),
                    'updated_at': None,
                }
            }

    def _broadcast_processing_status(self, stream_id: int, snapshot: Dict[str, Any]) -> None:
        """Best-effort broadcast with a short debounce per recording to reduce chatter."""
        try:
            if not websocket_manager:
                return
            rec_id = snapshot.get('data', {}).get('recording_id')
            if rec_id is None:
                # No debounce key; send immediately
                async def send_once():
                    await websocket_manager.send_message_to_all(snapshot)
                try:
                    loop = asyncio.get_running_loop()
                    asyncio.create_task(send_once())
                except RuntimeError:
                    pass
                return
            # Store/overwrite pending snapshot
            self._broadcast_debounce[rec_id] = snapshot
            async def delayed_send(recording_id: int):
                # small delay to coalesce rapid updates
                await asyncio.sleep(0.15)
                snap = self._broadcast_debounce.get(recording_id)
                if snap:
                    try:
                        await websocket_manager.send_message_to_all(snap)
                    finally:
                        # Clear after send
                        self._broadcast_debounce.pop(recording_id, None)
            try:
                loop = asyncio.get_running_loop()
                asyncio.create_task(delayed_send(rec_id))
            except RuntimeError:
                # No running loop; skip debounce
                async def send_fallback():
                    await websocket_manager.send_message_to_all(snapshot)
                try:
                    loop = asyncio.get_running_loop()
                    asyncio.create_task(send_fallback())
                except RuntimeError:
                    pass
        except Exception as e:
            logger.debug(f"_broadcast_processing_status failed for stream {stream_id}: {e}")

# Global instance
post_processing_task_handlers = PostProcessingTaskHandlers()
