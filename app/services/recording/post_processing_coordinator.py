"""
PostProcessingCoordinator - File processing and post-processing workflows

Extracted from recording_service.py ULTRA-BOSS (1084 lines)
Handles post-processing coordination, file validation, and metadata generation.
"""

import logging
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from app.utils import async_file
from app.utils.ffmpeg_utils import validate_mp4
from app.services.init.background_queue_init import enqueue_recording_post_processing

logger = logging.getLogger("streamvault")


class PostProcessingCoordinator:
    """Coordinates post-processing workflows for recordings"""

    def __init__(self, config_manager=None, websocket_service=None):
        self.config_manager = config_manager
        self.websocket_service = websocket_service

    async def enqueue_post_processing(
        self, recording_id: int, ts_file_path: str, recording_data: Dict[str, Any]
    ) -> bool:
        """Enqueue post-processing tasks for a completed recording"""
        try:
            logger.info(f"Enqueueing post-processing for recording {recording_id}")

            # Prepare post-processing payload
            payload = {
                "recording_id": recording_id,
                "ts_file_path": ts_file_path,
                "streamer_id": recording_data.get("streamer_id"),
                "stream_id": recording_data.get("stream_id"),
                "started_at": recording_data.get("started_at"),
                "metadata": recording_data.get("metadata", {}),
            }

            # Enqueue post-processing task
            await enqueue_recording_post_processing(payload)

            # Send WebSocket update
            if self.websocket_service:
                await self.websocket_service.send_recording_job_update(
                    recording_id=recording_id, job_type="post_processing", status="queued", progress=0.0
                )

            logger.info(f"Successfully enqueued post-processing for recording {recording_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to enqueue post-processing for recording {recording_id}: {e}")

            # Send error WebSocket update
            if self.websocket_service:
                await self.websocket_service.send_recording_error(
                    recording_id=recording_id, error_message=f"Failed to enqueue post-processing: {str(e)}"
                )

            return False

    async def find_and_validate_mp4(self, ts_file_path: str, max_wait_minutes: int = 10) -> Optional[str]:
        """Find and validate the converted MP4 file"""
        try:
            ts_path = Path(ts_file_path)
            expected_mp4_path = ts_path.with_suffix(".mp4")

            logger.info(f"Looking for MP4 file: {expected_mp4_path}")

            # Wait for MP4 file to appear
            max_wait_seconds = max_wait_minutes * 60
            wait_interval = 10  # Check every 10 seconds
            total_waited = 0

            while total_waited < max_wait_seconds:
                if expected_mp4_path.exists():
                    logger.info(f"Found MP4 file: {expected_mp4_path}")

                    # Validate the MP4 file
                    if await self._validate_mp4_file(expected_mp4_path):
                        logger.info(f"MP4 file validated successfully: {expected_mp4_path}")
                        return str(expected_mp4_path)
                    else:
                        logger.warning(f"MP4 file validation failed: {expected_mp4_path}")
                        return None

                await asyncio.sleep(wait_interval)
                total_waited += wait_interval

                if total_waited % 60 == 0:  # Log every minute
                    logger.info(f"Still waiting for MP4 file... ({total_waited // 60} minutes)")

            logger.warning(f"MP4 file not found after {max_wait_minutes} minutes: {expected_mp4_path}")
            return None

        except Exception as e:
            logger.error(f"Error finding/validating MP4 file for {ts_file_path}: {e}")
            return None

    async def _validate_mp4_file(self, mp4_path: Path) -> bool:
        """Validate MP4 file integrity"""
        try:
            # Check file size (should be > 0)
            file_size = mp4_path.stat().st_size
            if file_size == 0:
                logger.warning(f"MP4 file is empty: {mp4_path}")
                return False

            # Use ffmpeg validation
            is_valid = await validate_mp4(str(mp4_path))
            if not is_valid:
                logger.warning(f"MP4 file failed ffmpeg validation: {mp4_path}")
                return False

            logger.debug(f"MP4 file validation passed: {mp4_path} ({file_size} bytes)")
            return True

        except Exception as e:
            logger.error(f"Error validating MP4 file {mp4_path}: {e}")
            return False

    async def delayed_metadata_generation(self, recording_id: int, delay_minutes: int = 5) -> None:
        """Generate metadata after a delay (for late stream info)"""
        try:
            delay_seconds = delay_minutes * 60
            logger.info(
                f"Scheduling delayed metadata generation for recording {recording_id} in {delay_minutes} minutes"
            )

            await asyncio.sleep(delay_seconds)

            # Enqueue metadata generation task
            payload = {"recording_id": recording_id, "task_type": "delayed_metadata", "delay_applied": delay_minutes}

            # Use background queue to handle delayed metadata
            from app.services.background_queue_service import background_queue_service

            await background_queue_service.enqueue_task(task_type="delayed_metadata_generation", payload=payload)

            logger.info(f"Enqueued delayed metadata generation for recording {recording_id}")

        except Exception as e:
            logger.error(f"Failed to schedule delayed metadata generation for recording {recording_id}: {e}")

    async def generate_stream_metadata(self, recording_id: int, stream_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive metadata for a recording"""
        try:
            metadata = {
                "recording_id": recording_id,
                "generated_at": datetime.utcnow().isoformat(),
                "stream_info": stream_data,
                "processing_info": {
                    "post_processing_required": True,
                    "metadata_generation_time": datetime.utcnow().isoformat(),
                },
            }

            # Add file information if available
            file_path = stream_data.get("file_path")
            if file_path and Path(file_path).exists():
                file_stat = Path(file_path).stat()
                metadata["file_info"] = {
                    "size_bytes": file_stat.st_size,
                    "created_at": datetime.fromtimestamp(file_stat.st_ctime).isoformat(),
                    "modified_at": datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
                }

            # Add stream metadata
            if "title" in stream_data:
                metadata["stream_title"] = stream_data["title"]
            if "category_name" in stream_data:
                metadata["stream_category"] = stream_data["category_name"]
            if "started_at" in stream_data:
                metadata["stream_started_at"] = stream_data["started_at"]

            logger.debug(f"Generated metadata for recording {recording_id}")
            return metadata

        except Exception as e:
            logger.error(f"Failed to generate metadata for recording {recording_id}: {e}")
            return {"recording_id": recording_id, "error": str(e)}

    async def cleanup_temporary_files(self, file_paths: List[str], keep_originals: bool = False) -> List[str]:
        """Clean up temporary files after post-processing"""
        cleaned_files = []

        try:
            for file_path in file_paths:
                path = Path(file_path)

                if not path.exists():
                    logger.debug(f"File already removed: {file_path}")
                    continue

                # Check if it's a temporary file we should clean up
                if keep_originals and not self._is_temporary_file(path):
                    logger.debug(f"Keeping original file: {file_path}")
                    continue

                try:
                    await async_file.remove(file_path)
                    cleaned_files.append(file_path)
                    logger.debug(f"Cleaned up file: {file_path}")
                except Exception as e:
                    logger.warning(f"Failed to clean up file {file_path}: {e}")

            if cleaned_files:
                logger.info(f"Cleaned up {len(cleaned_files)} temporary files")

            return cleaned_files

        except Exception as e:
            logger.error(f"Error during file cleanup: {e}")
            return cleaned_files

    def _is_temporary_file(self, path: Path) -> bool:
        """Check if a file is considered temporary"""
        temp_extensions = {".ts", ".tmp", ".temp", ".part"}
        temp_prefixes = {"temp_", "tmp_", "processing_"}

        # Check extension
        if path.suffix.lower() in temp_extensions:
            return True

        # Check filename prefix
        filename = path.name.lower()
        for prefix in temp_prefixes:
            if filename.startswith(prefix):
                return True

        return False

    async def estimate_processing_time(
        self, file_size_bytes: int, file_duration_seconds: Optional[int] = None
    ) -> Dict[str, float]:
        """Estimate post-processing time based on file characteristics"""
        try:
            # Base estimates (in seconds)
            base_conversion_rate = 0.5  # seconds per MB for TS to MP4 conversion
            base_metadata_time = 30  # base metadata generation time

            file_size_mb = file_size_bytes / (1024 * 1024)

            estimates = {
                "conversion_time": file_size_mb * base_conversion_rate,
                "metadata_time": base_metadata_time,
                "total_time": (file_size_mb * base_conversion_rate) + base_metadata_time,
            }

            # Adjust based on duration if available
            if file_duration_seconds:
                duration_factor = min(file_duration_seconds / 3600, 4.0)  # Cap at 4x for very long streams
                estimates["conversion_time"] *= duration_factor
                estimates["total_time"] = estimates["conversion_time"] + estimates["metadata_time"]

            logger.debug(
                f"Estimated processing time: {estimates['total_time']:.1f} seconds for {file_size_mb:.1f} MB file"
            )
            return estimates

        except Exception as e:
            logger.error(f"Error estimating processing time: {e}")
            return {"conversion_time": 300, "metadata_time": 30, "total_time": 330}  # Default estimates

    async def get_processing_status(self, recording_id: int) -> Dict[str, Any]:
        """Get current post-processing status for a recording"""
        try:
            # This would integrate with the background queue service
            from app.services.background_queue_service import background_queue_service

            # Get tasks related to this recording
            active_tasks = background_queue_service.get_active_tasks()
            completed_tasks = background_queue_service.get_completed_tasks()

            recording_tasks = []

            # Find tasks for this recording
            for task_id, task in {**active_tasks, **completed_tasks}.items():
                if task.payload.get("recording_id") == recording_id:
                    recording_tasks.append(
                        {
                            "task_id": task_id,
                            "task_type": task.task_type,
                            "status": task.status.value,
                            "progress": task.progress,
                            "created_at": task.created_at.isoformat(),
                            "started_at": task.started_at.isoformat() if task.started_at else None,
                            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                        }
                    )

            return {
                "recording_id": recording_id,
                "tasks": recording_tasks,
                "total_tasks": len(recording_tasks),
                "completed_tasks": len([t for t in recording_tasks if t["status"] == "completed"]),
                "failed_tasks": len([t for t in recording_tasks if t["status"] == "failed"]),
                "status_updated_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to get processing status for recording {recording_id}: {e}")
            return {"recording_id": recording_id, "error": str(e), "status_updated_at": datetime.utcnow().isoformat()}
