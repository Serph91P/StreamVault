"""
Task handlers for post-processing tasks
Implements the actual task execution logic for different post-processing operations
"""

import asyncio
import logging
import os
import copy
from typing import TYPE_CHECKING
from collections.abc import Callable
from pathlib import Path

from cachetools import TTLCache

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.database import SessionLocal
from app.models import Stream, StreamMetadata, RecordingProcessingState, Recording
from app.services.processing.status_values import ProcessingStatus, RecordingAvailable
from app.utils.async_db_utils import run_in_thread_pool
from app.services.media.metadata_service import MetadataService
from app.services.media.thumbnail_service import ThumbnailService
from app.services.communication.websocket_manager import (
    ConnectionManager,
    websocket_manager,
)
from app.utils import ffmpeg_utils
from app.utils.structured_logging import log_with_context
from app.config.constants import CACHE_CONFIG, ASYNC_DELAYS

logger = logging.getLogger("streamvault")

if TYPE_CHECKING:
    from app.services.recording.unified_recovery_service import UnifiedRecoveryService


class PostProcessingTaskHandlers:
    """Collection of task handlers for post-processing operations"""

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session] | None = None,
        connection_manager: ConnectionManager | None = None,
        recovery_service_factory: Callable[[], "UnifiedRecoveryService"] | None = None,
    ):
        self._session_factory = session_factory
        self._recovery_service_factory = recovery_service_factory
        self.connection_manager = (
            connection_manager if connection_manager is not None else websocket_manager
        )
        self._broadcast_tasks: set[asyncio.Task[None]] = set()
        self._debounce_tasks: dict[int, asyncio.Task[None]] = {}
        self.metadata_service = MetadataService(session_factory=session_factory)
        self.thumbnail_service = ThumbnailService(session_factory=session_factory)
        # TTLCache for debouncing broadcasts (prevents memory leaks with automatic expiration)
        self._broadcast_debounce: TTLCache[int, ProcessingStatus] = TTLCache(
            maxsize=CACHE_CONFIG.SMALL_CACHE_SIZE,
            ttl=CACHE_CONFIG.BROADCAST_DEBOUNCE_TTL,
        )

        # Initialize logging service
        try:
            from app.services.system.logging_service import logging_service

            self.logging_service = logging_service
        except Exception as e:
            logger.warning(f"Could not initialize logging service: {e}")
            self.logging_service = None

    async def _check_stream_exists(
        self, stream_id: int, task_name: str, task_id: str | None = None
    ) -> tuple[bool, None]:
        """Check in a complete worker scope; never export a detached stream."""

        def work() -> bool:
            try:
                with self._sessions() as db:
                    exists = (
                        db.scalar(select(Stream.id).where(Stream.id == stream_id))
                        is not None
                    )
                if not exists:
                    log_with_context(
                        logger,
                        "warning",
                        f"Stream {stream_id} not found, skipping {task_name} (likely deleted during post-processing)",
                        task_id=task_id,
                        stream_id=stream_id,
                        operation=f"{task_name}_skip",
                    )
                return exists
            except Exception as e:
                logger.error(f"Error checking stream existence for {task_name}: {e}")
                return False

        return await run_in_thread_pool(work), None

    async def handle_metadata_generation(self, payload, progress_callback=None):
        """Handle metadata generation task"""
        # Deep copy payload to avoid accidental mutation across tasks
        local_payload = copy.deepcopy(payload)

        stream_id = local_payload["stream_id"]
        base_filename = local_payload["base_filename"]
        output_dir = local_payload["output_dir"]

        log_with_context(
            logger,
            "info",
            f"Starting metadata generation for stream {stream_id}",
            task_id=local_payload.get("task_id"),
            stream_id=stream_id,
            operation="metadata_generation_start",
        )

        # Check if stream still exists before processing
        exists, _ = await self._check_stream_exists(
            stream_id, "metadata_generation", local_payload.get("task_id")
        )
        if not exists:
            return {"status": "skipped", "reason": "stream_deleted"}

        # Mark running state (best-effort)
        try:
            await self._record_status(
                local_payload.get("recording_id"),
                stream_id,
                "metadata_generation",
                "running",
            )
        except Exception as e:
            logger.debug(f"metadata_generation: failed to mark running state: {e}")

        try:
            # Update progress
            if progress_callback:
                progress_callback(10.0)

            # Verify input parameters
            if not stream_id or not base_filename or not output_dir:
                raise ValueError(
                    f"Missing required parameters: stream_id={stream_id}, base_filename={base_filename}, output_dir={output_dir}"
                )

            # Normalize base filename (strip common extensions if provided)
            if base_filename.lower().endswith((".mp4", ".ts", ".mkv")):
                base_filename = Path(base_filename).stem

            # If possible, correct output_dir and base_filename from the authoritative recording_path
            try:
                with self._sessions() as db:
                    stream = db.query(Stream).filter(Stream.id == stream_id).first()
                    if stream and getattr(stream, "recording_path", None):
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
                logger.debug(
                    f"Could not correct metadata generation paths from recording_path: {corr_err}"
                )

            # Check if output directory exists
            output_path = Path(output_dir)
            if not output_path.exists():
                log_with_context(
                    logger,
                    "warning",
                    f"Output directory does not exist, creating: {output_dir}",
                    stream_id=stream_id,
                    operation="metadata_generation_dir_create",
                )
                output_path.mkdir(parents=True, exist_ok=True)

            if progress_callback:
                progress_callback(20.0)

            # Generate metadata using metadata service
            try:
                success = await self.metadata_service.generate_metadata_for_stream(
                    stream_id=stream_id,
                    base_path=output_dir,
                    base_filename=base_filename,
                )

                if not success:
                    log_with_context(
                        logger,
                        "warning",
                        f"Metadata generation returned False for stream {stream_id} - continuing with post-processing",
                        task_id=local_payload.get("task_id"),
                        stream_id=stream_id,
                        operation="metadata_generation_warning",
                    )
                else:
                    log_with_context(
                        logger,
                        "info",
                        f"Metadata generation completed successfully for stream {stream_id}",
                        task_id=local_payload.get("task_id"),
                        stream_id=stream_id,
                        operation="metadata_generation_complete",
                    )
            except Exception as metadata_error:
                log_with_context(
                    logger,
                    "warning",
                    f"Metadata generation failed for stream {stream_id}: {metadata_error} - continuing with post-processing",
                    task_id=local_payload.get("task_id"),
                    stream_id=stream_id,
                    error=str(metadata_error),
                    operation="metadata_generation_error_continue",
                )

            # Persist processing state
            try:
                await self._record_status(
                    payload.get("recording_id"),
                    stream_id,
                    "metadata_generation",
                    "completed",
                )
            except Exception as persist_err:
                logger.debug(f"Could not persist metadata status: {persist_err}")

            if progress_callback:
                progress_callback(90.0)

            if progress_callback:
                progress_callback(100.0)

        except Exception as e:
            # Log any unexpected errors in the metadata generation task
            log_with_context(
                logger,
                "error",
                f"Unexpected error in metadata generation task for stream {stream_id}: {e}",
                task_id=local_payload.get("task_id"),
                stream_id=stream_id,
                error=str(e),
                operation="metadata_generation_unexpected_error",
            )
            # Don't raise - metadata generation failures shouldn't stop post-processing
            # The specific metadata errors are already handled in the try-catch above
            try:
                await self._record_status(
                    payload.get("recording_id"),
                    payload.get("stream_id"),
                    "metadata_generation",
                    "failed",
                    str(e),
                )
            except Exception as persist_err:
                logger.debug(f"Could not persist metadata failed status: {persist_err}")

    async def handle_chapters_generation(self, payload, progress_callback=None):
        """Handle chapters generation task"""
        stream_id = payload["stream_id"]
        mp4_path = payload["mp4_path"]

        log_with_context(
            logger,
            "info",
            f"Starting chapters generation for stream {stream_id}",
            task_id=payload.get("task_id"),
            stream_id=stream_id,
            operation="chapters_generation_start",
        )

        # Check if stream still exists before processing
        exists, _ = await self._check_stream_exists(
            stream_id, "chapters_generation", payload.get("task_id")
        )
        if not exists:
            return {"status": "skipped", "reason": "stream_deleted"}

        try:
            await self._record_status(
                payload.get("recording_id"), stream_id, "chapters_generation", "running"
            )
        except Exception as e:
            logger.debug(f"chapters_generation: failed to mark running: {e}")

        try:
            # Generate chapters using metadata service
            chapter_info = await self.metadata_service.ensure_all_chapter_formats(
                stream_id=stream_id, mp4_path=mp4_path
            )

            if not chapter_info:
                raise Exception("Chapters generation failed")

            log_with_context(
                logger,
                "info",
                f"Chapters generation completed for stream {stream_id}",
                task_id=payload.get("task_id"),
                stream_id=stream_id,
                chapter_formats=list(chapter_info.keys()),
                operation="chapters_generation_complete",
            )
            # Persist
            try:
                await self._record_status(
                    payload.get("recording_id"),
                    payload.get("stream_id"),
                    "chapters_generation",
                    "completed",
                )
            except Exception as persist_err:
                logger.debug(f"Could not persist chapters status: {persist_err}")

        except Exception as e:
            log_with_context(
                logger,
                "error",
                f"Chapters generation failed for stream {stream_id}: {e}",
                task_id=payload.get("task_id"),
                stream_id=stream_id,
                error=str(e),
                operation="chapters_generation_error",
            )
            # Persist failure
            try:
                await self._record_status(
                    payload.get("recording_id"),
                    payload.get("stream_id"),
                    "chapters_generation",
                    "failed",
                    str(e),
                )
            except Exception as persist_err:
                logger.debug(f"Could not persist chapters failed status: {persist_err}")
            raise

    def _load_remux_inputs(
        self, stream_id: int, ts_file_path: str, streamer_name: str
    ) -> tuple[dict[str, str | None], list[dict[str, str | float]] | None]:
        if not os.path.exists(ts_file_path):
            raise Exception(f"TS file not found: {ts_file_path}")
        with self._sessions() as db:
            stream = db.query(Stream).filter(Stream.id == stream_id).first()
            if not stream:
                raise Exception(f"Stream {stream_id} not found")
            metadata = (
                db.query(StreamMetadata)
                .filter(StreamMetadata.stream_id == stream_id)
                .first()
            )
            metadata_dict = {
                "title": stream.title or f"{streamer_name} Stream",
                "artist": streamer_name,
                "date": stream.started_at.strftime("%Y-%m-%d")
                if stream.started_at
                else None,
                "creation_time": stream.started_at.isoformat()
                if stream.started_at
                else None,
                "comment": f"Stream by {streamer_name}",
                "genre": stream.category_name or "Livestream",
            }
            chapters: list[dict[str, str | float]] | None = None
            if metadata and metadata.chapters_ffmpeg_path:
                try:
                    import re

                    chapters_list: list[dict[str, str | float]] = []
                    if os.path.exists(metadata.chapters_ffmpeg_path):
                        with open(
                            metadata.chapters_ffmpeg_path, "r", encoding="utf-8"
                        ) as file:
                            content = file.read()
                        for block in re.split(r"\n\[CHAPTER\]\n", content)[1:]:
                            chapter_data = {}
                            for line in block.strip().split("\n"):
                                if "=" in line:
                                    key, value = line.split("=", 1)
                                    chapter_data[key] = value
                            if {"START", "END", "title"} <= chapter_data.keys():
                                chapters_list.append(
                                    {
                                        "start_time": int(chapter_data["START"])
                                        / 1000.0,
                                        "end_time": int(chapter_data["END"]) / 1000.0,
                                        "title": chapter_data["title"],
                                    }
                                )
                        if chapters_list:
                            chapters = chapters_list
                            logger.info(
                                "Loaded %s chapters for embedding", len(chapters_list)
                            )
                except Exception as error:
                    logger.warning(
                        "Failed to load chapters from %s: %s",
                        metadata.chapters_ffmpeg_path,
                        error,
                    )
            return metadata_dict, chapters

    def _finish_remux(
        self, stream_id: int, output_path: str
    ) -> RecordingAvailable | None:
        with self._sessions() as db:
            stream = (
                db.query(Stream)
                .options(joinedload(Stream.streamer))
                .filter(Stream.id == stream_id)
                .first()
            )
            if stream is None:
                logger.warning(
                    "Stream %s not found for recording_path update", stream_id
                )
                return None
            old_path = stream.recording_path
            stream.recording_path = output_path
            streamer = stream.streamer
            notification: RecordingAvailable | None = None
            if streamer is not None:
                notification = {
                    "type": "recording_available",
                    "data": {
                        "stream_id": stream_id,
                        "streamer_id": stream.streamer_id,
                        "streamer_name": streamer.username,
                        "recording_path": output_path,
                        "title": stream.title,
                    },
                }
            db.commit()
            logger.info(
                "Updated Stream.recording_path for stream %s: %s -> %s",
                stream_id,
                old_path,
                output_path,
            )
        return notification

    async def handle_mp4_remux(self, payload, progress_callback=None):
        """Handle MP4 remux task"""
        stream_id = payload["stream_id"]
        ts_file_path = payload["ts_file_path"]
        mp4_output_path = payload["mp4_output_path"]
        streamer_name = payload["streamer_name"]

        log_with_context(
            logger,
            "info",
            f"Starting MP4 remux for stream {stream_id}",
            task_id=payload.get("task_id"),
            stream_id=stream_id,
            ts_file_path=ts_file_path,
            mp4_output_path=mp4_output_path,
            operation="mp4_remux_start",
            streamer_name=streamer_name,
        )

        # Check if stream still exists before processing
        exists, _ = await self._check_stream_exists(
            stream_id, "mp4_remux", payload.get("task_id")
        )
        if not exists:
            return {"status": "skipped", "reason": "stream_deleted"}

        try:
            await self._record_status(
                payload.get("recording_id"), stream_id, "mp4_remux", "running"
            )
        except Exception as e:
            logger.debug(f"mp4_remux: failed to mark running: {e}")

        # Log to structured logging service
        if self.logging_service:
            await run_in_thread_pool(
                self.logging_service.log_recording_activity,
                "MP4_REMUX_START",
                streamer_name,
                f"Remuxing {ts_file_path} to {mp4_output_path}",
            )

        try:
            metadata_dict, chapters = await run_in_thread_pool(
                self._load_remux_inputs, stream_id, ts_file_path, streamer_name
            )

            # Convert TS to MP4 with metadata
            result = await ffmpeg_utils.embed_metadata_with_ffmpeg_wrapper(
                input_path=ts_file_path,
                output_path=mp4_output_path,
                metadata=metadata_dict,
                chapters=chapters,
                streamer_name=streamer_name,
                logging_service=self.logging_service,
                overwrite=payload.get("overwrite", False),
            )

            if not result.get("success"):
                raise Exception(
                    f"MP4 remux failed: {result.get('stderr', 'Unknown error')}"
                )

            # Validate MP4 file
            if not await ffmpeg_utils.validate_mp4(mp4_output_path):
                raise Exception("MP4 validation failed")

            notification = await run_in_thread_pool(
                self._finish_remux, stream_id, mp4_output_path
            )
            if notification is not None:
                try:
                    await self.connection_manager.send_notification(dict(notification))
                except Exception as error:
                    logger.warning(
                        "Failed to send recording_available WebSocket notification: %s",
                        error,
                    )

            log_with_context(
                logger,
                "info",
                f"MP4 remux completed for stream {stream_id}",
                task_id=payload.get("task_id"),
                stream_id=stream_id,
                mp4_output_path=mp4_output_path,
                operation="mp4_remux_complete",
            )
            # Persist
            try:
                await self._record_status(
                    payload.get("recording_id"), stream_id, "mp4_remux", "completed"
                )
            except Exception as persist_err:
                logger.debug(f"Could not persist mp4_remux status: {persist_err}")

        except Exception as e:
            log_with_context(
                logger,
                "error",
                f"MP4 remux failed for stream {stream_id}: {e}",
                task_id=payload.get("task_id"),
                stream_id=stream_id,
                error=str(e),
                operation="mp4_remux_error",
            )
            try:
                await self._record_status(
                    payload.get("recording_id"),
                    stream_id,
                    "mp4_remux",
                    "failed",
                    str(e),
                )
            except Exception as persist_err:
                logger.debug(
                    f"Could not persist mp4_remux failed status: {persist_err}"
                )
            raise

    async def handle_thumbnail_generation(self, payload, progress_callback=None):
        """Handle thumbnail generation task"""
        stream_id = payload["stream_id"]
        mp4_path = payload["mp4_path"]

        log_with_context(
            logger,
            "info",
            f"Starting thumbnail generation for stream {stream_id}",
            task_id=payload.get("task_id"),
            stream_id=stream_id,
            mp4_path=mp4_path,
            operation="thumbnail_generation_start",
        )

        # Check if stream still exists before processing
        exists, _ = await self._check_stream_exists(
            stream_id, "thumbnail_generation", payload.get("task_id")
        )
        if not exists:
            return {"status": "skipped", "reason": "stream_deleted"}
        try:
            await self._record_status(
                payload.get("recording_id"),
                stream_id,
                "thumbnail_generation",
                "running",
            )
        except Exception as e:
            logger.debug(f"thumbnail_generation: failed to mark running: {e}")

        try:
            # Generate unified thumbnail from MP4 (only creates -thumb.jpg format)
            thumbnail_path = await self.thumbnail_service.create_unified_thumbnail(
                stream_id=stream_id, mp4_path=mp4_path
            )

            if not thumbnail_path:
                raise Exception("Thumbnail generation failed")

            log_with_context(
                logger,
                "info",
                f"Thumbnail generation completed for stream {stream_id}",
                task_id=payload.get("task_id"),
                stream_id=stream_id,
                thumbnail_path=thumbnail_path,
                operation="thumbnail_generation_complete",
            )
            # Persist
            try:
                await self._record_status(
                    payload.get("recording_id"),
                    stream_id,
                    "thumbnail_generation",
                    "completed",
                )
            except Exception as persist_err:
                logger.debug(f"Could not persist thumbnail status: {persist_err}")

        except Exception as e:
            log_with_context(
                logger,
                "error",
                f"Thumbnail generation failed for stream {stream_id}: {e}",
                task_id=payload.get("task_id"),
                stream_id=stream_id,
                error=str(e),
                operation="thumbnail_generation_error",
            )
            try:
                await self._record_status(
                    payload.get("recording_id"),
                    stream_id,
                    "thumbnail_generation",
                    "failed",
                    str(e),
                )
            except Exception as persist_err:
                logger.debug(
                    f"Could not persist thumbnail failed status: {persist_err}"
                )
            raise

    async def handle_mp4_validation(self, payload, progress_callback=None):
        """Handle MP4 validation task"""
        stream_id = payload["stream_id"]
        mp4_path = payload["mp4_path"]
        ts_file_path = payload["ts_file_path"]
        validate_size_ratio = payload.get("validate_size_ratio", True)
        min_size_mb = payload.get("min_size_mb", 1)

        log_with_context(
            logger,
            "info",
            f"Starting MP4 validation for stream {stream_id}",
            task_id=payload.get("task_id"),
            stream_id=stream_id,
            mp4_path=mp4_path,
            operation="mp4_validation_start",
        )

        # Check if stream still exists before processing
        exists, _ = await self._check_stream_exists(
            stream_id, "mp4_validation", payload.get("task_id")
        )
        if not exists:
            return {"status": "skipped", "reason": "stream_deleted"}

        try:
            await self._record_status(
                payload.get("recording_id"), stream_id, "mp4_validation", "running"
            )
        except Exception as e:
            logger.debug(f"mp4_validation: failed to mark running: {e}")

        try:

            def checked_file_size() -> int:
                if not os.path.exists(mp4_path):
                    raise Exception(f"MP4 file not found: {mp4_path}")

                mp4_size = os.path.getsize(mp4_path)
                min_size_bytes = min_size_mb * 1024 * 1024
                if mp4_size < min_size_bytes:
                    raise Exception(
                        f"MP4 file too small: {mp4_size} bytes (minimum: {min_size_bytes} bytes)"
                    )

                if validate_size_ratio and os.path.exists(ts_file_path):
                    ts_size = os.path.getsize(ts_file_path)
                    if ts_size > 0:
                        size_ratio = mp4_size / ts_size
                        if size_ratio < 0.7:
                            raise Exception(
                                f"MP4 file too small compared to TS - Ratio: {size_ratio:.2f}"
                            )
                        elif size_ratio > 1.1:
                            logger.warning(
                                f"MP4 file larger than TS - Ratio: {size_ratio:.2f} (this is usually okay)"
                            )
                return mp4_size

            mp4_size = await run_in_thread_pool(checked_file_size)

            # Use FFmpeg utils validation
            is_valid = await ffmpeg_utils.validate_mp4(mp4_path)
            if not is_valid:
                raise Exception("MP4 validation failed - file may be corrupted")

            log_with_context(
                logger,
                "info",
                f"MP4 validation completed for stream {stream_id}",
                task_id=payload.get("task_id"),
                stream_id=stream_id,
                mp4_size=mp4_size,
                operation="mp4_validation_complete",
            )
            try:
                await self._record_status(
                    payload.get("recording_id"),
                    stream_id,
                    "mp4_validation",
                    "completed",
                )
            except Exception as persist_err:
                logger.debug(f"Could not persist mp4_validation status: {persist_err}")

        except Exception as e:
            log_with_context(
                logger,
                "error",
                f"MP4 validation failed for stream {stream_id}: {e}",
                task_id=payload.get("task_id"),
                stream_id=stream_id,
                error=str(e),
                operation="mp4_validation_error",
            )
            try:
                await self._record_status(
                    payload.get("recording_id"),
                    stream_id,
                    "mp4_validation",
                    "failed",
                    str(e),
                )
            except Exception as persist_err:
                logger.debug(
                    f"Could not persist mp4_validation failed status: {persist_err}"
                )
            raise

    @staticmethod
    def _validate_cleanup_output(mp4_path: str | None) -> None:
        if not mp4_path or not os.path.exists(mp4_path):
            raise Exception("MP4 file not found, not removing source files")
        mp4_size = os.path.getsize(mp4_path)
        if mp4_size < 1024 * 1024:
            raise Exception(
                f"MP4 file too small ({mp4_size} bytes), not removing source files"
            )

    def _persist_removed_segments(self, stream_id: int, segments_path: str) -> None:
        with self._sessions() as db:
            metadata = (
                db.query(StreamMetadata)
                .filter(StreamMetadata.stream_id == stream_id)
                .first()
            )
            if metadata is None:
                metadata = StreamMetadata(stream_id=stream_id)
                db.add(metadata)
            if hasattr(metadata, "segments_dir_path"):
                metadata.segments_dir_path = segments_path
            if hasattr(metadata, "segments_removed"):
                metadata.segments_removed = True
            db.commit()
            logger.debug(
                "Updated StreamMetadata for stream %s: segments_removed=True, segments_dir_path=%s",
                stream_id,
                segments_path,
            )

    async def handle_cleanup(self, payload, progress_callback=None):
        """Handle cleanup task with intelligent TS cleanup or stream deletion cleanup"""
        stream_id = payload["stream_id"]

        # Handle both post-processing cleanup and stream deletion cleanup
        if "cleanup_paths" in payload:
            # Stream deletion cleanup - delete everything without validation
            files_to_remove = payload["cleanup_paths"]
            mp4_path = None
            intelligent_cleanup = False
            is_deletion_cleanup = True
        else:
            # Post-processing cleanup - requires MP4 validation
            files_to_remove = payload.get("files_to_remove", [])
            mp4_path = payload["mp4_path"]
            intelligent_cleanup = payload.get("intelligent_cleanup", False)
            is_deletion_cleanup = False

        max_wait_time = payload.get("max_wait_time", 300)  # 5 minutes default
        streamer_name = payload.get("streamer_name", f"stream_{stream_id}")

        # Validate that files_to_remove is a list
        if not isinstance(files_to_remove, list):
            logger.warning(
                f"files_to_remove is not a list: {type(files_to_remove)}, converting to list"
            )
            files_to_remove = [files_to_remove] if files_to_remove else []

        # For post-processing cleanup, validate MP4 file exists early (fail fast)
        if not is_deletion_cleanup:
            await run_in_thread_pool(self._validate_cleanup_output, mp4_path)

        log_with_context(
            logger,
            "info",
            f"Starting {'deletion' if is_deletion_cleanup else 'post-processing'} cleanup for stream {stream_id}",
            task_id=payload.get("task_id"),
            stream_id=stream_id,
            files_to_remove=files_to_remove,
            intelligent_cleanup=intelligent_cleanup,
            operation="cleanup_start",
            streamer_name=streamer_name,
            is_deletion_cleanup=is_deletion_cleanup,
        )
        try:
            if not is_deletion_cleanup:
                await self._record_status(
                    payload.get("recording_id"), stream_id, "cleanup", "running"
                )
        except Exception as e:
            logger.debug(f"cleanup: failed to mark running: {e}")

        # Log to structured logging service
        if self.logging_service:
            cleanup_type = (
                "DELETION_CLEANUP" if is_deletion_cleanup else "POST_PROCESSING_CLEANUP"
            )
            await run_in_thread_pool(
                self.logging_service.log_recording_activity,
                f"{cleanup_type}_START",
                streamer_name,
                f"Cleaning up {len(files_to_remove)} files for stream {stream_id}",
            )

        try:
            removed_files = []
            segments_dirs_removed = []
            for file_path in files_to_remove:
                if await run_in_thread_pool(os.path.exists, file_path):
                    try:
                        is_directory = await run_in_thread_pool(
                            os.path.isdir, file_path
                        )
                        logger.debug(
                            f"🧹 CLEANUP_ATTEMPT: path={file_path} type={'dir' if is_directory else 'file'} intelligent={intelligent_cleanup and not is_deletion_cleanup}"
                        )
                        # Check if it's a directory
                        if is_directory:
                            # Track segments directories for DB update
                            if file_path.endswith("_segments"):
                                segments_dirs_removed.append(file_path)
                            # Remove directory and all its contents
                            import shutil

                            await run_in_thread_pool(shutil.rmtree, file_path)
                            logger.info(f"Removed directory: {file_path}")
                            removed_files.append(file_path)
                        else:
                            # Use intelligent cleanup for TS files if requested (only for post-processing cleanup)
                            if (
                                not is_deletion_cleanup
                                and intelligent_cleanup
                                and file_path.endswith(".ts")
                            ):
                                cleanup_success = await self._intelligent_ts_cleanup(
                                    file_path, mp4_path, max_wait_time
                                )
                                if cleanup_success:
                                    removed_files.append(file_path)
                                else:
                                    logger.warning(
                                        f"Intelligent cleanup failed for {file_path}, keeping file"
                                    )
                            else:
                                # Simple file removal
                                await run_in_thread_pool(os.remove, file_path)
                                logger.info(f"Removed file: {file_path}")
                                removed_files.append(file_path)
                    except Exception as e:
                        logger.warning(f"Failed to remove {file_path}: {e}")
                else:
                    logger.debug(f"🧹 CLEANUP_SKIP_MISSING: path={file_path}")

            # Update StreamMetadata with segments directory tracking
            if segments_dirs_removed and not is_deletion_cleanup:
                try:
                    await run_in_thread_pool(
                        self._persist_removed_segments,
                        stream_id,
                        segments_dirs_removed[0],
                    )
                except Exception as meta_err:
                    logger.debug(
                        f"Could not update StreamMetadata with segments info: {meta_err}"
                    )

            log_with_context(
                logger,
                "info",
                f"{'Deletion' if is_deletion_cleanup else 'Post-processing'} cleanup completed for stream {stream_id}",
                task_id=payload.get("task_id"),
                stream_id=stream_id,
                removed_files=removed_files,
                operation="cleanup_complete",
                is_deletion_cleanup=is_deletion_cleanup,
            )
            # Persist
            try:
                if not is_deletion_cleanup:
                    await self._record_status(
                        payload.get("recording_id"), stream_id, "cleanup", "completed"
                    )
            except Exception as persist_err:
                logger.debug(f"Could not persist cleanup status: {persist_err}")

            # Trigger database event for orphaned recovery after cleanup completion (only for post-processing)
            if not is_deletion_cleanup:
                try:
                    from app.services.recording.database_event_orphaned_recovery import (
                        on_post_processing_completed,
                    )

                    recording_id = payload.get("recording_id")
                    if recording_id:
                        await on_post_processing_completed(recording_id, "cleanup")
                except Exception as e:
                    logger.debug(
                        f"Could not trigger database event for orphaned recovery: {e}"
                    )

        except Exception as e:
            log_with_context(
                logger,
                "error",
                f"{'Deletion' if is_deletion_cleanup else 'Post-processing'} cleanup failed for stream {stream_id}: {e}",
                task_id=payload.get("task_id"),
                stream_id=stream_id,
                error=str(e),
                operation="cleanup_error",
                is_deletion_cleanup=is_deletion_cleanup,
            )
            try:
                if not is_deletion_cleanup:
                    await self._record_status(
                        payload.get("recording_id"),
                        stream_id,
                        "cleanup",
                        "failed",
                        str(e),
                    )
            except Exception as persist_err:
                logger.debug(f"Could not persist cleanup failed status: {persist_err}")
            raise

    async def _intelligent_ts_cleanup(
        self, ts_path: str, mp4_path: str, max_wait_time: int
    ):
        """Intelligent TS cleanup that waits for processes to finish"""
        try:
            # Use the intelligent cleanup from file_operations
            from app.services.recording.file_operations import intelligent_ts_cleanup

            # Check if psutil is available for process monitoring
            psutil_available = False
            try:
                psutil_available = True
            except ImportError:
                pass

            # Run intelligent cleanup
            return await intelligent_ts_cleanup(
                ts_path, max_wait_time, psutil_available
            )

        except Exception as e:
            # Fallback to simple removal if intelligent cleanup fails
            logger.warning(
                f"Intelligent cleanup failed, falling back to simple removal: {e}"
            )
            if await run_in_thread_pool(os.path.exists, ts_path):
                await run_in_thread_pool(os.remove, ts_path)
                return True

    async def handle_unified_recovery(self, payload, progress_callback=None):
        """Handle unified recovery scan task - runs in background to prevent frontend blocking"""
        max_age_hours = payload.get("max_age_hours", 72)
        dry_run = payload.get("dry_run", False)

        log_with_context(
            logger,
            "info",
            f"Starting unified recovery scan (max_age={max_age_hours}h, dry_run={dry_run})",
            task_id=payload.get("task_id"),
            operation="unified_recovery_start",
        )

        try:
            from app.services.recording.unified_recovery_service import (
                get_unified_recovery_service,
            )

            recovery_service = (
                await run_in_thread_pool(self._recovery_service_factory)
                if self._recovery_service_factory is not None
                else await get_unified_recovery_service()
            )

            # Run comprehensive recovery scan
            stats = await recovery_service.comprehensive_recovery_scan(
                max_age_hours=max_age_hours, dry_run=dry_run
            )

            log_with_context(
                logger,
                "info",
                f"Unified recovery completed: orphaned={stats.orphaned_segments}, "
                f"failed_pp={stats.failed_post_processing}, recovered={stats.recovered_recordings}, "
                f"triggered_pp={stats.triggered_post_processing}, size={stats.total_size_gb:.1f}GB",
                task_id=payload.get("task_id"),
                operation="unified_recovery_complete",
                stats=vars(stats),
            )

        except Exception as e:
            log_with_context(
                logger,
                "error",
                f"Unified recovery scan failed: {e}",
                task_id=payload.get("task_id"),
                error=str(e),
                operation="unified_recovery_error",
            )
            # Let the existing queue retry/failure channel own the outcome.
            raise

    async def cleanup(self):
        """Clean up services"""
        tasks = list(self._broadcast_tasks)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self._broadcast_tasks.clear()
        self._debounce_tasks.clear()
        self._broadcast_debounce.clear()
        await self.metadata_service.close()
        await self.thumbnail_service.close()

    # --- Helpers ---
    def _sessions(self) -> Session:
        return (self._session_factory or SessionLocal)()

    async def _record_status(
        self,
        recording_id: int | None,
        stream_id: int | None,
        step: str,
        status: str,
        last_error: str | None = None,
    ) -> None:
        if not recording_id or not stream_id:
            return

        def work() -> ProcessingStatus | None:
            with self._sessions() as db:
                if db.get_bind().dialect.name == "sqlite":
                    db.connection().exec_driver_sql("BEGIN IMMEDIATE")
                else:
                    db.scalar(
                        select(Recording.id)
                        .where(Recording.id == recording_id)
                        .with_for_update()
                    )
                return self._set_status(
                    db, recording_id, stream_id, step, status, last_error
                )

        snapshot = await run_in_thread_pool(work)
        if snapshot is not None:
            self._broadcast_processing_status(stream_id, snapshot)

    def _get_or_create_state(
        self, db: Session, recording_id: int, stream_id: int
    ) -> RecordingProcessingState | None:
        """Fetch or create RecordingProcessingState safely.
        Returns None if Stream is missing to avoid invalid FK values.
        """
        try:
            state = (
                db.query(RecordingProcessingState)
                .filter(RecordingProcessingState.recording_id == recording_id)
                .first()
            )
            if state:
                return state
            stream = db.get(Stream, stream_id)
            if not stream:
                logger.debug(
                    f"_get_or_create_state: stream {stream_id} not found for recording {recording_id}"
                )
                return None
            state = RecordingProcessingState(
                recording_id=recording_id,
                stream_id=stream_id,
                streamer_id=stream.streamer_id,
            )
            db.add(state)
            return state
        except Exception as e:
            logger.debug(f"_get_or_create_state failed: {e}")
            return None

    def _set_status(
        self,
        db: Session,
        recording_id: int,
        stream_id: int,
        step: str,
        status: str,
        last_error: str | None = None,
    ) -> ProcessingStatus | None:
        """Set a specific step status with minimal duplication.
        step can be one of: metadata_generation|metadata, chapters_generation|chapters, mp4_remux,
        mp4_validation, thumbnail_generation|thumbnail, cleanup
        """
        try:
            state = self._get_or_create_state(db, recording_id, stream_id)
            if not state:
                return
            step_map = {
                "metadata_generation": "metadata_status",
                "metadata": "metadata_status",
                "chapters_generation": "chapters_status",
                "chapters": "chapters_status",
                "mp4_remux": "mp4_remux_status",
                "mp4_validation": "mp4_validation_status",
                "thumbnail_generation": "thumbnail_status",
                "thumbnail": "thumbnail_status",
                "cleanup": "cleanup_status",
            }
            attr = step_map.get(step)
            if not attr:
                logger.debug(
                    f"_set_status: unknown step '{step}' for recording {recording_id}"
                )
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
                return self._status_snapshot(state)
            except Exception as be:
                logger.debug(
                    f"_set_status broadcast failed for recording {recording_id}: {be}"
                )
        except Exception as e:
            logger.debug(
                f"_set_status failed for recording {recording_id}, step {step}: {e}"
            )
        return None

    def _status_snapshot(self, state: RecordingProcessingState) -> ProcessingStatus:
        """Build a lightweight status snapshot for websocket updates."""
        try:
            updated_iso = None
            try:
                if getattr(state, "updated_at", None):
                    updated_iso = state.updated_at.isoformat()
            except Exception:
                updated_iso = None
            return {
                "type": "recording_processing_status",
                "data": {
                    "recording_id": state.recording_id,
                    "stream_id": state.stream_id,
                    "streamer_id": state.streamer_id,
                    "statuses": {
                        "metadata": state.metadata_status,
                        "chapters": state.chapters_status,
                        "mp4_remux": state.mp4_remux_status,
                        "mp4_validation": state.mp4_validation_status,
                        "thumbnail": state.thumbnail_status,
                        "cleanup": state.cleanup_status,
                    },
                    "last_error": state.last_error,
                    "updated_at": updated_iso,
                },
            }
        except Exception as e:
            logger.debug(f"_status_snapshot failed: {e}")
            return {
                "type": "recording_processing_status",
                "data": {
                    "recording_id": getattr(state, "recording_id", None),
                    "stream_id": getattr(state, "stream_id", None),
                    "streamer_id": getattr(state, "streamer_id", None),
                    "statuses": {},
                    "last_error": getattr(state, "last_error", None),
                    "updated_at": None,
                },
            }

    def _broadcast_processing_status(
        self, stream_id: int, snapshot: ProcessingStatus
    ) -> None:
        """Coalesce per-recording updates; retain producer ownership until cleanup."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        recording_id = snapshot["data"]["recording_id"]

        async def emit(value: ProcessingStatus) -> None:
            await self.connection_manager.send_notification(dict(value))

        if recording_id is None:
            coroutine = emit(snapshot)
        else:
            self._broadcast_debounce[recording_id] = snapshot
            previous = self._debounce_tasks.get(recording_id)
            if previous is not None and not previous.done():
                return

            async def delayed_send() -> None:
                while True:
                    await asyncio.sleep(ASYNC_DELAYS.POST_PROCESSING_DELAY)
                    value = self._broadcast_debounce.pop(recording_id, None)
                    if value is None:
                        return
                    await emit(value)
                    if recording_id not in self._broadcast_debounce:
                        return

            coroutine = delayed_send()
        task = loop.create_task(coroutine, name="streamvault:processing-status")
        self._broadcast_tasks.add(task)
        if recording_id is not None:
            self._debounce_tasks[recording_id] = task

        def finished(completed: asyncio.Task[None]) -> None:
            self._broadcast_tasks.discard(completed)
            if (
                recording_id is not None
                and self._debounce_tasks.get(recording_id) is completed
            ):
                self._debounce_tasks.pop(recording_id, None)
            if not completed.cancelled():
                error = completed.exception()
                if error is not None:
                    logger.debug(
                        "Processing status delivery failed for stream %s (%s)",
                        stream_id,
                        type(error).__name__,
                    )

        task.add_done_callback(finished)


# Global instance
post_processing_task_handlers = PostProcessingTaskHandlers()
