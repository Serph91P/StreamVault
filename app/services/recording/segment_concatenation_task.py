"""
Segment Concatenation Task Handler

Handles FFmpeg-based segment concatenation for long recordings
that were split into multiple parts.
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger("streamvault")


async def handle_segment_concatenation(task_data: Dict[str, Any], progress_callback=None) -> Dict[str, Any]:
    """
    Handle segment concatenation task
    
    Args:
        task_data: Dict containing:
            - recording_id: int - Recording ID
            - segment_files: list - List of segment file paths
            - output_path: str - Output path for concatenated file
            - streamer_name: str - Streamer name
            - stream_id: int - Stream ID
        progress_callback: Optional callback for progress updates
    
    Returns:
        Dict with concatenation result
    """
    try:
        recording_id = task_data.get("recording_id")
        segment_files = task_data.get("segment_files", [])
        output_path = task_data.get("output_path")
        streamer_name = task_data.get("streamer_name")
        stream_id = task_data.get("stream_id")
        
        logger.info(f"🎬 SEGMENT_CONCATENATION_START: recording_id={recording_id}, segments={len(segment_files)}")
        
        if not all([recording_id, segment_files, output_path, streamer_name]):
            logger.error(f"Missing required parameters for segment concatenation: {task_data}")
            return {
                "success": False,
                "error": "Missing required parameters",
                "recording_id": recording_id
            }
        
        # Validate segment files exist
        valid_segments = []
        for segment_path in segment_files:
            segment_file = Path(segment_path)
            if segment_file.exists() and segment_file.stat().st_size > 0:
                valid_segments.append(segment_file)
            else:
                logger.warning(f"Segment file missing or empty: {segment_path}")
        
        if not valid_segments:
            logger.error(f"No valid segments found for recording {recording_id}")
            return {
                "success": False,
                "error": "No valid segments found",
                "recording_id": recording_id
            }
        
        # Sort segments to maintain order
        valid_segments.sort()
        
        # Create concatenation list file for FFmpeg
        output_file = Path(output_path)
        segment_dir = valid_segments[0].parent
        concat_list_path = segment_dir / "concat_list.txt"
        
        try:
            with open(concat_list_path, 'w') as f:
                for segment in valid_segments:
                    # Use relative paths for FFmpeg safety
                    relative_path = segment.relative_to(segment_dir)
                    safe_name = str(relative_path).replace("'", "'\"'\"'")
                    f.write(f"file '{safe_name}'\n")
            
            logger.info(f"🎬 CONCAT_LIST_CREATED: {concat_list_path}")
            
            # Run FFmpeg concatenation
            ffmpeg_cmd = [
                "ffmpeg",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_list_path),
                "-c", "copy",
                "-y",  # Overwrite output file
                str(output_file)
            ]
            
            logger.info(f"🎬 STARTING_FFMPEG_CONCAT: {' '.join(ffmpeg_cmd)}")
            
            # Execute FFmpeg with timeout
            try:
                process = await asyncio.wait_for(
                    asyncio.create_subprocess_exec(
                        *ffmpeg_cmd,
                        cwd=str(segment_dir),  # Set working directory
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    ),
                    timeout=30  # 30 seconds to start
                )
                
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=600  # 10 minutes for concatenation
                )
                
                if process.returncode == 0:
                    logger.info(f"🎬 FFMPEG_CONCAT_SUCCESS: {output_file}")
                    
                    # Verify output file
                    if output_file.exists() and output_file.stat().st_size > 0:
                        # Clean up concat list file
                        try:
                            concat_list_path.unlink()
                        except Exception as e:
                            logger.warning(f"Could not remove concat list file: {e}")
                        
                        # Update recording path in database
                        try:
                            from app.database import SessionLocal
                            from app.models import Recording
                            
                            with SessionLocal() as db:
                                recording = db.query(Recording).filter(Recording.id == recording_id).first()
                                if recording:
                                    recording.path = str(output_file)
                                    recording.status = "completed"
                                    db.commit()
                                    logger.info(f"🎬 RECORDING_UPDATED: path={output_file}, status=completed")
                                else:
                                    logger.error(f"Recording {recording_id} not found in database")
                        except Exception as e:
                            logger.error(f"Error updating recording in database: {e}")
                        
                        
                        # Queue post-processing tasks for the concatenated file
                        await _queue_post_processing_tasks(recording_id, str(output_file), task_data)
                        
                        # Clean up segment files after successful concatenation
                        await _cleanup_segment_files(valid_segments, segment_dir)
                        
                        return {
                            "success": True,
                            "output_path": str(output_file),
                            "segments_processed": len(valid_segments),
                            "file_size": output_file.stat().st_size,
                            "recording_id": recording_id
                        }
                    else:
                        logger.error(f"🎬 FFMPEG_OUTPUT_INVALID: {output_file}")
                        return {
                            "success": False,
                            "error": "FFmpeg output file invalid",
                            "recording_id": recording_id
                        }
                else:
                    stderr_text = stderr.decode('utf-8', errors='replace')[:500]
                    logger.error(f"🎬 FFMPEG_CONCAT_FAILED: return_code={process.returncode}, stderr={stderr_text}")
                    return {
                        "success": False,
                        "error": f"FFmpeg failed with code {process.returncode}",
                        "stderr": stderr_text,
                        "recording_id": recording_id
                    }
                    
            except asyncio.TimeoutError:
                logger.error("🎬 FFMPEG_CONCAT_TIMEOUT: Process timed out")
                if 'process' in locals():
                    try:
                        process.kill()
                        await process.wait()
                    except:
                        pass
                return {
                    "success": False,
                    "error": "FFmpeg process timed out",
                    "recording_id": recording_id
                }
                
        finally:
            # Clean up concat list file on error
            if concat_list_path.exists():
                try:
                    concat_list_path.unlink()
                except:
                    pass
        
    except Exception as e:
        logger.error(f"Error in segment concatenation: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "recording_id": task_data.get("recording_id")
        }


async def _queue_post_processing_tasks(recording_id: int, ts_file_path: str, task_data: Dict[str, Any]):
    """Queue the standard post-processing tasks after concatenation"""
    try:
        from app.services.background_queue_service import background_queue_service
        
        # Create post-processing payload
        post_processing_payload = {
            'stream_id': task_data.get('stream_id', recording_id),
            'recording_id': recording_id,
            'ts_file_path': ts_file_path,
            'output_dir': str(Path(ts_file_path).parent),
            'streamer_name': task_data.get('streamer_name'),
            'started_at': task_data.get('started_at'),
            'cleanup_ts_file': True
        }
        
        # Queue post-processing chain
        task_ids = await background_queue_service.enqueue_recording_post_processing(**post_processing_payload)
        
        logger.info(f"🎬 POST_PROCESSING_QUEUED: recording_id={recording_id}, tasks={len(task_ids)}")
        
    except Exception as e:
        logger.error(f"Error queuing post-processing tasks: {e}", exc_info=True)


async def _cleanup_segment_files(segment_files: list, segment_dir: Path):
    """Clean up segment files after successful concatenation"""
    try:
        logger.info(f"🧹 CLEANING_UP_SEGMENTS: {len(segment_files)} files")
        
        # Remove segment files
        for segment_file in segment_files:
            try:
                if segment_file.exists():
                    segment_file.unlink()
                    logger.debug(f"Removed segment: {segment_file}")
            except Exception as e:
                logger.warning(f"Could not remove segment {segment_file}: {e}")
        
        # Try to remove segment directory if empty
        try:
            if segment_dir.exists() and not any(segment_dir.iterdir()):
                segment_dir.rmdir()
                logger.info(f"🧹 REMOVED_EMPTY_SEGMENT_DIR: {segment_dir}")
        except Exception as e:
            logger.debug(f"Could not remove segment directory {segment_dir}: {e}")
            
    except Exception as e:
        logger.error(f"Error cleaning up segments: {e}", exc_info=True)
