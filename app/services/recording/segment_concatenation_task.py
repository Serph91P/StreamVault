"""
Segment Concatenation Task Handler

Handles FFmpeg-based segment concatenation for long recordings
that were split into multiple parts.
"""

import asyncio
import logging
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, Callable

logger = logging.getLogger("streamvault")


async def handle_segment_concatenation(task_data: Dict[str, Any], progress_callback: Optional[Callable[[float], None]] = None) -> Dict[str, Any]:
    """
    Handle segment concatenation task
    
    Args:
        task_data: Dict containing:
            - recording_id: int - Recording ID
            - segment_files: list - List of segment file paths
            - output_path: str - Output path for concatenated file
            - streamer_name: str - Streamer name
            - stream_id: int - Stream ID
        progress_callback: Optional[Callable[[float], None]]
            A callback function for progress updates. The callback should accept a single argument:
                - progress (float): A value between 0.0 and 1.0 indicating the percentage of completion.
            The callback will be called periodically during the concatenation process to report progress.
    
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

        # If there's only one segment, avoid ffmpeg concat and just move/copy it
        if len(valid_segments) == 1:
            single = valid_segments[0]
            try:
                output_file.parent.mkdir(parents=True, exist_ok=True)
                if single.resolve() != output_file.resolve():
                    # Prefer moving to avoid duplicate storage; fall back to copy
                    try:
                        single.replace(output_file)
                    except (OSError, PermissionError) as e:
                        logger.warning(f"Could not move segment {single} to {output_file}, copying instead: {e}")
                        shutil.copy2(single, output_file)
                logger.info(f"🎬 SINGLE_SEGMENT_FASTPATH: wrote {output_file}")

                # Update recording path in DB
                try:
                    from app.database import SessionLocal
                    from app.models import Recording
                    with SessionLocal() as db:
                        recording = db.query(Recording).filter(Recording.id == recording_id).first()
                        if recording:
                            recording.path = str(output_file)
                            recording.status = "completed"
                            db.commit()
                except Exception as e:
                    logger.warning(f"Could not update recording after single segment move: {e}")

                # Queue post-processing tasks for the final file
                await _queue_post_processing_tasks(recording_id, str(output_file), task_data)

                # Clean up leftover segment dir if empty
                await _cleanup_segment_files([single], segment_dir)

                return {
                    "success": True,
                    "output_path": str(output_file),
                    "segments_processed": 1,
                    "file_size": output_file.stat().st_size,
                    "recording_id": recording_id
                }
            except Exception as e:
                logger.error(f"Error handling single segment fast-path: {e}", exc_info=True)
                return {"success": False, "error": str(e), "recording_id": recording_id}
        
        try:
            def _ffconcat_escape(p: str) -> str:
                # Escape single quotes for ffconcat syntax: file '...'
                return p.replace("'", "\\'")

            with open(concat_list_path, 'w', encoding='utf-8') as f:
                # Add header for concat demuxer
                f.write("ffconcat version 1.0\n")
                for segment in valid_segments:
                    relative_path = segment.relative_to(segment_dir)
                    safe_name = _ffconcat_escape(str(relative_path))
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
                    stderr_text = stderr.decode('utf-8', errors='replace')[:4096]
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
                    except (ProcessLookupError, OSError) as e:
                        logger.debug(f"Could not kill timed-out process: {e}")
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
                except (OSError, PermissionError) as e:
                    logger.debug(f"Could not remove concat list file {concat_list_path}: {e}")
        
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
        import asyncio
        
        # Validate that stream_id is present
        stream_id = task_data.get('stream_id')
        if stream_id is None:
            # Try to recover stream_id from recording in database
            logger.warning(f"stream_id missing from task_data for recording {recording_id}, attempting recovery from database")
            try:
                # Run blocking DB query in thread pool to avoid stalling event loop
                def _fetch_stream_id():
                    from app.database import SessionLocal
                    from app.models import Recording
                    with SessionLocal() as db:
                        recording = db.query(Recording).filter(Recording.id == recording_id).first()
                        if recording and recording.stream_id:
                            return recording.stream_id
                        return None
                
                loop = asyncio.get_event_loop()
                stream_id = await loop.run_in_executor(None, _fetch_stream_id)
                if stream_id:
                    logger.info(f"Recovered stream_id={stream_id} from recording {recording_id}")
                else:
                    logger.error(f"Could not recover stream_id for recording {recording_id}, cannot queue post-processing")
                    return
            except Exception as e:
                logger.error(f"Error recovering stream_id from database: {e}")
                return
        
        # Create post-processing payload
        post_processing_payload = {
            'stream_id': stream_id,
            'recording_id': recording_id,
            'ts_file_path': ts_file_path,
            'output_dir': str(Path(ts_file_path).parent),
            'streamer_name': task_data.get('streamer_name'),
            'started_at': task_data.get('started_at'),
            'cleanup_ts_file': True
        }
        
        # Queue post-processing chain
        task_ids = await background_queue_service.enqueue_recording_post_processing(**post_processing_payload)
        
        logger.info(f"🎬 POST_PROCESSING_QUEUED: recording_id={recording_id}, stream_id={stream_id}, tasks={len(task_ids)}")
        
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
            except (OSError, PermissionError) as e:
                logger.warning(f"Could not remove segment {segment_file}: {e}")
        
        # Try to remove segment directory if empty
        try:
            if segment_dir.exists() and not any(segment_dir.iterdir()):
                segment_dir.rmdir()
                logger.info(f"🧹 REMOVED_EMPTY_SEGMENT_DIR: {segment_dir}")
        except (OSError, PermissionError) as e:
            logger.debug(f"Could not remove segment directory {segment_dir}: {e}")
            
    except Exception as e:
        logger.error(f"Error cleaning up segments: {e}", exc_info=True)
